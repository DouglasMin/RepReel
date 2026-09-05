import os
import json
import shutil
import boto3
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.downloader import download_reel, extract_video_keyframes, detect_video_platform
from src.transcribe import transcribe_audio
from src.extractor import extract_workout_program, should_use_vision_pipeline
from src.db.client import DynamoDBClient

s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-northeast-2"))
db = DynamoDBClient()


def count_program_exercises(program_obj: Any) -> int:
    """Counts total structured exercises across all days in the program."""
    try:
        return sum(
            len(grp.exercises)
            for day in getattr(program_obj, "days", [])
            for grp in getattr(day, "exercise_groups", [])
        )
    except Exception:
        return 0


def process_single_job(job_id: str, url: str, reel_id: str, platform: Optional[str] = None) -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    bucket_name = os.getenv("BUCKET_NAME")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

    resolved_platform = platform or detect_video_platform(url)

    tmp_dir = f"/tmp/downloads_{job_id}"
    frames_dir = f"/tmp/frames_{job_id}"

    try:
        # 1. Download video (.mp4/.webm), audio (.mp3), and metadata
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
                print(f"Whisper STT failed ({stt_err}), continuing with caption/vision...")

        # 4. Smart Routing Decision: Text Mode vs Vision Mode
        # YouTube Shorts are visual-first with on-screen text overlays; force Vision mode
        if resolved_platform == "YOUTUBE_SHORTS":
            use_vision = True
            print(f"Job {job_id}: YouTube Shorts detected. Activating Vision Mode for on-screen title card analysis.")
        else:
            use_vision = should_use_vision_pipeline(transcript=transcript, caption=download_result.caption)

        keyframes: List[str] = []

        if use_vision and download_result.video_path:
            # YouTube Shorts uses high-resolution (768px width) and up to 16 frames to capture quick 2-second title cards
            max_frames = 16 if resolved_platform == "YOUTUBE_SHORTS" else 10
            fps = 0.5 if resolved_platform == "YOUTUBE_SHORTS" else 0.33
            frame_width = 768 if resolved_platform == "YOUTUBE_SHORTS" else 512

            print(f"Job {job_id}: Extracting up to {max_frames} keyframes ({frame_width}px, fps={fps})...")
            keyframes = extract_video_keyframes(
                video_path=str(download_result.video_path),
                output_dir=frames_dir,
                max_frames=max_frames,
                fps=fps,
                width=frame_width,
            )
            print(f"Job {job_id}: Extracted {len(keyframes)} keyframes for multimodal analysis.")

        # 5. Extract WorkoutProgram with GPT-5.4 mini
        program = extract_workout_program(
            transcript=transcript,
            caption=download_result.caption,
            uploader=download_result.uploader,
            image_paths=keyframes if keyframes else None,
            api_key=api_key,
            model=model,
            platform=resolved_platform,
        )

        # 6. Safety Net Fallback: If text mode yielded 0 exercises or low confidence, retry with Vision
        total_exercises = count_program_exercises(program)
        if (not keyframes) and (total_exercises == 0 or program.audit.confidence_score < 0.5) and download_result.video_path:
            print(f"Job {job_id}: Text mode yielded {total_exercises} exercises. Executing 2nd Safety Net Vision Fallback...")
            keyframes = extract_video_keyframes(
                video_path=str(download_result.video_path),
                output_dir=frames_dir,
                max_frames=16,
                fps=0.5,
                width=768,
            )
            if keyframes:
                program = extract_workout_program(
                    transcript=transcript,
                    caption=download_result.caption,
                    uploader=download_result.uploader,
                    image_paths=keyframes,
                    api_key=api_key,
                    model=model,
                    platform=resolved_platform,
                )

        # 7. Save complete JSON to S3
        s3_program_uri = None
        if bucket_name:
            try:
                s3_json_key = f"programs/{program.program_id}.json"
                s3_data = {
                    "url": url,
                    "reel_id": reel_id,
                    "platform": resolved_platform,
                    "model_used": model,
                    "uploader": download_result.uploader,
                    "caption": download_result.caption,
                    "transcript": transcript,
                    "vision_frames_used": len(keyframes),
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

        # 8. Save WorkoutProgram to DynamoDB
        db.save_workout_program(
            program_dict=program.model_dump(),
            reel_id=reel_id,
            uploader=download_result.uploader,
            s3_uri=s3_program_uri,
            platform=resolved_platform,
        )

        # 9. Update Job Status to COMPLETED
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

    finally:
        # 10. Clean up temporary files in /tmp/
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(frames_dir, ignore_errors=True)
        except Exception:
            pass


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
            platform = body.get("platform")

            print(f"Starting processing for Job: {job_id} ({url}, Platform: {platform})")
            process_single_job(job_id=job_id, url=url, reel_id=reel_id, platform=platform)

        except Exception as err:
            print(f"Error handling SQS record: {err}")
            raise err
