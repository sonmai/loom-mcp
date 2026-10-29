import fcntl
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from loom_mcp.client import LoomError, LoomSession, check_status, get_mp4_url
from loom_mcp.executables import find_executable

UNUSED_VIDEO_RETENTION_SECONDS = 30 * 24 * 60 * 60


class FrameExtractionError(LoomError):
    pass


def cache_directory() -> Path:
    cache = Path.home() / "Library" / "Caches" / "loom-mcp"
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    cache.chmod(0o700)
    return cache


def extract_frames(loom: LoomSession, video_id: str, timestamps: list[float]) -> list[tuple[float, Path, bytes]]:
    ffmpeg = find_executable("ffmpeg")
    if ffmpeg is None:
        raise LoomError("ffmpeg is missing. Run the installer again or install it with brew install ffmpeg.")
    cache = cache_directory()
    frame_directory = cache / video_id / "frames"
    frame_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    media_path = cache / f"{video_id}.mp4"
    with (cache / f"{video_id}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cached = media_path.is_file() and media_path.stat().st_size > 0
        if not cached:
            download_mp4(get_mp4_url(loom, video_id), media_path)
        try:
            frames = [extract_frame(ffmpeg, media_path, frame_directory, timestamp) for timestamp in timestamps]
        except FrameExtractionError:
            if not cached:
                raise
            download_mp4(get_mp4_url(loom, video_id), media_path)
            frames = [extract_frame(ffmpeg, media_path, frame_directory, timestamp) for timestamp in timestamps]
        os.utime(media_path)
    remove_unused_videos(cache, video_id)
    return frames


def extract_frame(ffmpeg: str, media_path: Path, frame_directory: Path, timestamp: float) -> tuple[float, Path, bytes]:
    frame_path = frame_directory / f"{timestamp!r}s.png"
    with tempfile.NamedTemporaryFile(dir=frame_directory, suffix=".png", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-ss", str(timestamp), "-i", str(media_path), "-map", "0:v:0",
             "-frames:v", "1", "-vf", "scale=1280:-2", str(temporary_path)],
            capture_output=True, timeout=120, check=False,
        )
        content = temporary_path.read_bytes()
        if result.returncode or not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise FrameExtractionError(
                "ffmpeg could not extract a frame from a freshly downloaded MP4. "
                "This timestamp may have no decodable frame."
            )
        temporary_path.replace(frame_path)
        return timestamp, frame_path.resolve(), content
    finally:
        temporary_path.unlink(missing_ok=True)


def remove_unused_videos(cache: Path, keep: str) -> None:
    """Delete MP4s and frames of videos not used for frames in the retention period.

    Best effort: a video another process holds the lock for is skipped, and failures are ignored.
    """
    cutoff = time.time() - UNUSED_VIDEO_RETENTION_SECONDS
    for media_path in cache.glob("*.mp4"):
        video_id = media_path.stem
        try:
            if video_id == keep or media_path.stat().st_mtime >= cutoff:
                continue
            with (cache / f"{video_id}.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                media_path.unlink(missing_ok=True)
                shutil.rmtree(cache / video_id, ignore_errors=True)
        except OSError:
            continue


def download_mp4(url: str, destination: Path) -> None:
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with httpx.Client(timeout=120, trust_env=False, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                check_status(response, "MP4 download")
                with temporary_path.open("wb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
        with temporary_path.open("rb") as downloaded:
            header = downloaded.read(32)
        if b"ftyp" not in header:
            raise LoomError("The download was not an MP4; the cache was not replaced.")
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
