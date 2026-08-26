from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SplitType(str, Enum):
    PPL = "PPL (Push/Pull/Legs)"
    UPPER_LOWER = "Upper/Lower (상체/하체)"
    BRO_SPLIT = "Bro Split (부위별 4-5분할)"
    FULL_BODY = "Full Body (무분할/전신)"
    CUSTOM = "Custom Routine"


class EquipmentType(str, Enum):
    BARBELL = "Barbell (바벨)"
    DUMBBELL = "Dumbbell (덤벨)"
    CABLE = "Cable (케이블)"
    MACHINE = "Machine (머신)"
    BODYWEIGHT = "Bodyweight (맨몸)"
    KETTLEBELL = "Kettlebell (케틀벨)"
    OTHER = "Other (기타)"


class GroupCategory(str, Enum):
    MAIN_COMPOUND = "Main Compound (메인 복합 다관절 운동)"
    ACCESSORY = "Accessory (보조 복합/단일 운동)"
    ISOLATION = "Isolation (고립/레이즈 운동)"
    CORE_FINISHER = "Core / Finisher (코어 및 마무리 운동)"


class RepType(str, Enum):
    REPS_RANGE = "Reps Range (반복 횟수 범위)"
    FIXED_REPS = "Fixed Reps (고정 횟수)"
    TO_FAILURE = "To Failure (실패 지점까지)"
    TIMED_SECONDS = "Timed Seconds (시간/초 단위)"


class PrescribedVolume(BaseModel):
    min_sets: int = Field(
        description="Minimum number of prescribed sets (e.g., 3, 5)."
    )
    max_sets: int = Field(
        description="Maximum number of prescribed sets (e.g., 4, 5)."
    )
    min_reps: int = Field(
        description="Minimum repetition target per set (e.g., 8, 15)."
    )
    max_reps: Optional[int] = Field(
        default=None,
        description="Maximum repetition target per set (e.g., 12, 20). Null if open-ended or to failure."
    )
    rep_type: RepType = Field(
        default=RepType.REPS_RANGE,
        description="Type of repetition prescription."
    )
    rest_seconds: Optional[int] = Field(
        default=None,
        description="Prescribed rest time in seconds between sets if specified (e.g. 60, 90, 120)."
    )
    weight_guidance: Optional[str] = Field(
        default=None,
        description="Load or intensity guidance (e.g., 'RPE 8', '점진적 과부하', '가벼운 무게로 고반복')."
    )
    rpe_target: Optional[float] = Field(
        default=None,
        description="Target Rate of Perceived Exertion (RPE 1-10) if mentioned."
    )


class CoachingGuide(BaseModel):
    form_cues: List[str] = Field(
        default_factory=list,
        description="Step-by-step biomechanical execution cues and posture directions."
    )
    common_mistakes_to_avoid: List[str] = Field(
        default_factory=list,
        description="Common mistakes and injury prevention warnings for this exercise."
    )
    tempo_notes: Optional[str] = Field(
        default=None,
        description="Cadence/tempo notes (e.g., '신장성 수축 2초, 폭발적 수축 1초')."
    )


class StructuredExercise(BaseModel):
    exercise_id: str = Field(
        description="Clean snake_case identifier for database keys (e.g., 'bench_press', 'side_lateral_raise')."
    )
    canonical_name_ko: str = Field(
        description="Standardized Korean exercise name with decoded slang (e.g., '사이드 레터럴 레이즈')."
    )
    canonical_name_en: str = Field(
        description="Standardized English exercise name (e.g., 'Side Lateral Raise')."
    )
    equipment: EquipmentType = Field(
        description="Required equipment type."
    )
    primary_muscle: str = Field(
        description="Primary target muscle (e.g., '대흉근 (가슴)', '측면 삼각근 (어깨)', '광배근 (등)', '대퇴사두근 (하체)')."
    )
    secondary_muscles: List[str] = Field(
        default_factory=list,
        description="Secondary synergist muscles involved (e.g., ['삼두근', '전면 삼각근'])."
    )
    is_main_lift: bool = Field(
        default=False,
        description="True if this is the focal/main heavy lift of the workout session."
    )
    volume: PrescribedVolume = Field(
        description="Detailed prescribed sets, reps, and load volume."
    )
    guide: CoachingGuide = Field(
        description="Coaching instructions and form cues."
    )


class ExerciseGroup(BaseModel):
    category: GroupCategory = Field(
        description="Category of exercise grouping within the workout session."
    )
    target_region: Optional[str] = Field(
        default=None,
        description="Specific anatomical focus for this group (e.g., '가슴 (Chest)', '삼두 (Triceps)', '어깨 (Shoulders)')."
    )
    exercises: List[StructuredExercise] = Field(
        description="Sequential list of exercises inside this group."
    )


class WorkoutDay(BaseModel):
    day_number: int = Field(
        description="Sequential day number in the cycle (1, 2, 3, etc.)."
    )
    day_title: str = Field(
        description="Title of the day session (e.g., 'Day 1: 푸쉬 (Push - 가슴 / 삼두 / 어깨)')."
    )
    day_focus: str = Field(
        description="Primary focus or movement pattern for the day (e.g., '상체 밀기 (Push Pattern)')."
    )
    target_muscle_groups: List[str] = Field(
        description="List of target muscle groups trained on this day."
    )
    exercise_groups: List[ExerciseGroup] = Field(
        description="Grouped exercises for the day (Main Compound -> Accessories -> Isolations -> Core)."
    )


class ProgressionRule(BaseModel):
    overload_strategy: str = Field(
        description="Overload and progression principles (e.g., '매주 중량 또는 횟수 점진적 증가')."
    )
    frequency_schedule: str = Field(
        description="Weekly frequency & split cycle (e.g., '6일 운동 + 1일 휴식 2사이클')."
    )
    recovery_guidance: Optional[str] = Field(
        default=None,
        description="Rest day notes or deload suggestions."
    )


class DataQualityAudit(BaseModel):
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence score (0.0 to 1.0)."
    )
    sets_ambiguous: bool = Field(
        default=False,
        description="True if any exercise sets were prescribed as a range requiring user selection."
    )
    weight_missing: bool = Field(
        default=False,
        description="True if starting weight/load was not explicitly specified."
    )
    rest_missing: bool = Field(
        default=False,
        description="True if rest intervals between sets were omitted."
    )
    user_action_items: List[str] = Field(
        default_factory=list,
        description="List of specific setup actions the user must confirm in the mobile app UI."
    )
    audit_notes: str = Field(
        description="Detailed summary of data quality, assumptions made, and completeness."
    )


class WorkoutProgram(BaseModel):
    program_id: str = Field(
        description="Unique identifier for the workout program (e.g., 'che-dan-sil-ppl-routine-part2')."
    )
    title: str = Field(
        description="Official title of the workout routine (e.g., '체단실 3분할 루틴 2탄 (푸쉬 / 풀 / 하체)')."
    )
    split_type: SplitType = Field(
        description="High-level split classification."
    )
    overview: str = Field(
        description="Comprehensive summary of the program goals and methodology."
    )
    cycle_frequency: str = Field(
        description="Cycle frequency summary (e.g., '6일 운동 1일 휴식')."
    )
    days: List[WorkoutDay] = Field(
        description="Sequential list of workout days composing the full cycle."
    )
    progression: ProgressionRule = Field(
        description="Progression and overload rules for tracking long-term gains."
    )
    audit: DataQualityAudit = Field(
        description="Quality audit and verification report for the mobile client."
    )
