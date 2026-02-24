"""Text-to-speech using Groq Orpheus API."""

from __future__ import annotations

import re

from groq import Groq


def _sanitize_for_tts(text: str) -> str:
    """Clean text so the TTS model can pronounce it correctly."""
    # Strip markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # *italic*
    text = re.sub(r"`(.+?)`", r"\1", text)  # `code`
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)  # # headings

    # Replace math symbols with speakable words
    text = text.replace("÷", " divided by ")
    text = text.replace("×", " times ")
    text = text.replace("→", " gives ")
    text = text.replace("←", " from ")
    text = text.replace("≈", " approximately ")
    text = text.replace("≠", " not equal to ")
    text = text.replace("≤", " less than or equal to ")
    text = text.replace("≥", " greater than or equal to ")
    text = text.replace("±", " plus or minus ")

    # Collapse newlines into spaces
    text = text.replace("\n", " ")

    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


class TTSEngine:
    """Generate speech audio using Groq Orpheus."""

    def __init__(self, api_key: str, voice: str = "autumn") -> None:
        self.voice = voice
        self.client = Groq(api_key=api_key)

    def generate(self, text: str) -> bytes | None:
        """Generate WAV audio bytes from text. Returns None if text should be skipped."""
        text = text.strip()
        if not text:
            return None
        if re.match(r"^```mermaid", text):
            return None

        text = _sanitize_for_tts(text)
        if not text:
            return None

        try:
            response = self.client.audio.speech.create(
                model="canopylabs/orpheus-v1-english",
                voice=self.voice,
                response_format="wav",
                input=text,
            )
            return response.read()
        except Exception as e:
            print(f"[TTS] Error on text: {text!r}: {e}")
            return None
