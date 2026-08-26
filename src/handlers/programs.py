import json
import uuid
from typing import Dict, Any, List
from src.db.client import DynamoDBClient
from src.ai_coach import AICoachEngine
from src.auth.guard import verify_request_authorization

db = DynamoDBClient()
coach = AICoachEngine()


def get_by_id(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /programs/{program_id}
    Returns complete hierarchical WorkoutProgram JSON.
    """
    path_parameters = event.get("pathParameters") or {}
    program_id = path_parameters.get("program_id")

    if not program_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing program_id path parameter"}),
        }

    program_item = db.get_workout_program(program_id)

    if not program_item:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Workout program '{program_id}' not found"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(program_item),
    }


def list_programs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /programs
    Query parameters:
      ?creator=<creator_name>&limit=<20>
    """
    query_params = event.get("queryStringParameters") or {}
    creator = query_params.get("creator")
    limit = int(query_params.get("limit", 20))

    if creator:
        programs = db.list_programs_by_creator(creator=creator, limit=limit)
    else:
        # Default empty list if no creator provided
        programs = []

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"count": len(programs), "programs": programs}),
    }


def update_program(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    PUT /programs/{program_id}
    Saves user edits, confirmed sets/weights, or customized form cues.
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    path_parameters = event.get("pathParameters") or {}
    program_id = path_parameters.get("program_id")

    if not program_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing program_id path parameter"}),
        }

    try:
        body = json.loads(event.get("body") or "{}")
        updated = db.update_workout_program(program_id=program_id, program_dict=body)

        if not updated:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": f"Program '{program_id}' not found"}),
            }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": True, "program": updated}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


def delete_by_id(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    DELETE /programs/{program_id}
    Deletes a workout program from DynamoDB.
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    path_parameters = event.get("pathParameters") or {}
    program_id = path_parameters.get("program_id")

    if not program_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing program_id path parameter"}),
        }

    deleted = db.delete_workout_program(program_id)
    if not deleted:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Program '{program_id}' not found"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"success": True, "message": f"Program '{program_id}' deleted successfully."}),
    }


def merge_programs(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /programs/merge
    Body: { "program_ids": ["id1", "id2", "id3"], "title": "Optional merged title" }
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    try:
        body = json.loads(event.get("body") or "{}")
        program_ids = body.get("program_ids", [])

        if not program_ids or len(program_ids) < 2:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "At least 2 'program_ids' are required for merging."}),
            }

        programs_data: List[Dict[str, Any]] = []
        creator = "Combined Series"
        for pid in program_ids:
            prog_item = db.get_workout_program(pid)
            if prog_item and "program_data" in prog_item:
                programs_data.append(prog_item["program_data"])
                creator = prog_item.get("creator", creator)

        if len(programs_data) < 2:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Could not find sufficient programs to merge."}),
            }

        merged_program = coach.merge_programs(programs_data)
        if body.get("title"):
            merged_program["title"] = body["title"]

        merged_id = f"merged_{uuid.uuid4().hex[:10]}"
        merged_program["program_id"] = merged_id

        # Save merged program to DynamoDB
        saved_item = db.save_workout_program(
            program_dict=merged_program,
            reel_id="merged_series",
            uploader=creator,
        )

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": True, "merged_program_id": merged_id, "program": saved_item}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


def get_next_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /programs/{program_id}/next-session?day_number=1
    Calculates AI progressive overload recommendations and target weights for upcoming workout.
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    path_parameters = event.get("pathParameters") or {}
    program_id = path_parameters.get("program_id")
    query_params = event.get("queryStringParameters") or {}
    day_number = int(query_params.get("day_number", 1))

    user_id = headers.get("x-user-email") or headers.get("x-user-id") or "default_user"

    program_item = db.get_workout_program(program_id)
    if not program_item or "program_data" not in program_item:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Program '{program_id}' not found"}),
        }

    past_sessions = db.list_workout_sessions(user_id=user_id, program_id=program_id, limit=5)

    try:
        recommendations = coach.calculate_next_session(
            program_data=program_item["program_data"],
            day_number=day_number,
            past_sessions=past_sessions,
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": True, **recommendations}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


def coach_query(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /programs/{program_id}/coach-query
    Body: { "question": "I have slight shoulder pain, what should I modify in Day 1?" }
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    path_parameters = event.get("pathParameters") or {}
    program_id = path_parameters.get("program_id")

    program_item = db.get_workout_program(program_id)
    if not program_item or "program_data" not in program_item:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Program '{program_id}' not found"}),
        }

    try:
        body = json.loads(event.get("body") or "{}")
        question = body.get("question")
        if not question:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required field 'question'"}),
            }

        advice = coach.query_coach(
            program_data=program_item["program_data"],
            question=question,
        )
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": True, **advice}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
