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
    Calculates total volume (Planfit-style) and cleans up active draft.
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


def save_active_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    PUT /sessions/active
    Saves or updates current in-progress workout draft in real time (called per set checked).
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
        saved_active = db.save_active_session(user_id=user_id, session_data=body)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": True,
                "active_session": saved_active,
            }),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }


def get_active_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /sessions/active
    Retrieves in-progress workout draft for the user (to resume if app was closed).
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

    active_session = db.get_active_session(user_id=user_id)
    if not active_session:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "has_active_session": False,
                "message": "No active workout in progress.",
            }),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "has_active_session": True,
            "active_session": active_session,
        }),
    }


def delete_active_session(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    DELETE /sessions/active
    Discards or cancels the in-progress workout draft.
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

    deleted = db.delete_active_session(user_id=user_id)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "success": True,
            "deleted": deleted,
            "message": "Active session discarded successfully.",
        }),
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
