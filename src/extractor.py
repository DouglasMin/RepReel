import os
import re
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from openai import OpenAI
from src.schema import WorkoutProgram

SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT = """You are an elite Strength & Conditioning Software Architect and Kinesiology Specialist.
Your goal is to parse raw short-form workout video content (Instagram Reels, YouTube Shorts: audio transcription from speech, written post caption, and/or on-screen video frames) into a deeply structured, hierarchical, database-ready `WorkoutProgram`.

Follow this systematic 4-Stage Reasoning Process:

─────────────────────────────────────────────────────────────
STAGE 1: ENTITY NORMALIZATION & SLANG RESOLUTION
─────────────────────────────────────────────────────────────
• Decode all Korean gym abbreviations, on-screen text overlays, and slang into standardized bilingual names:
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
• Identify the high-level split (e.g., PPL, Upper/Lower, Full Body, Bro Split).
• Divide the program into sequential `WorkoutDay` units (Day 1, Day 2, Day 3, etc.).
• Within each day, organize exercises into logical `ExerciseGroup` categories:
  - `MAIN_COMPOUND`: Primary heavy compound strength lifts (e.g., Bench Press, Pull-Up, Squat).
  - `ACCESSORY`: Secondary compound or targeted accessory movements.
  - `ISOLATION`: Single-joint isolation or raise movements (e.g., lateral raises, curls, extensions).
  - `CORE_FINISHER`: Core stabilization and abdominal movements (e.g., hanging leg raises).

─────────────────────────────────────────────────────────────
STAGE 3: VOLUME SOLVER & RULE PROPAGATION
─────────────────────────────────────────────────────────────
• Propagate stated or visible volume rules across the tree:
  - Main compound movements: sets: min_sets=5, max_sets=5, reps: min_reps=8, max_reps=12, is_main_lift=True.
  - Accessory movements: sets: min_sets=3, max_sets=4, reps: min_reps=8, max_reps=12, is_main_lift=False.
  - Isolation/Raise movements (e.g. Lateral Raises): sets: min_sets=3, max_sets=4, reps: min_reps=15, max_reps=20, rep_type: REPS_RANGE.
• If sets or reps are given as a range (e.g. 3-4 sets), set `min_sets=3`, `max_sets=4` and mark `sets_ambiguous=True` in DataQualityAudit.

─────────────────────────────────────────────────────────────
STAGE 4: QUALITY AUDIT & MOBILE ACTION ITEM GENERATION
─────────────────────────────────────────────────────────────
• Detect missing variables needed for a mobile workout log (starting weights, rest intervals, set confirmations).
• Generate concrete `user_action_items` for the mobile app setup screen.
• Formulate clear, concise coaching cues and common mistakes to avoid for each exercise.

Strictly adhere to the `WorkoutProgram` JSON Schema.
"""


def should_use_vision_pipeline(transcript: str, caption: str) -> bool:
    """
    Evaluates fitness information density in audio transcript and caption to determine
    whether the Vision pipeline (FFmpeg keyframes) should be activated.
    Returns:
      True  -> Activate Vision Keyframe Extractor (for silent, music-only, or text-overlay reels)
      False -> Fast & Cheap Text-Only Path
    """
    combined_text = f"{transcript or ''}\n{caption or ''}".strip()

    # 1. If text is extremely short (< 30 characters), audio is empty or absent
    if len(combined_text) < 30:
        return True

    # 2. Clean music / subtitle noise artifacts (e.g. [음악], ♪, repetitive hallucinations)
    clean_text = re.sub(r"\[.*?\]|♪|♫", "", combined_text).strip()

    # 3. Comprehensive fitness keywords (Korean & English)
    EXERCISE_KEYWORDS = [
        "스쿼트", "데드리프트", "벤치프레스", "벤치", "인클라인", "프레스", "숄더프레스", "체스트프레스", "밀프",
        "랫풀다운", "랫풀", "바벨로우", "덤벨로우", "시티드로우", "로우", "풀업", "턱걸이", "친업", "딥스", "푸쉬업",
        "사이드레터럴", "사레레", "프론트레이즈", "리어델트", "페이스풀", "슈러그", "레이즈",
        "바벨컬", "덤벨컬", "해머컬", "트라이셉스", "푸시다운", "익스텐션", "컬", "플라이", "펙덱",
        "레그프레스", "레그익스텐션", "레그컬", "런지", "카프레이즈", "힙쓰러스트", "불스스", "루데",
        "squat", "deadlift", "bench", "press", "row", "pulldown", "raise", "curl", "lunge", "fly", "dip",
    ]

    lower_text = clean_text.lower()
    exercise_matches = sum(1 for kw in EXERCISE_KEYWORDS if kw in lower_text)

    # 4. Volume / Rep pattern matching (e.g. "4세트", "10회", "8-12회", "3x10", "80kg")
    VOLUME_PATTERN = r"(\d+\s*(?:세트|set|회|rep|개|kg|킬로|x\s*\d+))"
    volume_matches = len(re.findall(VOLUME_PATTERN, clean_text, re.IGNORECASE))

    # High-information condition: at least 2 distinct exercise terms AND at least 2 set/rep indicators
    has_sufficient_workout_info = (exercise_matches >= 2 and volume_matches >= 2)

    return not has_sufficient_workout_info


def encode_image_to_base64(image_path: str) -> Optional[str]:
    """Reads a local image file and converts it to a base64 Data URL."""
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded_string}"
    except Exception:
        return None


def extract_workout_program(
    transcript: str,
    caption: str,
    uploader: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> WorkoutProgram:
    """
    Extracts a fully hierarchical WorkoutProgram from transcript, caption, and optional video frames
    using OpenAI reasoning/multimodal models (GPT-5.4 mini / GPT-4o).
    """
    client = OpenAI(api_key=api_key) if api_key else OpenAI()
    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    text_prompt = f"""Analyze this workout routine video (Instagram Reel / YouTube Shorts):

[Creator / Uploader]:
{uploader or 'Unknown'}

[Spoken Audio Transcription (Whisper)]:
{transcript.strip() if transcript else '(No audio transcript)'}

[Written Post Caption / Description]:
{caption.strip() if caption else '(No caption text)'}

Instructions:
1. If on-screen video frames are attached, carefully read all exercise names, sets, reps, cards, and movement form cues shown in the frames.
2. Cross-reference audio, caption, and video frames to build the complete workout split.
3. Execute the 4-Stage Reasoning Process and return the complete hierarchical WorkoutProgram.
"""

    if image_paths and len(image_paths) > 0:
        # Multimodal Vision Payload
        user_content_blocks: List[Dict[str, Any]] = [
            {"type": "text", "text": text_prompt}
        ]
        for img_path in image_paths:
            base64_url = encode_image_to_base64(img_path)
            if base64_url:
                user_content_blocks.append({
                    "type": "image_url",
                    "image_url": {
                        "url": base64_url,
                        "detail": "low",  # Optimal 85-token cost efficiency
                    },
                })
        messages = [
            {"role": "system", "content": SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content_blocks},
        ]
    else:
        # Fast & Cheap Text-Only Payload
        messages = [
            {"role": "developer" if selected_model.startswith("o") else "system", "content": SEQUENTIAL_MULTI_ROLE_SYSTEM_PROMPT},
            {"role": "user", "content": text_prompt},
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
                {"role": "user", "content": text_prompt},
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
