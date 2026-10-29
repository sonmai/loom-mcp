import fcntl
import subprocess
import tempfile
from pathlib import Path

import httpx

from loom_mcp.client import LoomError, check_status, get_mp4_url
from loom_mcp.executables import find_executable


def extract_frames(video_id: str, timestamps: list[float]) -> list[tuple[float, Path, bytes]]:
    ffmpeg = find_executable("ffmpeg")
    if ffmpeg is None:
        raise LoomError("ffmpeg is missing. Run the installer again or install it with brew install ffmpeg.")
    cache = Path.home() / "Library" / "Caches" / "loom-mcp"
    frame_directory = cache / video_id / "frames"
    frame_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    media_path = cache / f"{video_id}.mp4"
    with (cache / f"{video_id}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not media_path.is_file() or media_path.stat().st_size == 0:
            download_mp4(get_mp4_url(video_id), media_path)
        frames = []
        for timestamp in timestamps:
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
                    raise LoomError(
                        "ffmpeg could not extract a frame. The MP4 cache may be invalid, "
                        "or this timestamp has no decodable frame."
                    )
                temporary_path.replace(frame_path)
                frames.append((timestamp, frame_path.resolve(), content))
            finally:
                temporary_path.unlink(missing_ok=True)
        return frames


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
