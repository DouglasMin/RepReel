import os
from typing import Optional, Dict, Any
from openai import OpenAI
from src.schema import WorkoutProgram

SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT = """You are an elite Strength & Conditioning Software Architect and Kinesiology Specialist.
Your goal is to parse raw Instagram Reel content (audio transcription from speech, plus caption/post description) into a deeply structured, hierarchical, database-ready `WorkoutProgram`.

Follow this systematic 4-Stage Reasoning Process:

─────────────────────────────────────────────────────────────
STAGE 1: ENTITY NORMALIZATION & SLANG RESOLUTION
─────────────────────────────────────────────────────────────
• Decode all Korean gym abbreviations and slang into standardized bilingual names:
  - '사레레' -> canonical_name_ko: '사이드 레터럴 레이즈', canonical_name_en: 'Side Lateral Raise', equipment: DUMBBELL
  - '벤레레' -> canonical_name_ko: '벤트오버 레터럴 레이즈', canonical_name_en: 'Bent-Over Lateral Raise', equipment: DUMBBELL
  - '불스스' -> canonical_name_ko: '불가리안 스플릿 스쿼트', canonical_name_en: 'Bulgarian Split Squat', equipment: DUMBBELL or BODYWEIGHT
  - '루데' -> canonical_name_ko: '루마니안 데드리프트', canonical_name_en: 'Romanian Deadlift', equipment: BARBELL or DUMBBELL
  - '인클덤프' -> canonical_name_ko: '인클라인 덤벨 프레스', canonical_name_en: 'Incline Dumbbell Press', equipment: DUMBBELL
• Accurately classify `EquipmentType` (BARBELL, DUMBBELL, CABLE, MACHINE, BODYWEIGHT).
• Identify anatomical `primary_muscle` and synergist `secondary_muscles`.

─────────────────────────────────────────────────────────────
STAGE 2: HIERARCHICAL PROGRAM DECOMPOSITION
─────────────────────────────────────────────────────────────
• Identify the high-level split (e.g., PPL, Upper/Lower, Full Body).
• Divide the program into sequential `WorkoutDay` units (Day 1, Day 2, Day 3, etc.).
• Within each day, organize exercises into logical `ExerciseGroup` categories:
  - `MAIN_COMPOUND`: Primary heavy compound strength lifts (e.g., Bench Press, Pull-Up, Squat).
  - `ACCESSORY`: Secondary compound or targeted accessory movements.
  - `ISOLATION`: Single-joint isolation or raise movements (e.g., lateral raises, curls, extensions).
  - `CORE_FINISHER`: Core stabilization and abdominal movements (e.g., hanging leg raises).

─────────────────────────────────────────────────────────────
STAGE 3: VOLUME SOLVER & RULE PROPAGATION
─────────────────────────────────────────────────────────────
• Propagate stated volume rules across the tree:
  - Main compound movements: sets: min_sets=5, max_sets=5, reps: min_reps=8, max_reps=12, is_main_lift=True.
  - Accessory movements: sets: min_sets=3, max_sets=4, reps: min_reps=8, max_reps=12, is_main_lift=False.
  - Isolation/Raise movements (e.g. Lateral Raises): sets: min_sets=3, max_sets=4, reps: min_reps=15, max_reps=20, rep_type: REPS_RANGE.
• If sets or reps are given as a range (e.g. 3-4 sets), set `min_sets=3`, `max_sets=4` and mark `sets_ambiguous=True` in DataQualityAudit.

─────────────────────────────────────────────────────────────
STAGE 4: QUALITY AUDIT & MOBILE ACTION ITEM GENERATION
─────────────────────────────────────────────────────────────
• Detect missing variables needed for a mobile workout log (starting weights, rest intervals, set confirmations).
• Generate concrete `user_action_items` for the mobile app setup screen (e.g., "Select default 3 or 4 sets for dumbbell accessory lifts", "Enter starting 1RM or working weight for Bench Press and Squat").
• Formulate clear, concise coaching cues and common mistakes to avoid for each exercise.

Strictly adhere to the `WorkoutProgram` JSON Schema.
"""


def extract_workout_program(
    transcript: str,
    caption: str,
    uploader: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> WorkoutProgram:
    """
    Extracts a fully hierarchical WorkoutProgram from transcript and caption
    using OpenAI reasoning models (o3-mini or gpt-4o).
    """
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    selected_model = model or os.getenv("OPENAI_MODEL", "o3-mini")

    user_content = f"""Analyze this Instagram Reel workout routine:

[Creator / Uploader]:
{uploader or 'Unknown'}

[Spoken Audio Transcription (Whisper)]:
{transcript.strip() if transcript else '(No audio transcript)'}

[Written Post Caption / Description]:
{caption.strip() if caption else '(No caption text)'}

Execute the 4-Stage Reasoning Process and return the complete hierarchical WorkoutProgram.
"""

    messages = [
        {"role": "developer" if selected_model.startswith("o") else "system", "content": SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    kwargs: Dict[str, Any] = {
        "model": selected_model,
        "messages": messages,
        "response_format": WorkoutProgram,
    }

    if not selected_model.startswith("o"):
        kwargs["temperature"] = 0.1

    try:
        completion = client.beta.chat.completions.parse(**kwargs)
        return completion.choices[0].message.parsed
    except Exception as primary_error:
        fallback_model = "gpt-4o" if selected_model != "gpt-4o" else "gpt-4o-mini"
        fallback_kwargs: Dict[str, Any] = {
            "model": fallback_model,
            "messages": [
                {"role": "system", "content": SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "response_format": WorkoutProgram,
            "temperature": 0.1,
        }
        try:
            completion = client.beta.chat.completions.parse(**fallback_kwargs)
            return completion.choices[0].message.parsed
        except Exception as fallback_error:
            raise RuntimeError(
                f"Failed with {selected_model} ({primary_error}) and fallback {fallback_model} ({fallback_error})"
            )
