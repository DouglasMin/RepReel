import os
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from pydantic import BaseModel, Field

from src.schema import WorkoutProgram, StructuredExercise


class ExerciseSubstituteItem(BaseModel):
    exercise_name: str = Field(description="Name of the substitute exercise in Korean & English")
    equipment: str = Field(description="Equipment required (Barbell, Dumbbell, Cable, Machine, Bodyweight)")
    target_muscle: str = Field(description="Primary muscle group and head targeted")
    rationale: str = Field(description="Biomechanical reason why this is an effective substitute")
    recommended_volume: str = Field(description="Recommended sets and reps scheme")


class ExerciseSubstituteResponse(BaseModel):
    original_exercise: str
    target_muscle: str
    substitutes: List[ExerciseSubstituteItem]


class NextSessionRecommendationItem(BaseModel):
    exercise_id: str
    exercise_name: str
    last_weight_kg: Optional[float] = None
    recommended_weight_kg: float = Field(description="Target working weight for the upcoming session")
    target_sets: int
    target_reps: str
    target_rpe: float
    progression_note: str = Field(description="Rationale for weight increase, maintenance, or rep progression")


class NextSessionRecommendationResponse(BaseModel):
    program_id: str
    day_number: int
    day_title: str
    overload_summary: str
    exercise_recommendations: List[NextSessionRecommendationItem]


class CoachQueryResponse(BaseModel):
    program_id: str
    question: str
    answer: str = Field(description="Actionable, certified strength & conditioning coach guidance")
    suggested_action_items: List[str]


class AICoachEngine:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
        self.api_key = os.getenv("OPENAI_API_KEY", "mock-key-for-tests")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def substitute_exercise(
        self,
        exercise_name: str,
        target_muscle: str,
        preferred_equipment: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Suggests 3 biomechanically matched alternative exercises.
        """
        equipment_filter = (
            f"Available equipment preferred: {', '.join(preferred_equipment)}"
            if preferred_equipment
            else "Any standard gym equipment."
        )

        prompt = f"""You are a Master Strength & Conditioning Coach and Kinesiology Specialist.
The user is at the gym and needs 3 immediate substitute exercises for:
- Original Exercise: {exercise_name}
- Target Muscle: {target_muscle}
- Constraints: {equipment_filter}

Provide 3 biomechanically accurate alternatives targeting the exact same muscle heads and movement plane.
Explain the rationale and recommended sets/reps in natural Korean."""

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are an elite strength & conditioning coach and biomechanist."},
                {"role": "user", "content": prompt},
            ],
            response_format=ExerciseSubstituteResponse,
        )
        return completion.choices[0].message.parsed.model_dump()

    def merge_programs(self, programs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merges multiple sub-programs (e.g. Day 1 Push Reel + Day 2 Pull Reel + Day 3 Legs Reel)
        into a single unified WorkoutProgram.
        """
        prompt = f"""You are a Head Strength & Conditioning Coach.
The user has imported multiple separate Instagram Reels workout routines that form a multi-part series (e.g. Push, Pull, Legs).
Merge these {len(programs)} routines into ONE unified, coherent WorkoutProgram.

Input Sub-Programs JSON:
{json.dumps(programs, ensure_ascii=False, indent=2)}

Rules for merging:
1. Renumber days logically (Day 1, Day 2, Day 3, ...).
2. Consolidate overlapping progression rules and frequency schedules.
3. Preserve all specific exercise details and volume prescriptions.
4. Set a unified clean title and overview."""

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a master strength coach orchestrating unified multi-day workout programs."},
                {"role": "user", "content": prompt},
            ],
            response_format=WorkoutProgram,
        )
        return completion.choices[0].message.parsed.model_dump()

    def calculate_next_session(
        self,
        program_data: Dict[str, Any],
        day_number: int,
        past_sessions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates recommended working weights and progressive overload targets based on workout history.
        """
        prompt = f"""You are an elite sports scientist specializing in Progressive Overload.
Given the target Workout Program Day {day_number} and the user's past workout logs:

Target Program Data:
{json.dumps(program_data, ensure_ascii=False, indent=2)}

User Past Logged Sessions:
{json.dumps(past_sessions, ensure_ascii=False, indent=2)}

Calculate specific working weight targets for each exercise in Day {day_number}.
If previous sessions showed RPE < 8 with max reps achieved, prescribe a +2.5kg to +5kg increase (or +1kg for dumbbells).
If RPE was 9-10 or rep targets were missed, maintain weight and prescribe target reps.
If no history exists, recommend starting weights based on standard intermediate lifter baseline."""

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a progressive overload algorithm and strength coach."},
                {"role": "user", "content": prompt},
            ],
            response_format=NextSessionRecommendationResponse,
        )
        return completion.choices[0].message.parsed.model_dump()

    def query_coach(
        self,
        program_data: Dict[str, Any],
        question: str,
    ) -> Dict[str, Any]:
        """
        Answers contextual fitness and form questions about an imported workout routine.
        """
        prompt = f"""You are the personal AI Strength Coach for this workout program:
{json.dumps(program_data, ensure_ascii=False, indent=2)}

User Question:
"{question}"

Provide a direct, concise, and highly actionable response in Korean (2-4 paragraphs max) with specific action items."""

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a world-class strength & conditioning coach assisting an athlete in real-time."},
                {"role": "user", "content": prompt},
            ],
            response_format=CoachQueryResponse,
        )
        return completion.choices[0].message.parsed.model_dump()
