from __future__ import annotations

import os

import httpx


class AssistantVoiceProviderError(RuntimeError):
    pass


class ElevenLabsVoiceProvider:
    base_url = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 30.0):
        self.api_key = (api_key or os.getenv("ELEVENLABS_API_KEY") or "").strip()
        self.timeout_seconds = timeout_seconds

    def generate_mp3(self, text: str, voice_id: str) -> bytes:
        value = str(text or "").strip()
        voice = str(voice_id or "").strip()

        if not self.api_key:
            raise AssistantVoiceProviderError("ELEVENLABS_API_KEY is not configured")
        if not value:
            raise AssistantVoiceProviderError("Text is required")
        if not voice:
            raise AssistantVoiceProviderError("Voice ID is required")

        url = f"{self.base_url}/text-to-speech/{voice}"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": value,
            "model_id": "eleven_multilingual_v2",
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AssistantVoiceProviderError("ElevenLabs TTS request failed") from exc

        if not response.content:
            raise AssistantVoiceProviderError("ElevenLabs returned empty audio")

        return response.content
