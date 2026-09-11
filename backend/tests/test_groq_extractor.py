import json
from unittest.mock import patch

import pytest
import respx
from httpx import Response

from app.services.extraction.groq_extractor import (
    _clean_json_markdown,
    extract_with_groq,
)


@pytest.fixture
def sample_label_bytes():
    # 1x1 transparent PNG bytes
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


@pytest.fixture
def mock_groq_json_payload():
    return {
        "fields": {
            "manufacturer_name": {
                "raw": "Hindustan Foods Ltd",
                "confidence": 0.98,
                "bbox": [100.0, 100.0, 150.0, 300.0],
                "present": True,
            },
            "manufacturer_address": {
                "raw": "Plot 12, Whitefield, Bengaluru, Karnataka 560066",
                "confidence": 0.95,
                "bbox": [155.0, 100.0, 200.0, 450.0],
                "present": True,
            },
            "importer_name": {"present": False, "confidence": 0.0},
            "importer_address": {"present": False, "confidence": 0.0},
            "country_of_origin": {
                "raw": "India",
                "normalized": "India",
                "confidence": 0.99,
                "present": True,
            },
            "net_quantity": {
                "raw": "500 g",
                "value": 500.0,
                "unit": "g",
                "confidence": 0.96,
                "present": True,
            },
            "mrp": {
                "raw": "Rs 150.00 (incl. of all taxes)",
                "value": 150.0,
                "currency": "INR",
                "taxes_inclusive_text": "Inclusive of all taxes",
                "confidence": 0.97,
                "present": True,
            },
            "mfg_date": {
                "raw": "01/2026",
                "month": 1,
                "year": 2026,
                "confidence": 0.94,
                "present": True,
            },
            "expiry_date": {
                "raw": "01/2027",
                "month": 1,
                "year": 2027,
                "confidence": 0.93,
                "present": True,
            },
            "consumer_care": {
                "phone": ["1800200300"],
                "email": "care@example.com",
                "address": "Whitefield, Bengaluru",
                "confidence": 0.92,
                "present": True,
            },
            "dimensions": {"present": False, "confidence": 0.0},
            "generic_name": {
                "raw": "Rolled Oats",
                "confidence": 0.95,
                "present": True,
            },
            "quantity_declaration_other": {"present": False, "confidence": 0.0},
        },
        "detected_text_blocks": [
            {
                "text": "NutriHarvest Rolled Oats 500g",
                "bbox": [50.0, 100.0, 90.0, 400.0],
                "estimated_char_height_px": 24.0,
            }
        ],
        "page_count": 1,
        "language_hints": ["en"],
        "raw_text": "NutriHarvest Rolled Oats 500g MRP Rs 150.00 incl. of all taxes",
    }


def test_clean_json_markdown():
    wrapped = '```json\n{"foo": "bar"}\n```'
    assert _clean_json_markdown(wrapped) == '{"foo": "bar"}'

    plain = '{"foo": "bar"}'
    assert _clean_json_markdown(plain) == '{"foo": "bar"}'


def test_groq_missing_api_key(sample_label_bytes):
    with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
        extract_with_groq([sample_label_bytes], api_key="")


@respx.mock
def test_groq_successful_multimodal_extraction(sample_label_bytes, mock_groq_json_payload):
    route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(mock_groq_json_payload),
                        }
                    }
                ]
            },
            headers={
                "x-ratelimit-remaining-requests": "29",
                "x-ratelimit-remaining-tokens": "69000",
            },
        )
    )

    result, avg_conf, model_used = extract_with_groq(
        [sample_label_bytes],
        api_key="gsk_test_mock_key",
        preferred_model="groq/compound",
    )

    assert route.called
    assert model_used == "groq/compound"
    assert avg_conf > 0.9
    assert result.fields.manufacturer_name.raw == "Hindustan Foods Ltd"
    assert result.fields.manufacturer_name.source == "groq"
    assert result.fields.net_quantity.value == 500.0
    assert result.fields.net_quantity.unit == "g"
    assert result.fields.mrp.value == 150.0


@respx.mock
def test_groq_rate_limit_failover(sample_label_bytes, mock_groq_json_payload):
    # First request to groq/compound returns 429
    # Second request to groq/compound-mini returns 200
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        side_effect=[
            Response(429, json={"error": "Rate limit exceeded"}, headers={"retry-after": "2"}),
            Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(mock_groq_json_payload),
                            }
                        }
                    ]
                },
            ),
        ]
    )

    result, avg_conf, model_used = extract_with_groq(
        [sample_label_bytes],
        api_key="gsk_test_mock_key",
        preferred_model="groq/compound",
        fallback_models=["groq/compound-mini", "openai/gpt-oss-120b"],
    )

    assert model_used == "groq/compound-mini"
    assert result.fields.manufacturer_name.raw == "Hindustan Foods Ltd"


@respx.mock
def test_groq_unsupported_vision_falls_back_to_text_ocr(sample_label_bytes, mock_groq_json_payload):
    # First request returns 400 Bad Request with vision error
    # Second request with text-only payload returns 200 OK
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        side_effect=[
            Response(400, text="Model openai/gpt-oss-120b does not support image or vision inputs"),
            Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(mock_groq_json_payload),
                            }
                        }
                    ]
                },
            ),
        ]
    )

    with patch(
        "app.services.extraction.groq_extractor._extract_offline_ocr_text",
        return_value="Sample OCR Text",
    ):
        result, avg_conf, model_used = extract_with_groq(
            [sample_label_bytes],
            api_key="gsk_test_mock_key",
            preferred_model="openai/gpt-oss-120b",
            fallback_models=[],
        )

    assert model_used == "openai/gpt-oss-120b"
    assert result.fields.country_of_origin.raw == "India"


@respx.mock
def test_groq_all_models_fail_raises_runtime_error(sample_label_bytes):
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=Response(500, json={"error": "Internal Server Error"})
    )

    with pytest.raises(RuntimeError, match="All Groq models exhausted"):
        extract_with_groq(
            [sample_label_bytes],
            api_key="gsk_test_mock_key",
            preferred_model="groq/compound",
            fallback_models=["groq/compound-mini"],
        )
