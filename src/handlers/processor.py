import os
import json
import boto3
from pathlib import Path
from typing import Dict, Any

from src.downloader import download_reel
from src.transcribe import transcribe_audio
from src.extractor import extract_workout_program
from src.db.client import DynamoDBClient

s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
db = DynamoDBClient()


def process_single_job(job_id: str, url: str, reel_id: str) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    bucket_name = os.getenv("BUCKET_NAME")
    model = os.getenv("OPENAI_MODEL", "o3-mini")

    try:
        # 1. Download Reel audio and extract captions (/tmp directory in Lambda)
        tmp_dir = "/tmp/downloads"
        download_result = download_reel(url, output_dir=tmp_dir)

        # 2. Upload audio to S3 if available
        s3_audio_key = None
        if download_result.download_success and download_result.audio_path and bucket_name:
            try:
                s3_audio_key = f"audio/{reel_id}.mp3"
                s3.upload_file(str(download_result.audio_path), bucket_name, s3_audio_key)
            except Exception as s3_err:
                print(f"Warning: Failed to upload audio to S3: {s3_err}")

        # 3. Transcribe audio with OpenAI Whisper
        transcript = ""
        if download_result.download_success and download_result.audio_path and api_key:
            try:
                transcript = transcribe_audio(download_result.audio_path, api_key=api_key)
            except Exception as stt_err:
                print(f"Whisper STT failed ({stt_err}), continuing with caption...")

        # 4. Multi-Role Structured Extraction with o3-mini
        program = extract_workout_program(
            transcript=transcript,
            caption=download_result.caption,
            uploader=download_result.uploader,
            api_key=api_key,
            model=model,
        )

        # 5. Save complete JSON to S3
        s3_program_uri = None
        if bucket_name:
            try:
                s3_json_key = f"programs/{program.program_id}.json"
                s3_data = {
                    "url": url,
                    "reel_id": reel_id,
                    "model_used": model,
                    "uploader": download_result.uploader,
                    "caption": download_result.caption,
                    "transcript": transcript,
                    "workout_program": program.model_dump(),
                }
                s3.put_object(
                    Bucket=bucket_name,
                    Key=s3_json_key,
                    Body=json.dumps(s3_data, ensure_ascii=False, indent=2),
                    ContentType="application/json",
                )
                s3_program_uri = f"s3://{bucket_name}/{s3_json_key}"
            except Exception as s3_err:
                print(f"Warning: Failed to upload program JSON to S3: {s3_err}")

        # 6. Save WorkoutProgram to DynamoDB
        db.save_workout_program(
            program_dict=program.model_dump(),
            reel_id=reel_id,
            uploader=download_result.uploader,
            s3_uri=s3_program_uri,
        )

        # 7. Update Job Status to COMPLETED
        db.update_job_status(
            job_id=job_id,
            status="COMPLETED",
            program_id=program.program_id,
            confidence_score=program.audit.confidence_score,
        )
        print(f"Job {job_id} successfully completed. Program ID: {program.program_id}")

    except Exception as e:
        error_msg = str(e)
        print(f"Job {job_id} failed: {error_msg}")
        db.update_job_status(
            job_id=job_id,
            status="FAILED",
            error=error_msg,
        )
        raise e


def handler(event: Dict[str, Any], context: Any) -> None:
    """
    SQS Event Consumer Lambda handler.
    Processes background video analysis jobs.
    """
    records = event.get("Records", [])
    print(f"Processing {len(records)} SQS message(s)...")

    for record in records:
        try:
            body = json.loads(record.get("body") or "{}")
            job_id = body["job_id"]
            url = body["url"]
            reel_id = body["reel_id"]

            print(f"Starting processing for Job: {job_id} ({url})")
            process_single_job(job_id=job_id, url=url, reel_id=reel_id)

        except Exception as err:
            print(f"Error handling SQS record: {err}")
            # Re-raising allows SQS retry & Dead Letter Queue (DLQ) if persistent
            raise err
