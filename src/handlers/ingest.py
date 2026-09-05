import os
import json
import uuid
import boto3
from typing import Dict, Any

from src.downloader import extract_reel_id, is_supported_video_url, detect_video_platform
from src.db.client import DynamoDBClient
from src.auth.guard import verify_request_authorization

sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
db = DynamoDBClient()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    POST /reels
    Ingests Instagram Reel or YouTube Shorts URL, checks authorization, initializes Job in DynamoDB, and enqueues to SQS.
    Returns 202 Accepted if valid, 401/403 if unauthorized.
    """
    try:
        headers = event.get("headers") or {}

        # 1. Verify App / User Authorization & Whitelist Guard
        is_authorized, auth_error = verify_request_authorization(headers)
        if not is_authorized:
            return {
                "statusCode": 403,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Forbidden",
                    "message": auth_error or "You are not authorized to use this private API.",
                }),
            }

        # 2. Parse request payload
        body = json.loads(event.get("body") or "{}")
        url = body.get("url")

        if not is_supported_video_url(url):
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Invalid or missing 'url' parameter. Must be an Instagram Reel or YouTube Shorts URL."
                }),
            }

        platform = detect_video_platform(url)
        reel_id = extract_reel_id(url)
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        # 3. Create Job in DynamoDB with platform tracking
        job = db.create_job(job_id=job_id, url=url, reel_id=reel_id, platform=platform)

        # 4. Push message to SQS Queue with platform metadata
        queue_url = os.getenv("QUEUE_URL")
        if queue_url:
            message_body = {
                "job_id": job_id,
                "url": url,
                "reel_id": reel_id,
                "platform": platform,
            }
            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message_body),
            )

        # 5. Return 202 Accepted
        response_body = {
            "success": True,
            "job_id": job_id,
            "reel_id": reel_id,
            "platform": platform,
            "status": "PROCESSING",
            "message": f"{platform.replace('_', ' ').title()} analysis job initiated successfully.",
            "status_url": f"/jobs/{job_id}",
        }

        return {
            "statusCode": 202,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response_body),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Internal Server Error: {str(e)}"}),
        }
