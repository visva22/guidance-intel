import pytest
from pathlib import Path


@pytest.fixture
def fixtures_path():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def repo_path(fixtures_path):
    return str(fixtures_path / "repo")


@pytest.fixture
def transcripts_path(fixtures_path):
    return str(fixtures_path / "transcripts")
