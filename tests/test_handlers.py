import json
import pytest
import os
from unittest.mock import MagicMock, patch
from decimal import Decimal

from src.schema import (
    WorkoutProgram,
    WorkoutDay,
    ExerciseGroup,
    StructuredExercise,
    PrescribedVolume,
    CoachingGuide,
    SplitType,
    EquipmentType,
    GroupCategory,
    RepType,
    ProgressionRule,
    DataQualityAudit,
)
from src.db.client import float_to_decimal, decimal_to_python
from src.handlers import ingest, jobs, programs, sessions, exercises
from src.auth.guard import verify_request_authorization


def test_dynamodb_float_conversion():
    sample_data = {
        "confidence_score": 0.95,
        "sets": [3, 4, 5],
        "nested": {"rpe": 8.5, "name": "Bench Press"},
    }
    converted = float_to_decimal(sample_data)
    assert isinstance(converted["confidence_score"], Decimal)
    assert isinstance(converted["nested"]["rpe"], Decimal)

    restored = decimal_to_python(converted)
    assert restored["confidence_score"] == 0.95
    assert restored["nested"]["rpe"] == 8.5


def test_db_session_crud_operations():
    from src.db.client import DynamoDBClient
    client = DynamoDBClient(table_name="test-table")
    mock_table = MagicMock()
    client.table = mock_table

    # Test get_workout_session
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "USER#me@example.com",
            "SK": "SESSION#session_123",
            "session_id": "session_123",
            "program_id": "prog_123",
            "day_number": 1,
            "duration_seconds": 3600,
        }
    }
    session = client.get_workout_session("me@example.com", "session_123")
    assert session is not None
    assert session["session_id"] == "session_123"

    # Test delete_workout_session (exists)
    mock_table.get_item.return_value = {"Item": {"PK": "USER#me@example.com", "SK": "SESSION#session_123"}}
    assert client.delete_workout_session("me@example.com", "session_123") is True
    mock_table.delete_item.assert_called_once_with(Key={"PK": "USER#me@example.com", "SK": "SESSION#session_123"})

    # Test delete_workout_session (not found)
    mock_table.get_item.return_value = {}
    assert client.delete_workout_session("me@example.com", "session_nonexistent") is False

    # Test update_workout_session
    mock_table.get_item.return_value = {
        "Item": {
            "PK": "USER#me@example.com",
            "SK": "SESSION#session_123",
            "session_id": "session_123",
            "program_id": "prog_123",
            "day_number": 1,
        }
    }
    updated = client.update_workout_session(
        user_id="me@example.com",
        session_id="session_123",
        session_data={
            "program_id": "prog_123",
            "day_number": 1,
            "duration_seconds": 4000,
            "completed_exercises": [
                {
                    "exercise_id": "bench_press",
                    "exercise_name": "Bench Press",
                    "sets": [{"set_number": 1, "weight_kg": 100.0, "reps": 5, "completed": True}],
                }
            ],
        },
    )
    assert updated is not None
    assert updated["duration_seconds"] == 4000
    assert updated["volume_analytics"]["total_volume_kg"] == 500.0
    mock_table.update_item.assert_called_once()


def test_schema_instantiation():
    program = WorkoutProgram(
        program_id="test-program-1",
        title="Test Push Routine",
        split_type=SplitType.PPL,
        overview="Test overview",
        cycle_frequency="6 days on, 1 day off",
        days=[
            WorkoutDay(
                day_number=1,
                day_title="Day 1: Push",
                day_focus="Chest & Triceps",
                target_muscle_groups=["Chest", "Triceps"],
                exercise_groups=[
                    ExerciseGroup(
                        category=GroupCategory.MAIN_COMPOUND,
                        target_region="Chest",
                        exercises=[
                            StructuredExercise(
                                exercise_id="bench_press",
                                canonical_name_ko="벤치프레스",
                                canonical_name_en="Bench Press",
                                equipment=EquipmentType.BARBELL,
                                primary_muscle="Chest",
                                is_main_lift=True,
                                volume=PrescribedVolume(
                                    min_sets=5,
                                    max_sets=5,
                                    min_reps=8,
                                    max_reps=12,
                                    rep_type=RepType.REPS_RANGE,
                                ),
                                guide=CoachingGuide(
                                    form_cues=["Keep shoulder blades retracted"],
                                    common_mistakes_to_avoid=["Do not flare elbows"],
                                ),
                            )
                        ],
                    )
                ],
            )
        ],
        progression=ProgressionRule(
            overload_strategy="Add 2.5kg each week",
            frequency_schedule="Twice per week",
        ),
        audit=DataQualityAudit(
            confidence_score=0.98,
            sets_ambiguous=False,
            weight_missing=True,
            rest_missing=True,
            user_action_items=["Enter working weight"],
            audit_notes="Test audit",
        ),
    )

    program_dict = program.model_dump()
    assert program_dict["program_id"] == "test-program-1"
    assert program_dict["days"][0]["exercise_groups"][0]["exercises"][0]["canonical_name_ko"] == "벤치프레스"


def test_auth_guard_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_EMAILS", "me@domain.com,dongik@example.com")
    monkeypatch.setenv("APP_SECRET_KEY", "super-secret-token")

    # Unauthorized email
    is_auth, err = verify_request_authorization({
        "x-app-secret": "super-secret-token",
        "x-user-email": "stranger@unknown.com"
    })
    assert is_auth is False

    # Invalid secret
    is_auth, err = verify_request_authorization({
        "x-app-secret": "wrong-token",
        "x-user-email": "me@domain.com"
    })
    assert is_auth is False

    # Authorized
    is_auth, err = verify_request_authorization({
        "x-app-secret": "super-secret-token",
        "x-user-email": "me@domain.com"
    })
    assert is_auth is True


@patch("src.handlers.ingest.db.create_job")
@patch("src.handlers.ingest.sqs.send_message")
def test_ingest_handler_success(mock_sqs, mock_create_job):
    mock_create_job.return_value = {"job_id": "job_123", "status": "PROCESSING"}
    mock_sqs.return_value = {"MessageId": "msg_123"}

    event = {
        "headers": {},
        "body": json.dumps({"url": "https://www.instagram.com/reel/DccqEKJPPqR/"})
    }

    response = ingest.handler(event, None)
    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["status"] == "PROCESSING"
    assert body["reel_id"] == "DccqEKJPPqR"
    assert "job_id" in body


def test_ingest_handler_unauthorized(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "my-secret-key")
    event = {
        "headers": {"x-app-secret": "invalid-key"},
        "body": json.dumps({"url": "https://www.instagram.com/reel/DccqEKJPPqR/"})
    }
    response = ingest.handler(event, None)
    assert response["statusCode"] == 403


def test_ingest_handler_invalid_url():
    event = {
        "headers": {},
        "body": json.dumps({"url": "https://invalid-url.com/post/123"})
    }
    response = ingest.handler(event, None)
    assert response["statusCode"] == 400


@patch("src.handlers.jobs.db.get_job")
def test_get_job_handler(mock_get_job):
    mock_get_job.return_value = {
        "job_id": "job_abc",
        "status": "COMPLETED",
        "program_id": "chedansil-part2",
    }
    event = {"pathParameters": {"job_id": "job_abc"}}
    response = jobs.get_status(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["status"] == "COMPLETED"


@patch("src.handlers.programs.db.get_workout_program")
def test_get_program_handler(mock_get_program):
    mock_get_program.return_value = {
        "program_id": "prog_123",
        "title": "Sample Workout",
    }
    event = {"pathParameters": {"program_id": "prog_123"}}
    response = programs.get_by_id(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["program_id"] == "prog_123"


@patch("src.handlers.programs.db.update_workout_program")
def test_update_program_handler(mock_update):
    mock_update.return_value = {"program_id": "prog_123", "title": "Updated Title"}
    event = {
        "pathParameters": {"program_id": "prog_123"},
        "body": json.dumps({"title": "Updated Title"}),
    }
    response = programs.update_program(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True


@patch("src.handlers.programs.db.delete_workout_program")
def test_delete_program_handler(mock_delete):
    mock_delete.return_value = True
    event = {"pathParameters": {"program_id": "prog_123"}}
    response = programs.delete_by_id(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True


@patch("src.handlers.programs.coach.merge_programs")
@patch("src.handlers.programs.db.save_workout_program")
@patch("src.handlers.programs.db.get_workout_program")
def test_merge_programs_handler(mock_get_prog, mock_save_prog, mock_merge_coach):
    mock_get_prog.return_value = {
        "program_id": "prog_1",
        "creator": "Coach",
        "program_data": {"title": "Part 1"},
    }
    mock_merge_coach.return_value = {"title": "Merged Routine", "days": []}
    mock_save_prog.return_value = {"program_id": "merged_123", "title": "Merged Routine"}

    event = {"body": json.dumps({"program_ids": ["prog_1", "prog_2"]})}
    response = programs.merge_programs(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["success"] is True


@patch("src.handlers.programs.coach.calculate_next_session")
@patch("src.handlers.programs.db.list_workout_sessions")
@patch("src.handlers.programs.db.get_workout_program")
def test_get_next_session_handler(mock_get_prog, mock_list_sess, mock_calc):
    mock_get_prog.return_value = {"program_id": "prog_1", "program_data": {}}
    mock_list_sess.return_value = []
    mock_calc.return_value = {
        "program_id": "prog_1",
        "day_number": 1,
        "overload_summary": "+2.5kg",
        "exercise_recommendations": [],
    }

    event = {
        "pathParameters": {"program_id": "prog_1"},
        "queryStringParameters": {"day_number": "1"},
    }
    response = programs.get_next_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["overload_summary"] == "+2.5kg"


@patch("src.handlers.programs.coach.query_coach")
@patch("src.handlers.programs.db.get_workout_program")
def test_coach_query_handler(mock_get_prog, mock_query):
    mock_get_prog.return_value = {"program_id": "prog_1", "program_data": {}}
    mock_query.return_value = {
        "program_id": "prog_1",
        "question": "Warm up tips?",
        "answer": "Do 2 sets of rotator cuff warmups.",
        "suggested_action_items": [],
    }

    event = {
        "pathParameters": {"program_id": "prog_1"},
        "body": json.dumps({"question": "Warm up tips?"}),
    }
    response = programs.coach_query(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert "rotator cuff" in body["answer"]


@patch("src.handlers.exercises.coach.substitute_exercise")
def test_substitute_exercise_handler(mock_sub):
    mock_sub.return_value = {
        "original_exercise": "Incline Hammer Press",
        "target_muscle": "Upper Chest",
        "substitutes": [
            {
                "exercise_name": "Incline DB Press",
                "equipment": "Dumbbell",
                "target_muscle": "Upper Chest",
                "rationale": "Same angle",
                "recommended_volume": "3-4x8-12",
            }
        ],
    }

    event = {
        "body": json.dumps({
            "exercise_name": "Incline Hammer Press",
            "target_muscle": "Upper Chest",
            "preferred_equipment": ["Dumbbell"],
        })
    }
    response = exercises.substitute_exercise(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert len(body["substitutes"]) == 1


@patch("src.handlers.sessions.db.log_workout_session")
def test_create_session_handler(mock_log):
    mock_log.return_value = {"session_id": "session_123", "program_id": "prog_123"}
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "body": json.dumps({"program_id": "prog_123", "day_number": 1, "exercises": []}),
    }
    response = sessions.create_session(event, None)
    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["session_id"].startswith("session_")


@patch("src.handlers.sessions.db.list_workout_sessions")
def test_list_sessions_handler(mock_list):
    mock_list.return_value = [{"session_id": "session_123"}]
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "queryStringParameters": {"program_id": "prog_123"},
    }
    response = sessions.list_sessions(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["count"] == 1


@patch("src.handlers.sessions.db.save_active_session")
def test_save_active_session_handler(mock_save):
    mock_save.return_value = {"user_id": "me@example.com", "program_id": "prog_123"}
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "body": json.dumps({"program_id": "prog_123", "completed_exercises": []}),
    }
    response = sessions.save_active_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True


@patch("src.handlers.sessions.db.get_active_session")
def test_get_active_session_handler(mock_get):
    mock_get.return_value = {"user_id": "me@example.com", "program_id": "prog_123"}
    event = {"headers": {"x-user-email": "me@example.com"}}
    response = sessions.get_active_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["has_active_session"] is True


@patch("src.handlers.sessions.db.delete_active_session")
def test_delete_active_session_handler(mock_del):
    mock_del.return_value = True
    event = {"headers": {"x-user-email": "me@example.com"}}
    response = sessions.delete_active_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True


@patch("src.handlers.sessions.db.delete_workout_session")
def test_delete_session_handler_success(mock_delete):
    mock_delete.return_value = True
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {"session_id": "session_123"},
    }
    response = sessions.delete_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["message"] == "Session deleted successfully"


@patch("src.handlers.sessions.db.delete_workout_session")
def test_delete_session_handler_not_found(mock_delete):
    mock_delete.return_value = False
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {"session_id": "session_nonexistent"},
    }
    response = sessions.delete_session(event, None)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert body["error"] == "Not Found"


def test_delete_session_handler_missing_id():
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {},
    }
    response = sessions.delete_session(event, None)
    assert response["statusCode"] == 400


@patch("src.handlers.sessions.db.update_workout_session")
def test_update_session_handler_success(mock_update):
    mock_update.return_value = {
        "session_id": "session_123",
        "program_id": "prog_123",
        "volume_analytics": {"total_volume_kg": 800.0},
    }
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {"session_id": "session_123"},
        "body": json.dumps({
            "program_id": "prog_123",
            "completed_exercises": [
                {
                    "exercise_id": "bench",
                    "sets": [{"weight_kg": 80.0, "reps": 10, "completed": True}],
                }
            ],
        }),
    }
    response = sessions.update_session(event, None)
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["session_id"] == "session_123"
    assert body["session"]["volume_analytics"]["total_volume_kg"] == 800.0


@patch("src.handlers.sessions.db.update_workout_session")
def test_update_session_handler_not_found(mock_update):
    mock_update.return_value = None
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {"session_id": "session_nonexistent"},
        "body": json.dumps({"program_id": "prog_123"}),
    }
    response = sessions.update_session(event, None)
    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert body["error"] == "Not Found"


def test_update_session_handler_missing_id():
    event = {
        "headers": {"x-user-email": "me@example.com"},
        "pathParameters": {},
        "body": json.dumps({"program_id": "prog_123"}),
    }
    response = sessions.update_session(event, None)
    assert response["statusCode"] == 400


def test_volume_analytics_calculation():
    from src.db.client import calculate_session_volume_analytics
    sample_session = {
        "completed_exercises": [
            {
                "exercise_id": "bench_press",
                "exercise_name": "Bench Press",
                "sets": [
                    {"set_number": 1, "weight_kg": 80.0, "reps": 10, "completed": True},
                    {"set_number": 2, "weight_kg": 85.0, "reps": 8, "completed": True},
                    {"set_number": 3, "weight_kg": 90.0, "reps": 6, "completed": False}, # Unchecked
                ]
            }
        ]
    }
    analytics = calculate_session_volume_analytics(sample_session)
    # Set 1: 80 * 10 = 800
    # Set 2: 85 * 8 = 680
    # Total = 1480.0 kg
    assert analytics["total_volume_kg"] == 1480.0
    assert analytics["total_sets_completed"] == 2
    assert analytics["total_reps_completed"] == 18
    assert analytics["exercise_breakdown"][0]["estimated_1rm_kg"] > 85.0


def test_should_use_vision_pipeline_text_rich():
    from src.extractor import should_use_vision_pipeline
    transcript = "오늘 가슴 루틴입니다. 1번 인클라인 벤치프레스 4세트 10회, 2번 덤벨 플라이 3세트 12회 진행합니다."
    caption = "가슴 폭발 루틴"
    assert should_use_vision_pipeline(transcript, caption) is False


def test_should_use_vision_pipeline_silent_or_music():
    from src.extractor import should_use_vision_pipeline
    # Silent / only music lyrics
    transcript = "[음악] baby one more time ♪"
    caption = "#오운완 #헬스타그램"
    assert should_use_vision_pipeline(transcript, caption) is True


def test_should_use_vision_pipeline_caption_fallback():
    from src.extractor import should_use_vision_pipeline
    transcript = "" # No voiceover
    caption = "오늘의 하체 루틴: 1. 스쿼트 5세트 8회, 2. 레그프레스 4세트 12회, 3. 레그익스텐션 3세트 15회"
    assert should_use_vision_pipeline(transcript, caption) is False


def test_extract_video_id_instagram():
    from src.downloader import extract_reel_id
    assert extract_reel_id("https://www.instagram.com/reel/DccqEKJPPqR/") == "DccqEKJPPqR"
    assert extract_reel_id("https://instagram.com/p/DccqEKJPPqR") == "DccqEKJPPqR"
    assert extract_reel_id("https://instagr.am/reels/DccqEKJPPqR/?igsh=abc") == "DccqEKJPPqR"


def test_extract_video_id_youtube():
    from src.downloader import extract_reel_id, extract_video_id
    assert extract_reel_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_reel_id("https://youtube.com/shorts/dQw4w9WgXcQ?feature=share") == "dQw4w9WgXcQ"
    assert extract_reel_id("https://youtu.be/dQw4w9WgXcQ?si=123xyz") == "dQw4w9WgXcQ"
    assert extract_reel_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_reel_id("https://m.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_is_supported_video_url():
    from src.downloader import is_supported_video_url
    assert is_supported_video_url("https://www.instagram.com/reel/DccqEKJPPqR/") is True
    assert is_supported_video_url("https://youtube.com/shorts/dQw4w9WgXcQ") is True
    assert is_supported_video_url("https://youtu.be/dQw4w9WgXcQ") is True
    assert is_supported_video_url("https://m.youtube.com/shorts/dQw4w9WgXcQ") is True
    assert is_supported_video_url("https://tiktok.com/@user/video/123") is False
    assert is_supported_video_url("https://random-site.com/video") is False
    assert is_supported_video_url("") is False
    assert is_supported_video_url(None) is False


@patch("src.handlers.ingest.db.create_job")
@patch("src.handlers.ingest.sqs.send_message")
def test_ingest_handler_youtube_shorts_success(mock_sqs, mock_create_job):
    mock_create_job.return_value = {"job_id": "job_yt_123", "status": "PROCESSING"}
    mock_sqs.return_value = {"MessageId": "msg_yt_123"}

    event = {
        "headers": {},
        "body": json.dumps({"url": "https://youtube.com/shorts/dQw4w9WgXcQ?feature=share"}),
    }

    response = ingest.handler(event, None)
    assert response["statusCode"] == 202
    body = json.loads(response["body"])
    assert body["success"] is True
    assert body["status"] == "PROCESSING"
    assert body["reel_id"] == "dQw4w9WgXcQ"
    assert body["job_id"].startswith("job_")


@patch("requests.get")
def test_fetch_oembed_caption_youtube(mock_requests_get):
    from src.downloader import fetch_oembed_caption
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "Full Body Dumbbell Workout",
        "author_name": "FitnessCoach",
    }
    mock_requests_get.return_value = mock_response

    oembed = fetch_oembed_caption("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert oembed is not None
    assert oembed["title"] == "Full Body Dumbbell Workout"
    assert oembed["author_name"] == "FitnessCoach"

