from __future__ import annotations

import os


ASSISTANT_VOICE_PROFILES = {
    "male": os.getenv("ELEVENLABS_MALE_VOICE_ID", "CwhRBWXzGAHq8TQ4Fs17"),
    "female": os.getenv("ELEVENLABS_FEMALE_VOICE_ID", "yMBZR4SLoc24wOJLWAB2"),
}


def get_assistant_voice_id(profile: str) -> str:
    try:
        return ASSISTANT_VOICE_PROFILES[profile]
    except KeyError as exc:
        raise ValueError(f"Unsupported assistant voice profile: {profile}") from exc
