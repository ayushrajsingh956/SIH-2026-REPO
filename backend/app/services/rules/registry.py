import logging
from pathlib import Path

import yaml

from app.schemas.rule import RuleDefinitionSchema

logger = logging.getLogger(__name__)

_DEFAULT_DEFINITIONS_DIR = Path(__file__).parent / "definitions"
_RULE_CACHE: dict[str, RuleDefinitionSchema] | None = None


def load_rules(
    definitions_dir: Path | None = None, reload: bool = False
) -> dict[str, RuleDefinitionSchema]:
    """
    Loads and validates all YAML rule definitions from definitions_dir.
    Raises ValueError or pydantic.ValidationError if any rule fails schema validation.
    Caches rules in memory.
    """
    global _RULE_CACHE
    if _RULE_CACHE is not None and not reload:
        return _RULE_CACHE

    target_dir = definitions_dir or _DEFAULT_DEFINITIONS_DIR
    if not target_dir.exists():
        raise FileNotFoundError(f"Rules definition directory not found: {target_dir}")

    loaded: dict[str, RuleDefinitionSchema] = {}
    yaml_files = sorted(list(target_dir.glob("*.yaml")) + list(target_dir.glob("*.yml")))

    if not yaml_files:
        logger.warning(f"No YAML rule definitions found in {target_dir}")

    for file_path in yaml_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ValueError(
                    f"Rule definition file {file_path.name} must contain a YAML mapping"
                )
            rule = RuleDefinitionSchema.model_validate(data)
            if rule.id in loaded:
                raise ValueError(f"Duplicate rule ID '{rule.id}' detected in {file_path.name}")
            loaded[rule.id] = rule
        except Exception as e:
            logger.error(f"Failed to parse rule definition in {file_path.name}: {e}")
            raise

    _RULE_CACHE = loaded
    logger.info(f"Loaded and validated {len(_RULE_CACHE)} LMPC compliance rules.")
    return _RULE_CACHE


def get_all_rules() -> dict[str, RuleDefinitionSchema]:
    """Returns cached rules dictionary, loading them if necessary."""
    return load_rules()


def get_rule(rule_id: str) -> RuleDefinitionSchema | None:
    """Retrieves a single rule definition by its ID."""
    return get_all_rules().get(rule_id)


def clear_cache() -> None:
    """Clears the rule definition cache (used in testing)."""
    global _RULE_CACHE
    _RULE_CACHE = None
