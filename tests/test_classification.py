from guidance_intel.classification import build_uuid_index, classify_read
from guidance_intel.models import TranscriptEvent


def _user(uuid, text, parent=None, mentions=None):
    return TranscriptEvent(
        kind="user_message", name="user", session_id="s1", uuid=uuid, parent_uuid=parent,
        metadata={"text": text, "mentions": mentions or []},
    )


def _read(uuid, file_path, parent=None, sidechain=False):
    return TranscriptEvent(
        kind="document", name="TEST_PLAN", session_id="s1", uuid=uuid, parent_uuid=parent,
        is_sidechain=sidechain,
        metadata={"file_path": file_path, "manual_reference": True},
    )


def _classify(events, read):
    return classify_read(read, events, build_uuid_index(events))


# --- Causal path ---

def test_exact_filename_is_user_requested_high():
    u = _user("u1", "Read docs/TEST_PLAN.md and run it")
    r = _read("a1", "docs/TEST_PLAN.md", parent="u1")
    res = _classify([u, r], r)
    assert res.classification == "user_requested"
    assert res.confidence == "high"
    assert res.method == "causal"


def test_autonomous_when_no_mention():
    u = _user("u1", "Generate tests for the friends package")
    r = _read("a1", "docs/TEST_PLAN.md", parent="u1")
    res = _classify([u, r], r)
    assert res.classification == "autonomous"
    assert res.confidence == "high"


def test_sidechain_read_is_autonomous():
    u = _user("u1", "Read docs/TEST_PLAN.md")  # even with a mention...
    r = _read("a1", "docs/TEST_PLAN.md", parent="u1", sidechain=True)
    res = _classify([u, r], r)
    assert res.classification == "autonomous"
    assert "subagent" in res.reason.lower()


def test_at_mention_is_high():
    u = _user("u1", "check this", mentions=["docs/TEST_PLAN.md"])
    r = _read("a1", "docs/TEST_PLAN.md", parent="u1")
    res = _classify([u, r], r)
    assert res.classification == "user_requested"
    assert res.confidence == "high"


def test_multi_hop_chain_resolves_to_user():
    u = _user("u1", "Read docs/TEST_PLAN.md")
    mid = TranscriptEvent(kind="skill", name="graphify", session_id="s1", uuid="a1", parent_uuid="u1")
    r = _read("a2", "docs/TEST_PLAN.md", parent="a1")
    res = _classify([u, mid, r], r)
    assert res.classification == "user_requested"


def test_name_plus_verb_is_medium():
    u = _user("u1", "please review the graphify skill")
    r = TranscriptEvent(
        kind="skill", name="graphify", session_id="s1", uuid="a1", parent_uuid="u1",
        metadata={"file_path": ".claude/skills/graphify/SKILL.md", "manual_reference": True},
    )
    res = _classify([u, r], r)
    assert res.classification == "user_requested"
    assert res.confidence == "medium"


def test_no_user_turn_in_chain_is_system():
    # Read whose parent chain never reaches a user message.
    root = TranscriptEvent(kind="skill", name="x", session_id="s1", uuid="a0", parent_uuid=None)
    r = _read("a1", "docs/TEST_PLAN.md", parent="a0")
    res = _classify([root, r], r)
    assert res.classification == "system"


# --- Heuristic fallback (no causal fields) ---

def test_heuristic_fallback_matches_recent_user_message():
    u = TranscriptEvent(kind="user_message", name="user", session_id="s1",
                        metadata={"text": "Read docs/TEST_PLAN.md", "mentions": []})
    r = TranscriptEvent(kind="document", name="TEST_PLAN", session_id="s1",
                        metadata={"file_path": "docs/TEST_PLAN.md", "manual_reference": True})
    res = _classify([u, r], r)
    assert res.classification == "user_requested"
    assert res.method == "heuristic"
    assert res.confidence == "medium"  # downgraded from high


def test_heuristic_no_user_messages_is_unknown():
    r = TranscriptEvent(kind="document", name="TEST_PLAN", session_id="s1",
                        metadata={"file_path": "docs/TEST_PLAN.md", "manual_reference": True})
    res = _classify([r], r)
    assert res.classification == "unknown"
    assert res.confidence == "none"
