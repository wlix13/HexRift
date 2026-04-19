from pathlib import Path

import pytest

from hexrift.app import HexRiftApp


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
FIXTURE_TOPOLOGY = FIXTURES_DIR / "topology.yaml"
FIXTURE_KEYS_DIR = FIXTURES_DIR / "keys"
FIXTURE_CONFIGS_DIR = FIXTURES_DIR / "configs"


@pytest.fixture()
def real_app() -> HexRiftApp:
    return HexRiftApp(yaml_path=FIXTURE_TOPOLOGY)
