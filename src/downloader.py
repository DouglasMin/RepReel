import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import yt_dlp
import requests


class ReelDownloadResult:
    def __init__(
        self,
        reel_id: str,
        title: str,
        caption: str,
        uploader: Optional[str] = None,
        duration: Optional[float] = None,
        audio_path: Optional[Path] = None,
        video_path: Optional[Path] = None,
        download_success: bool = False,
        error_message: Optional[str] = None,
    ):
        self.reel_id = reel_id
        self.title = title
        self.caption = caption
        self.uploader = uploader
        self.duration = duration
        self.audio_path = audio_path
        self.video_path = video_path
        self.download_success = download_success
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reel_id": self.reel_id,
            "title": self.title,
            "caption": self.caption,
            "uploader": self.uploader,
            "duration": self.duration,
            "audio_path": str(self.audio_path) if self.audio_path else None,
            "video_path": str(self.video_path) if self.video_path else None,
            "download_success": self.download_success,
            "error_message": self.error_message,
        }


def is_supported_video_url(url: str) -> bool:
    """Checks if the URL is a supported Instagram or YouTube video/shorts URL."""
    if not url or not isinstance(url, str):
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in ["instagram.com", "instagr.am", "youtube.com", "youtu.be"])


def extract_reel_id(url: str) -> str:
    """Extract the shortcode or ID from Instagram Reel or YouTube Shorts URL."""
    # 1. Instagram pattern: /(reel|p|reels)/<id>
    ig_match = re.search(r"/(?:reel|p|reels)/([A-Za-z0-9_-]+)", url)
    if ig_match:
        return ig_match.group(1)

    # 2. YouTube Shorts pattern: /shorts/<id>
    yt_shorts_match = re.search(r"/shorts/([A-Za-z0-9_-]+)", url)
    if yt_shorts_match:
        return yt_shorts_match.group(1)

    # 3. YouTube youtu.be/<id>
    yt_short_domain = re.search(r"youtu\.be/([A-Za-z0-9_-]+)", url)
    if yt_short_domain:
        return yt_short_domain.group(1)

    # 4. YouTube watch?v=<id>
    yt_watch_match = re.search(r"[?&]v=([A-Za-z0-9_-]+)", url)
    if yt_watch_match:
        return yt_watch_match.group(1)

    # 5. YouTube embed or /v/<id>
    yt_embed_match = re.search(r"/(?:embed|v)/([A-Za-z0-9_-]+)", url)
    if yt_embed_match:
        return yt_embed_match.group(1)

    # 6. Fallback clean
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", url.split("?")[0].rstrip("/").split("/")[-1])
    return cleaned or "unknown_video"


# Alias for generalized video ID extraction
extract_video_id = extract_reel_id


def fetch_oembed_caption(url: str) -> Optional[Dict[str, Any]]:
    """Fallback: Fetch oEmbed metadata from Instagram or YouTube without downloading video."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        url_lower = url.lower()
        if "instagram.com" in url_lower or "instagr.am" in url_lower:
            oembed_url = f"https://api.instagram.com/oembed/?url={url}"
            res = requests.get(oembed_url, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
            res = requests.get(oembed_url, headers=headers, timeout=10)
            if res.status_code == 200:
                return res.json()
    except Exception:
        pass
    return None


def extract_video_keyframes(
    video_path: str,
    output_dir: Optional[str] = None,
    max_frames: int = 10,
    fps: float = 0.33,
) -> List[str]:
    """
    Extracts representative keyframes from video using FFmpeg for GPT-5.4 mini Vision analysis.
    Resizes to 512px width for minimal token usage (~85 tokens/image).
    """
    if not video_path or not os.path.exists(video_path):
        return []

    target_dir = Path(output_dir or f"/tmp/frames_{Path(video_path).stem}")
    target_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = str(target_dir / "frame_%03d.jpg")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"fps={fps},scale=512:-1",
        "-q:v", "3",
        output_pattern,
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except Exception as e:
        # Fallback if ffmpeg fails
        return []

    extracted = sorted([str(p) for p in target_dir.glob("frame_*.jpg")])

    # If more than max_frames, downsample evenly
    if len(extracted) > max_frames:
        step = len(extracted) / max_frames
        extracted = [extracted[int(i * step)] for i in range(max_frames)]

    return extracted


def download_reel(url: str, output_dir: str = "/tmp/downloads") -> ReelDownloadResult:
    """
    Downloads an Instagram Reel or YouTube Shorts video, preserving video (.mp4/.webm) and extracting audio (.mp3).
    Extracts caption/description and metadata.
    """
    download_dir = Path(output_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    reel_id = extract_reel_id(url)

    video_template = str(download_dir / f"{reel_id}.%(ext)s")
    expected_audio_path = download_dir / f"{reel_id}.mp3"

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best",
        "outtmpl": video_template,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extract_flat": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise ValueError("Could not extract video info.")

            title = info.get("title", "")
            description = info.get("description", "")
            uploader = info.get("uploader") or info.get("uploader_id") or info.get("channel")
            duration = info.get("duration")

            # Identify downloaded video file
            video_path = None
            for candidate in download_dir.glob(f"{reel_id}.*"):
                if candidate.suffix.lower() in [".mp4", ".mov", ".mkv", ".webm"]:
                    video_path = candidate
                    break

            # Extract audio with FFmpeg if video exists
            audio_path = None
            if video_path and video_path.exists():
                try:
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "libmp3lame", "-q:a", "4", str(expected_audio_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                    if expected_audio_path.exists():
                        audio_path = expected_audio_path
                except Exception:
                    pass

            return ReelDownloadResult(
                reel_id=reel_id,
                title=title,
                caption=description or title,
                uploader=uploader,
                duration=duration,
                audio_path=audio_path,
                video_path=video_path,
                download_success=bool((audio_path and audio_path.exists()) or (video_path and video_path.exists())),
                error_message=None,
            )

    except Exception as e:
        error_msg = str(e)
        oembed_data = fetch_oembed_caption(url)
        caption = ""
        uploader = None
        if oembed_data:
            caption = oembed_data.get("title", "")
            uploader = oembed_data.get("author_name")

        return ReelDownloadResult(
            reel_id=reel_id,
            title="",
            caption=caption,
            uploader=uploader,
            duration=None,
            audio_path=None,
            video_path=None,
            download_success=False,
            error_message=f"Download failed ({error_msg}). Fallback caption obtained: {bool(caption)}",
        )


# Alias for generalized video download
download_video = download_reel
