import os
import time
from decimal import Decimal
from typing import Dict, Any, Optional, List
import boto3
from boto3.dynamodb.conditions import Key, Attr

# Helper function to convert Python floats to Decimal for DynamoDB compatibility
def float_to_decimal(obj: Any) -> Any:
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [float_to_decimal(v) for v in obj]
    return obj


# Helper function to convert Decimal back to float/int for JSON responses
def decimal_to_python(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_python(v) for v in obj]
    return obj


class DynamoDBClient:
    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or os.getenv("TABLE_NAME", "instagram-reels-workout-table-dev")
        self.dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
        self.table = self.dynamodb.Table(self.table_name)

    # -------------------------------------------------------------
    # JOB OPERATIONS
    # -------------------------------------------------------------
    def create_job(self, job_id: str, url: str, reel_id: str) -> Dict[str, Any]:
        now = int(time.time())
        item = {
            "PK": f"JOB#{job_id}",
            "SK": "METADATA",
            "entity_type": "JOB",
            "job_id": job_id,
            "url": url,
            "reel_id": reel_id,
            "status": "PROCESSING",
            "created_at": now,
            "updated_at": now,
            "GSI1_PK": "STATUS#PROCESSING",
            "GSI1_SK": str(now),
        }
        self.table.put_item(Item=item)
        return decimal_to_python(item)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        res = self.table.get_item(Key={"PK": f"JOB#{job_id}", "SK": "METADATA"})
        item = res.get("Item")
        return decimal_to_python(item) if item else None

    def update_job_status(
        self,
        job_id: str,
        status: str,
        error: Optional[str] = None,
        program_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
    ) -> None:
        now = int(time.time())
        update_expr = "SET #status = :status, updated_at = :updated_at, GSI1_PK = :gsi1_pk, GSI1_SK = :gsi1_sk"
        expr_names = {"#status": "status"}
        expr_values: Dict[str, Any] = {
            ":status": status,
            ":updated_at": now,
            ":gsi1_pk": f"STATUS#{status}",
            ":gsi1_sk": str(now),
        }

        if error:
            update_expr += ", #error = :error"
            expr_names["#error"] = "error"
            expr_values[":error"] = error

        if program_id:
            update_expr += ", program_id = :program_id"
            expr_values[":program_id"] = program_id

        if confidence_score is not None:
            update_expr += ", confidence_score = :confidence_score"
            expr_values[":confidence_score"] = float_to_decimal(confidence_score)

        self.table.update_item(
            Key={"PK": f"JOB#{job_id}", "SK": "METADATA"},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )

    # -------------------------------------------------------------
    # PROGRAM OPERATIONS
    # -------------------------------------------------------------
    def save_workout_program(
        self,
        program_dict: Dict[str, Any],
        reel_id: str,
        uploader: Optional[str] = None,
        s3_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = int(time.time())
        program_id = program_dict["program_id"]
        creator = uploader or "Unknown"

        item = {
            "PK": f"PROGRAM#{program_id}",
            "SK": "METADATA",
            "entity_type": "PROGRAM",
            "program_id": program_id,
            "reel_id": reel_id,
            "creator": creator,
            "title": program_dict.get("title", "Workout Program"),
            "split_type": program_dict.get("split_type"),
            "cycle_frequency": program_dict.get("cycle_frequency"),
            "overview": program_dict.get("overview"),
            "program_data": float_to_decimal(program_dict),
            "s3_uri": s3_uri,
            "created_at": now,
            "updated_at": now,
            "GSI1_PK": f"CREATOR#{creator}",
            "GSI1_SK": str(now),
        }

        self.table.put_item(Item=item)
        return decimal_to_python(item)

    def update_workout_program(
        self,
        program_id: str,
        program_dict: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        now = int(time.time())
        res = self.table.get_item(Key={"PK": f"PROGRAM#{program_id}", "SK": "METADATA"})
        existing = res.get("Item")
        if not existing:
            return None

        update_expr = "SET program_data = :pdata, title = :title, updated_at = :updated_at"
        expr_values = {
            ":pdata": float_to_decimal(program_dict),
            ":title": program_dict.get("title", existing.get("title", "Workout Program")),
            ":updated_at": now,
        }

        self.table.update_item(
            Key={"PK": f"PROGRAM#{program_id}", "SK": "METADATA"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        return decimal_to_python({**existing, "program_data": program_dict, "updated_at": now})

    def delete_workout_program(self, program_id: str) -> bool:
        res = self.table.get_item(Key={"PK": f"PROGRAM#{program_id}", "SK": "METADATA"})
        if not res.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"PROGRAM#{program_id}", "SK": "METADATA"})
        return True

    def get_workout_program(self, program_id: str) -> Optional[Dict[str, Any]]:
        res = self.table.get_item(Key={"PK": f"PROGRAM#{program_id}", "SK": "METADATA"})
        item = res.get("Item")
        return decimal_to_python(item) if item else None

    def list_programs_by_creator(self, creator: str, limit: int = 20) -> List[Dict[str, Any]]:
        res = self.table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1_PK").eq(f"CREATOR#{creator}"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return [decimal_to_python(item) for item in res.get("Items", [])]

    # -------------------------------------------------------------
    # SESSION LOGGING OPERATIONS
    # -------------------------------------------------------------
    def log_workout_session(
        self,
        session_id: str,
        program_id: str,
        day_number: int,
        user_id: str,
        session_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = int(time.time())
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"SESSION#{session_id}",
            "entity_type": "SESSION",
            "session_id": session_id,
            "program_id": program_id,
            "day_number": day_number,
            "user_id": user_id,
            "logged_at": session_data.get("logged_at", now),
            "session_data": float_to_decimal(session_data),
            "created_at": now,
            "GSI1_PK": f"USER_PROGRAM#{user_id}#{program_id}",
            "GSI1_SK": str(now),
        }
        self.table.put_item(Item=item)
        return decimal_to_python(item)

    def list_workout_sessions(
        self,
        user_id: str,
        program_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        if program_id:
            res = self.table.query(
                IndexName="GSI1",
                KeyConditionExpression=Key("GSI1_PK").eq(f"USER_PROGRAM#{user_id}#{program_id}"),
                ScanIndexForward=False,
                Limit=limit,
            )
        else:
            res = self.table.query(
                KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("SESSION#"),
                ScanIndexForward=False,
                Limit=limit,
            )
        return [decimal_to_python(item) for item in res.get("Items", [])]
