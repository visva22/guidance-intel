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


@pytest.fixture
def real_transcripts_path(fixtures_path):
    """Real-shaped Claude Code transcripts with causal fields, user messages, and sidechains."""
    return str(fixtures_path / "real_transcripts")
