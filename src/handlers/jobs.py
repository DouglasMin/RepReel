import json
from typing import Dict, Any
from src.db.client import DynamoDBClient

db = DynamoDBClient()


def get_status(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    GET /jobs/{job_id}
    Returns status, error (if any), and program_id (if completed).
    """
    path_parameters = event.get("pathParameters") or {}
    job_id = path_parameters.get("job_id")

    if not job_id:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing job_id path parameter"}),
        }

    job = db.get_job(job_id)

    if not job:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Job '{job_id}' not found"}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(job),
    }


# Alias for backward/command compatibility
get_job_status = get_status
