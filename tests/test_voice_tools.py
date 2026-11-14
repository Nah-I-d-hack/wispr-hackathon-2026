"""[K] K2 helpers: STT scoring and the Wispr request shape (no network)."""
import base64

from eval.voice.metrics import cer, idiom_hits, normalise, wer
from voice import vocab, wispr


def test_normalise_handles_danda_and_case():
    assert normalise("Seene mein dard hai।") == "seene mein dard hai"
    assert normalise("বুকে ব্যথা।") == "বুকে ব্যথা"


def test_wer_cer():
    assert wer("mujhe chakkar aa raha hai", "mujhe chakkar aa raha hai") == 0
    assert wer("mujhe chakkar aa raha hai", "mujhe shakkar aa raha hai") == 0.2
    assert cer("gas", "gas") == 0 and cer("gas", "") == 1


def test_idiom_hits():
    idioms = ["chakkar aana", "seene mein bhaari", "gas"]
    assert idiom_hits("kal se chakkar aana shuru hua aur gas bhi", "kal se shakkar aana shuru hua aur gas bhi", idioms) == (2, 1)


def test_vocab_reads_safety_md():
    p = vocab.symptom_phrases()
    assert "chakkar aana" in p and "seene mein bhaari" in p and "dil baith raha hai" in p
    assert not any("?" in x for x in p)


def test_wispr_request_shape():
    b = wispr.build_request(b"RIFF", ["hi", "en"], ["chakkar", "chakkar"], [{"role": "assistant", "content": "Kab se hai?"}])
    assert base64.b64decode(b["audio"]) == b"RIFF" and b["language"] == ["hi", "en"]
    assert b["context"]["dictionary_context"] == ["chakkar"]
    assert b["context"]["conversation"]["messages"][0]["content"] == "Kab se hai?"
