from __future__ import annotations

from dataclasses import dataclass

from services.assistant_voice_cache import AssistantVoiceCache
from services.assistant_voice_provider import ElevenLabsVoiceProvider


@dataclass(frozen=True)
class AssistantVoiceResult:
    audio: bytes
    cache_key: str
    cache_hit: bool


class AssistantVoiceService:
    provider_name = "elevenlabs"
    model_name = "eleven_multilingual_v2"

    def __init__(
        self,
        provider: ElevenLabsVoiceProvider | None = None,
        cache: AssistantVoiceCache | None = None,
    ):
        self.provider = provider or ElevenLabsVoiceProvider()
        self.cache = cache or AssistantVoiceCache()

    def generate_mp3(
        self,
        *,
        text: str,
        voice_id: str,
        language: str = "uk-UA",
        settings: dict | None = None,
    ) -> AssistantVoiceResult:
        cache_key = self.cache.build_key(
            provider=self.provider_name,
            model=self.model_name,
            voice_id=voice_id,
            language=language,
            text=text,
            settings=settings,
        )

        cached_audio = self.cache.get(cache_key)
        if cached_audio is not None:
            return AssistantVoiceResult(
                audio=cached_audio,
                cache_key=cache_key,
                cache_hit=True,
            )

        audio = self.provider.generate_mp3(text, voice_id)
        self.cache.put(cache_key, audio)

        return AssistantVoiceResult(
            audio=audio,
            cache_key=cache_key,
            cache_hit=False,
        )
