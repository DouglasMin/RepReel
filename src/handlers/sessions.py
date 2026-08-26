import os
import json
import uuid
from typing import Dict, Any

from src.db.client import DynamoDBClient
from src.auth.guard import verify_request_authorization

db = DynamoDBClient()


def create_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /sessions
    Logs an executed workout session with actual reps, weights lifted, RPE, and notes.
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    user_id = (
        headers.get("x-user-email")
        or headers.get("x-user-id")
        or "default_user"
    )

    try:
        body = json.loads(event.get("body") or "{}")
        program_id = body.get("program_id")
        day_number = int(body.get("day_number", 1))

        if not program_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required field 'program_id'"}),
            }

        session_id = f"session_{uuid.uuid4().hex[:12]}"
        logged_session = db.log_workout_session(
            session_id=session_id,
            program_id=program_id,
            day_number=day_number,
            user_id=user_id,
            session_data=body,
        )

        return {
            "statusCode": 201,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": True,
                "session_id": session_id,
                "session": logged_session,
            }),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


def list_sessions(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /sessions
    Query parameters:
      ?program_id=<id>&limit=<50>
    """
    headers = event.get("headers") or {}
    is_auth, auth_err = verify_request_authorization(headers)
    if not is_auth:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Forbidden", "message": auth_err}),
        }

    user_id = (
        headers.get("x-user-email")
        or headers.get("x-user-id")
        or "default_user"
    )

    query_params = event.get("queryStringParameters") or {}
    program_id = query_params.get("program_id")
    limit = int(query_params.get("limit", 50))

    try:
        sessions = db.list_workout_sessions(
            user_id=user_id,
            program_id=program_id,
            limit=limit,
        )

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"count": len(sessions), "sessions": sessions}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
