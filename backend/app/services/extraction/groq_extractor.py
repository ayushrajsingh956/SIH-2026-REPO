import base64
import io
import json
import logging
import re
from typing import Any

import httpx
from PIL import Image

from app.core.config import GROQ_MODEL_LIMITS, settings
from app.schemas.extraction import ExtractionResultSchema
from app.services.extraction.gemini_extractor import apply_normalizations, compute_avg_confidence
from app.services.extraction.prompts import LMPC_EXTRACTION_PROMPT_V1

logger = logging.getLogger(__name__)


def _clean_json_markdown(text: str) -> str:
    """Removes markdown code fences and extraneous text from JSON output."""
    trimmed = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", trimmed, re.DOTALL)
    if match:
        return match.group(1).strip()
    brace_match = re.search(r"(\{.*\})", trimmed, re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()
    return trimmed


def _extract_offline_ocr_text(images_bytes: list[bytes]) -> str:
    """Extracts raw text from image buffers using pytesseract as a fallback for text-only LLMs."""
    import pytesseract

    accumulated: list[str] = []
    for idx, img_buf in enumerate(images_bytes):
        try:
            pil_img = Image.open(io.BytesIO(img_buf))
            text = pytesseract.image_to_string(pil_img)
            if text.strip():
                accumulated.append(f"--- Image {idx + 1} Raw OCR Text ---\n{text.strip()}")
        except Exception as exc:
            logger.warning("OCR text extraction failed for image %d: %s", idx, exc)
    return "\n\n".join(accumulated)


def extract_with_groq(
    images_bytes: list[bytes],
    mime_types: list[str] | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    preferred_model: str | None = None,
    fallback_models: list[str] | None = None,
    timeout: float = 20.0,
) -> tuple[ExtractionResultSchema, float, str]:
    """Invokes Groq's OpenAI-compatible API to extract structured LMPC compliance declarations.

    Supports multimodal vision payloads, automatic failover across configured fallback models
    upon rate limiting (HTTP 429), and OCR-text based structuring for text-specialized models.

    Args:
        images_bytes: Raw bytes of preprocessed product label images.
        mime_types: Optional MIME types corresponding to images.
        api_key: Optional Groq API key (defaults to settings.GROQ_API_KEY).
        base_url: Optional Groq Base URL (defaults to settings.GROQ_BASE_URL).
        preferred_model: Initial model to attempt (defaults to settings.GROQ_MODEL).
        fallback_models: Ordered list of models to try if the initial model fails.
        timeout: HTTP request timeout in seconds.

    Returns:
        tuple of (ExtractionResultSchema, avg_confidence, model_used)

    Raises:
        ValueError: If Groq API key is missing or response is unparseable.
        RuntimeError: If all candidate models in the fallback chain fail.
    """
    key = api_key or settings.GROQ_API_KEY
    if not key:
        raise ValueError("GROQ_API_KEY is not configured.")

    endpoint = (base_url or settings.GROQ_BASE_URL).rstrip("/")
    url = f"{endpoint}/chat/completions"

    # Build candidate model sequence preserving user order without duplicates
    primary = preferred_model or settings.GROQ_MODEL or "groq/compound"
    fallbacks = (
        fallback_models
        or settings.GROQ_FALLBACK_MODELS
        or [
            "groq/compound",
            "groq/compound-mini",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
        ]
    )

    candidate_models: list[str] = []
    for m in [primary] + list(fallbacks):
        if m and m not in candidate_models:
            candidate_models.append(m)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "LegalMetro-Shield/1.0",
    }

    # Prepare base64 images for multimodal vision requests
    image_contents: list[dict[str, Any]] = []
    for idx, img_buf in enumerate(images_bytes):
        mtype = mime_types[idx] if (mime_types and idx < len(mime_types)) else "image/png"
        b64_img = base64.b64encode(img_buf).decode("utf-8")
        image_contents.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mtype};base64,{b64_img}"},
            }
        )

    schema_prompt = (
        f"{LMPC_EXTRACTION_PROMPT_V1}\n\n"
        "CRITICAL INSTRUCTION: Return a single strictly valid JSON object matching this schema:\n"
        f"{json.dumps(ExtractionResultSchema.model_json_schema(), indent=2)}"
    )

    errors: list[str] = []
    cached_ocr_text: str | None = None

    for model in candidate_models:
        tier_info = GROQ_MODEL_LIMITS.get(model, {})
        logger.info(
            "Attempting Groq extraction with model '%s' (Tier limits: %s RPM, %s RPD)",
            model,
            tier_info.get("rpm", "N/A"),
            tier_info.get("rpd", "N/A"),
        )

        # 1. Attempt Multimodal Vision Call
        multimodal_payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a specialized Legal Metrology Vision AI. Always output strictly valid JSON matching the requested schema.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": schema_prompt},
                        *image_contents,
                    ],
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, headers=headers, json=multimodal_payload)

                # Telemetry: Log rate limit headers from Groq if provided
                req_rem = resp.headers.get("x-ratelimit-remaining-requests")
                tok_rem = resp.headers.get("x-ratelimit-remaining-tokens")
                if req_rem is not None:
                    logger.debug(
                        "Groq [%s] remaining requests: %s, tokens: %s", model, req_rem, tok_rem
                    )

                # Rate Limit (429) or Server Overload (503) -> Failover to next candidate model
                if resp.status_code in (429, 503):
                    retry_after = resp.headers.get("retry-after", "unknown")
                    msg = f"Model {model} hit rate limit / capacity (HTTP {resp.status_code}, Retry-After: {retry_after})"
                    logger.warning("%s. Failing over to next fallback model.", msg)
                    errors.append(msg)
                    continue

                # If model is text-only or returns 400 rejecting image_url, fallback to OCR transcript
                if resp.status_code == 400:
                    logger.info(
                        "Model %s does not accept vision inputs (%s). Retrying with OCR text prompt.",
                        model,
                        resp.text[:80],
                    )
                    if cached_ocr_text is None:
                        cached_ocr_text = _extract_offline_ocr_text(images_bytes)

                    text_payload = {
                        "model": model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a specialized Legal Metrology AI. Always output strictly valid JSON matching the requested schema.",
                            },
                            {
                                "role": "user",
                                "content": (
                                    f"{schema_prompt}\n\n"
                                    f"Extracted Raw OCR Text from Label:\n```\n{cached_ocr_text}\n```"
                                ),
                            },
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    }
                    resp = client.post(url, headers=headers, json=text_payload)

                resp.raise_for_status()
                data = resp.json()

                # Extract content from OpenAI chat completion choices
                choices = data.get("choices")
                if not choices or not choices[0].get("message", {}).get("content"):
                    raise ValueError(f"Groq model {model} returned empty completion content.")

                raw_content = choices[0]["message"]["content"]
                clean_json_str = _clean_json_markdown(raw_content)
                parsed_json = json.loads(clean_json_str)

                result_schema = ExtractionResultSchema.model_validate(parsed_json)

                # Tag extracted fields with source="groq"
                for _, field_obj in result_schema.fields:
                    if hasattr(field_obj, "source"):
                        field_obj.source = "groq"

                # Apply standard normalizers (currency, date, metric units, addresses)
                result_schema = apply_normalizations(result_schema)
                avg_conf = compute_avg_confidence(result_schema)

                logger.info(
                    "Groq extraction succeeded with model '%s' (Confidence: %s)", model, avg_conf
                )
                return result_schema, avg_conf, model

        except Exception as exc:
            err_msg = f"Groq extraction with model '{model}' failed: {exc}"
            logger.warning(err_msg)
            errors.append(err_msg)
            continue

    raise RuntimeError(f"All Groq models exhausted. Errors: {'; '.join(errors)}")
