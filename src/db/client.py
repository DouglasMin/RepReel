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


def calculate_session_volume_analytics(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Planfit-style workout volume and progressive overload calculator:
    - Total Volume (총 볼륨 kg): sum(weight_kg * reps) for all completed sets
    - Total Sets & Reps
    - Estimated 1RM per exercise via Epley Formula: 1RM = weight * (1 + reps / 30)
    - Volume distribution per exercise
    """
    total_volume_kg = 0.0
    total_sets_completed = 0
    total_reps_completed = 0
    exercise_analytics: List[Dict[str, Any]] = []

    for exercise in session_data.get("completed_exercises", []):
        ex_id = exercise.get("exercise_id", "unknown")
        ex_name = exercise.get("exercise_name", "Unknown Exercise")
        ex_volume = 0.0
        ex_sets_completed = 0
        ex_reps_completed = 0
        max_est_1rm = 0.0
        top_set_weight = 0.0

        for s in exercise.get("sets", []):
            if s.get("completed", True):
                weight = float(s.get("weight_kg", 0.0))
                reps = int(s.get("reps", 0))
                set_volume = weight * reps

                ex_volume += set_volume
                ex_sets_completed += 1
                ex_reps_completed += reps
                total_volume_kg += set_volume
                total_sets_completed += 1
                total_reps_completed += reps

                if weight > top_set_weight:
                    top_set_weight = weight

                # Epley Formula for 1RM estimation
                if reps > 0 and weight > 0:
                    est_1rm = round(weight * (1.0 + reps / 30.0), 1)
                    if est_1rm > max_est_1rm:
                        max_est_1rm = est_1rm

        exercise_analytics.append({
            "exercise_id": ex_id,
            "exercise_name": ex_name,
            "volume_kg": round(ex_volume, 1),
            "completed_sets": ex_sets_completed,
            "completed_reps": ex_reps_completed,
            "top_set_weight_kg": round(top_set_weight, 1),
            "estimated_1rm_kg": round(max_est_1rm, 1),
        })

    return {
        "total_volume_kg": round(total_volume_kg, 1),
        "total_sets_completed": total_sets_completed,
        "total_reps_completed": total_reps_completed,
        "exercise_breakdown": exercise_analytics,
    }


class DynamoDBClient:
    def __init__(self, table_name: Optional[str] = None):
        self.table_name = table_name or os.getenv("TABLE_NAME", "instagram-reels-workout-table-dev")
        self.dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
        self.table = self.dynamodb.Table(self.table_name)

    # -------------------------------------------------------------
    # JOB OPERATIONS
    # -------------------------------------------------------------
    def create_job(self, job_id: str, url: str, reel_id: str, platform: Optional[str] = None) -> Dict[str, Any]:
        now = int(time.time())
        item = {
            "PK": f"JOB#{job_id}",
            "SK": "METADATA",
            "entity_type": "JOB",
            "job_id": job_id,
            "url": url,
            "reel_id": reel_id,
            "platform": platform or "UNKNOWN",
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
        platform: Optional[str] = None,
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
            "platform": platform or "UNKNOWN",
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

    def list_all_programs(self, limit: int = 50) -> List[Dict[str, Any]]:
        res = self.table.scan(
            FilterExpression=Attr("entity_type").eq("PROGRAM"),
            Limit=limit,
        )
        return [decimal_to_python(item) for item in res.get("Items", [])]

    # -------------------------------------------------------------
    # ACTIVE IN-PROGRESS WORKOUT SESSION DRAFT (Live Checklists)
    # -------------------------------------------------------------
    def save_active_session(self, user_id: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves or updates real-time in-progress workout draft (sets checked, weights, live timers).
        """
        now = int(time.time())
        analytics = calculate_session_volume_analytics(session_data)
        
        item = {
            "PK": f"USER#{user_id}",
            "SK": "ACTIVE_SESSION",
            "entity_type": "ACTIVE_SESSION",
            "user_id": user_id,
            "program_id": session_data.get("program_id"),
            "day_number": session_data.get("day_number", 1),
            "started_at": session_data.get("started_at", now),
            "last_updated_at": now,
            "session_data": float_to_decimal(session_data),
            "volume_analytics": float_to_decimal(analytics),
        }
        self.table.put_item(Item=item)
        return decimal_to_python(item)

    def get_active_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves active in-progress workout draft for resuming upon app launch.
        """
        res = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "ACTIVE_SESSION"})
        item = res.get("Item")
        return decimal_to_python(item) if item else None

    def delete_active_session(self, user_id: str) -> bool:
        """
        Clears active draft when workout is finished or cancelled.
        """
        res = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": "ACTIVE_SESSION"})
        if not res.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"USER#{user_id}", "SK": "ACTIVE_SESSION"})
        return True

    # -------------------------------------------------------------
    # COMPLETED SESSION LOGGING & HISTORY
    # -------------------------------------------------------------
    def log_workout_session(
        self,
        session_id: str,
        program_id: str,
        day_number: int,
        user_id: str,
        session_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Logs completed workout with Planfit-style volume analytics and clears active draft.
        """
        now = int(time.time())
        analytics = calculate_session_volume_analytics(session_data)

        item = {
            "PK": f"USER#{user_id}",
            "SK": f"SESSION#{session_id}",
            "entity_type": "SESSION",
            "session_id": session_id,
            "program_id": program_id,
            "day_number": day_number,
            "user_id": user_id,
            "logged_at": session_data.get("logged_at", now),
            "duration_seconds": session_data.get("duration_seconds", 0),
            "session_data": float_to_decimal(session_data),
            "volume_analytics": float_to_decimal(analytics),
            "created_at": now,
            "GSI1_PK": f"USER_PROGRAM#{user_id}#{program_id}",
            "GSI1_SK": str(now),
        }
        self.table.put_item(Item=item)
        
        # Clean up any active in-progress draft
        self.delete_active_session(user_id=user_id)
        
        return decimal_to_python(item)

    def get_workout_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a completed workout session log by user_id and session_id.
        """
        res = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"})
        item = res.get("Item")
        return decimal_to_python(item) if item else None

    def delete_workout_session(self, user_id: str, session_id: str) -> bool:
        """
        Permanently deletes a completed workout session log.
        """
        existing = self.table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"})
        if not existing.get("Item"):
            return False
        self.table.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"})
        return True

    def update_workout_session(
        self,
        user_id: str,
        session_id: str,
        session_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Updates a completed workout session log, recalculating Planfit-style volume analytics.
        """
        existing = self.get_workout_session(user_id=user_id, session_id=session_id)
        if not existing:
            return None

        now = int(time.time())
        analytics = calculate_session_volume_analytics(session_data)

        program_id = session_data.get("program_id") or existing.get("program_id", "custom")
        day_number = int(session_data.get("day_number", existing.get("day_number", 1)))
        logged_at = session_data.get("logged_at", existing.get("logged_at", now))
        duration_seconds = session_data.get("duration_seconds", existing.get("duration_seconds", 0))

        update_expr = (
            "SET session_data = :sdata, volume_analytics = :vanalytics, "
            "program_id = :pid, day_number = :day_num, logged_at = :lat, "
            "duration_seconds = :dur, updated_at = :uat, GSI1_PK = :gsi1_pk"
        )
        expr_values = {
            ":sdata": float_to_decimal(session_data),
            ":vanalytics": float_to_decimal(analytics),
            ":pid": program_id,
            ":day_num": day_number,
            ":lat": logged_at,
            ":dur": duration_seconds,
            ":uat": now,
            ":gsi1_pk": f"USER_PROGRAM#{user_id}#{program_id}",
        }

        self.table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"SESSION#{session_id}"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

        updated_item = {
            **existing,
            "session_data": session_data,
            "volume_analytics": analytics,
            "program_id": program_id,
            "day_number": day_number,
            "logged_at": logged_at,
            "duration_seconds": duration_seconds,
            "updated_at": now,
        }
        return updated_item

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
