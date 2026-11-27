"""[R] The AI-model timeout path (deck slide 7): when Gemini times out, the turn falls back to the rules and
emergencies still escalate. No network: urlopen is replaced by a fake that records the timeout and raises.
Run: python -m pytest tests/test_agent_llm_timeout.py -q
"""
from __future__ import annotations

import pytest

from agent import core, llm


@pytest.fixture
def llm_times_out(monkeypatch):
    seen = []

    def fake_urlopen(req, timeout=None):
        seen.append(timeout)
        raise TimeoutError("timed out")

    monkeypatch.delenv("AGENT_NO_LLM", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("AGENT_LLM_MIN_INTERVAL", "0")
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    return seen


def _turn(text, i, state, lang="hi", channel="web"):
    req = {"contract": "1.0", "session_id": "timeout", "turn": i, "channel": channel, "state": state}
    if text is None:
        req.update(event="start", ui_lang_hint=lang)
    else:
        req.update(event="utterance", transcript={"text": text, "language": lang})
    return core.turn(req)


def test_timeout_uses_the_configured_limit_and_falls_back(llm_times_out):
    assert llm.available()
    r = _turn(None, 0, None)
    r = _turn("do din se halka bukhar hai", 1, r["state"])
    assert llm_times_out and all(t == core.LLM_TIMEOUT for t in llm_times_out)
    assert r["debug"]["fallback"] is True and "Timeout" in r["debug"]["reason"]
    assert r["action"] == "ask" and r["escalation"] is None  # routine: the rules still ask the next question


@pytest.mark.parametrize("channel", ["web", "phone_in"])
def test_emergency_still_escalates_when_the_model_times_out(llm_times_out, channel):
    r = _turn(None, 0, None, channel=channel)
    r = _turn("seene mein bahut dard hai aur saans nahi aa rahi", 1, r["state"], channel=channel)
    assert r["debug"]["fallback"] is True
    assert r["action"] == "escalate" and r["escalation"]["call"]["number"] == "112"
    assert r["escalation"].get("transfer", False) is (channel == "phone_in")
