from pathlib import Path
from typing import Optional
from openai import OpenAI


def transcribe_audio(
    audio_path: Path,
    api_key: Optional[str] = None,
    prompt: Optional[str] = None
) -> str:
    """
    Transcribes an audio file into text using OpenAI Whisper API.
    Provides domain-specific prompts (Korean & English fitness terms)
    for improved recognition of exercise names and reps.
    """
    if not audio_path or not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    client = OpenAI(api_key=api_key) if api_key else OpenAI()

    fitness_prompt = prompt or (
        "헬스, 운동 루틴, 세트, 횟수, 랫풀다운, 데드리프트, 스쿼트, 벤치프레스, "
        "바벨, 덤벨, 가슴, 등, 하체, 어깨, 이두, 삼두, 광배근, 대흉근, "
        "reps, sets, workout routine, form cues, posture, drop set, superset"
    )

    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            prompt=fitness_prompt,
        )

    return transcription.text
