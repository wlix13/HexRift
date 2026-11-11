import json
from pathlib import Path

from hexrift.components.schema.models.root import ConglomerateConfig


SCHEMA = Path(__file__).parents[3] / "hexrift" / "components" / "schema" / "schema.json"


def test_committed_schema_matches_models():
    text = json.dumps(ConglomerateConfig.model_json_schema(), indent=2) + "\n"
    assert SCHEMA.read_text(encoding="utf-8") == text
