import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from app.services.tts_engine import TTSEngine


@pytest.fixture
def engine():
    with patch("app.services.tts_engine.KittenTTS") as mock_cls:
        mock_model = MagicMock()
        mock_model.generate.return_value = np.zeros(24000, dtype=np.float32)  # 1 sec silence
        mock_cls.return_value = mock_model
        e = TTSEngine()
        yield e


def test_generate_returns_wav_bytes(engine):
    audio_bytes = engine.generate("Hello world")
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0


def test_generate_skips_empty_text(engine):
    assert engine.generate("") is None
    assert engine.generate("   ") is None


def test_generate_skips_mermaid(engine):
    assert engine.generate("```mermaid\ngraph TD\nA-->B\n```") is None
