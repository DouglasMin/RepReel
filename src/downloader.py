import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
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
        download_success: bool = False,
        error_message: Optional[str] = None,
    ):
        self.reel_id = reel_id
        self.title = title
        self.caption = caption
        self.uploader = uploader
        self.duration = duration
        self.audio_path = audio_path
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
            "download_success": self.download_success,
            "error_message": self.error_message,
        }


def extract_reel_id(url: str) -> str:
    """Extract the shortcode or ID from Instagram Reel URL."""
    match = re.search(r"/(?:reel|p|reels)/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    # fallback to cleaning alphanumeric characters
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", url.split("?")[0].rstrip("/").split("/")[-1])
    return cleaned or "unknown_reel"


def fetch_oembed_caption(url: str) -> Optional[Dict[str, Any]]:
    """Fallback: Fetch oEmbed metadata from Instagram without downloading video."""
    try:
        oembed_url = f"https://api.instagram.com/oembed/?url={url}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(oembed_url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def download_reel(url: str, output_dir: str = "downloads") -> ReelDownloadResult:
    """
    Downloads an Instagram Reel and extracts audio as MP3.
    Extracts caption/description and metadata.
    Implements graceful fallback if video download fails.
    """
    download_dir = Path(output_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    reel_id = extract_reel_id(url)

    audio_template = str(download_dir / f"{reel_id}.%(ext)s")
    expected_audio_path = download_dir / f"{reel_id}.mp3"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
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

            # Check if expected audio exists
            audio_path = None
            if expected_audio_path.exists():
                audio_path = expected_audio_path
            else:
                # check if any other file was created
                for candidate in download_dir.glob(f"{reel_id}.*"):
                    if candidate.suffix.lower() in [".mp3", ".m4a", ".wav", ".mp4"]:
                        audio_path = candidate
                        break

            return ReelDownloadResult(
                reel_id=reel_id,
                title=title,
                caption=description or title,
                uploader=uploader,
                duration=duration,
                audio_path=audio_path,
                download_success=bool(audio_path and audio_path.exists()),
                error_message=None,
            )

    except Exception as e:
        error_msg = str(e)
        # Attempt fallback to oEmbed or metadata without download
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
            download_success=False,
            error_message=f"Download failed ({error_msg}). Fallback caption obtained: {bool(caption)}",
        )
