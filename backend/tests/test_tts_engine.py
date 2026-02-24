import pytest
from unittest.mock import patch, MagicMock
from app.services.tts_engine import TTSEngine


@pytest.fixture
def engine():
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Return a minimal WAV: RIFF header + enough bytes
    wav_header = b"RIFF" + b"\x00" * 40 + b"\x01\x02\x03\x04"
    mock_response.read.return_value = wav_header
    mock_client.audio.speech.create.return_value = mock_response
    with patch("app.services.tts_engine.Groq", return_value=mock_client):
        e = TTSEngine(api_key="test-key")
        yield e


def test_generate_returns_wav_bytes(engine):
    audio_bytes = engine.generate("Hello world")
    assert isinstance(audio_bytes, bytes)
    assert audio_bytes[:4] == b"RIFF"


def test_generate_skips_empty_text(engine):
    assert engine.generate("") is None
    assert engine.generate("   ") is None


def test_generate_skips_mermaid(engine):
    assert engine.generate("```mermaid\ngraph TD\nA-->B\n```") is None
