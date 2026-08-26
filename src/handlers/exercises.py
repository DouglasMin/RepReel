import json
from typing import Dict, Any
from src.ai_coach import AICoachEngine
from src.auth.guard import verify_request_authorization

coach = AICoachEngine()


def substitute_exercise(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /exercises/substitute
    Suggests 3 biomechanically matched alternative exercises.
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
        exercise_name = body.get("exercise_name")
        target_muscle = body.get("target_muscle", "Target Muscle")
        preferred_equipment = body.get("preferred_equipment")

        if not exercise_name:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required field 'exercise_name'"}),
            }

        result = coach.substitute_exercise(
            exercise_name=exercise_name,
            target_muscle=target_muscle,
            preferred_equipment=preferred_equipment,
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"success": True, **result}),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
