import io
import re

import soundfile as sf

try:
    from kittentts import KittenTTS
except ImportError:
    KittenTTS = None  # Will be injected or fail at runtime


class TTSEngine:
    def __init__(
        self,
        model_name: str = "KittenML/kitten-tts-nano-0.8-int8",
        voice: str = "Bella",
    ):
        self.model = KittenTTS(model_name)
        self.voice = voice

    def generate(self, text: str) -> bytes | None:
        """Generate WAV audio bytes from text. Returns None if text should be skipped."""
        text = text.strip()
        if not text:
            return None
        if re.match(r"^```mermaid", text):
            return None
        audio = self.model.generate(text, voice=self.voice)
        buf = io.BytesIO()
        sf.write(buf, audio, 24000, format="WAV")
        return buf.getvalue()
