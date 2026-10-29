# Full code draft for approval

Not installed or runtime-verified. See [upstream research and layout](upstream.md),
[README and all six client configurations](../README.md), and
[MIT notice](../THIRD_PARTY_NOTICES.md).

## pyproject.toml

```toml
[project]
name = "loom-mcp"
version = "0.1.0"
description = "Read Loom metadata, transcripts, and frames over MCP stdio"
readme = "README.md"
requires-python = ">=3.11"
dependencies = ["mcp==2.3.0", "httpx==0.28.1"]

[project.scripts]
loom-mcp = "loom_mcp.server:main"

[build-system]
requires = ["uv_build>=0.13.6,<0.14"]
build-backend = "uv_build"
```

## .gitignore

```text
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.cache/
cache/
caches/
dist/
*.egg-info/
*.mp4
*.png
*.webm
*.mov
*.part
.DS_Store
```

## src/loom_mcp/__init__.py

```python
```

## src/loom_mcp/client.py

```python
import math
import subprocess
import sys
from urllib.parse import urlsplit

import httpx

from loom_mcp import queries

REFRESH_COOKIE = (
    "Refresh the Loom session: in your signed-in browser open DevTools > Application > "
    "Cookies > connect.sid, copy its value, then run "
    "security add-generic-password -U -s loom-mcp -a connect.sid -w "
    "and enter the value at the prompt."
)


class LoomError(Exception):
    pass


def read_cookie() -> str:
    if sys.platform != "darwin":
        raise LoomError("This server requires macOS Keychain.")
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", "loom-mcp",
             "-a", "connect.sid", "-w"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LoomError("Cannot read the Loom cookie from Keychain. " + REFRESH_COOKIE) from None
    cookie = result.stdout.strip()
    if result.returncode or not cookie:
        raise LoomError("Loom cookie is missing or Keychain access was denied. " + REFRESH_COOKIE)
    if any(ord(character) < 33 or ord(character) > 126 or character == ";" for character in cookie):
        raise LoomError("The Keychain item must contain only the connect.sid value. " + REFRESH_COOKIE)
    if cookie.startswith("connect.sid="):
        raise LoomError("Store only the cookie value, without 'connect.sid='. " + REFRESH_COOKIE)
    return cookie


def check_status(response: httpx.Response, source: str) -> None:
    if response.status_code in {401, 403}:
        raise LoomError(f"{source} denied access; the session may be expired. " + REFRESH_COOKIE)
    if not 200 <= response.status_code < 300:
        raise LoomError(f"{source} returned HTTP {response.status_code}.")


def graphql(operation: str, query: str, variables: dict) -> dict:
    cookie = read_cookie()
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        response = client.post(
            "https://www.loom.com/graphql",
            headers={
                "content-type": "application/json",
                "apollographql-client-name": "web",
                "x-loom-request-source": "loom_web",
                "cookie": f"connect.sid={cookie}",
            },
            json={"operationName": operation, "query": query, "variables": variables},
        )
    check_status(response, "Loom GraphQL")
    body = response.json()
    if body.get("errors"):
        raise LoomError(
            "Loom rejected the read query. Access may be denied, the session may have expired, "
            "or the internal API may have changed. " + REFRESH_COOKIE
        )
    if not isinstance(body.get("data"), dict):
        raise LoomError("Loom returned an unexpected GraphQL response; its internal API may have changed.")
    return body["data"]


def get_video_metadata(video_id: str) -> dict:
    data = graphql("fetchVideoData", queries.VIDEO, {"id": video_id, "password": None})
    video = data.get("video") or {}
    if video.get("__typename") != "RegularUserVideo":
        raise LoomError(
            "Video is unavailable, private, password-protected, or the session has expired. "
            + REFRESH_COOKIE
        )
    duration = video.get("playable_duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration):
        raise LoomError("Loom returned an invalid video duration; its internal API may have changed.")
    return {
        "id": video_id,
        "name": video["name"],
        "owner": video.get("owner"),
        "duration_seconds": duration,
        "created_at": video.get("createdAt"),
        "description": video.get("description"),
    }


def validate_download_url(value: str) -> str:
    url = urlsplit(value)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise LoomError("Loom returned an invalid HTTPS download URL.")
    return value


def get_video_transcript(video_id: str) -> dict:
    data = graphql("fetchVideoTranscript", queries.TRANSCRIPT, {"videoId": video_id})
    details = data.get("fetchVideoTranscript") or {}
    if details.get("__typename") != "VideoTranscriptDetails":
        raise LoomError("Transcript is unavailable or access was denied. " + REFRESH_COOKIE)
    if not details.get("source_url"):
        raise LoomError("The video has no transcript source yet; it may still be processing.")
    with httpx.Client(timeout=60, trust_env=False, follow_redirects=True) as client:
        response = client.get(validate_download_url(details["source_url"]))
    check_status(response, "Transcript download")
    phrases = response.json()["phrases"]
    return {
        "video_id": video_id,
        "segments": [
            {"timestamp_seconds": phrase["ts"], "speaker": phrase.get("speakerName"),
             "text": phrase["value"]}
            for phrase in phrases
        ],
    }


def get_mp4_url(video_id: str) -> str:
    data = graphql(
        "GetVideoTranscodedUrl", queries.DOWNLOAD,
        {"videoId": video_id, "forceOriginal": False},
    )
    source = data.get("getVideoTranscodedUrl") or {}
    if not source.get("url"):
        raise LoomError(
            "No MP4 download is available. Export may be disabled, processing incomplete, "
            "or access denied. This server cannot regenerate or enable exports. " + REFRESH_COOKIE
        )
    return validate_download_url(source["url"])
```

## src/loom_mcp/frames.py

```python
import fcntl
import subprocess
import tempfile
from pathlib import Path

import httpx

from loom_mcp.client import LoomError, check_status, get_mp4_url

FFMPEG = "/opt/homebrew/bin/ffmpeg"


def extract_frames(video_id: str, timestamps: list[float]) -> list[tuple[float, Path, bytes]]:
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
                    [FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
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
```

## src/loom_mcp/parsing.py

```python
import math
import re
from urllib.parse import urlsplit


def parse_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", value):
        return value.lower()
    try:
        url = urlsplit(value)
        match = re.fullmatch(r"/share/([0-9a-fA-F]{32})/?", url.path)
        if (
            url.scheme == "https"
            and url.netloc.lower() in {"loom.com", "www.loom.com"}
            and match
        ):
            return match.group(1).lower()
    except ValueError:
        pass
    raise ValueError("Use a 32-character hexadecimal video ID or an HTTPS Loom share URL.")


def parse_timestamps(values: list[str | float], duration: float) -> list[float]:
    if not 1 <= len(values) <= 10:
        raise ValueError("Provide between 1 and 10 timestamps.")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Loom did not return a positive, finite video duration.")
    timestamps = []
    for value in values:
        if isinstance(value, bool):
            raise ValueError("Timestamps must be seconds or M:SS strings, not booleans.")
        if isinstance(value, str):
            match = re.fullmatch(r"([0-9]+):([0-5][0-9](?:\.[0-9]+)?)", value)
            if match:
                seconds = int(match.group(1)) * 60 + float(match.group(2))
            elif re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
                seconds = float(value)
            else:
                raise ValueError("Use non-negative seconds or M:SS, for example 39 or '1:14'.")
        elif isinstance(value, (int, float)):
            seconds = float(value)
        else:
            raise ValueError("Timestamps must be seconds or M:SS strings.")
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Timestamps must be finite and non-negative.")
        if seconds >= duration:
            raise ValueError(
                f"Each timestamp must be less than the video duration ({duration:g} seconds); "
                "the endpoint has no frame."
            )
        timestamps.append(seconds)
    return timestamps
```

## src/loom_mcp/queries.py

```python
# Queries adapted from karbassi/mcp-loom@9d5f0ce5bfad960541ae11a3e525640d5acc8081 (MIT)

VIDEO = """query fetchVideoData($id: ID!, $password: String) {
  video: getVideo(id: $id, password: $password) {
    __typename
    ... on RegularUserVideo {
      id name createdAt playable_duration description
      owner { id display_name }
    }
  }
}"""

TRANSCRIPT = """query fetchVideoTranscript($videoId: ID!) {
  fetchVideoTranscript(videoId: $videoId) {
    __typename
    ... on VideoTranscriptDetails {
      source_url transcription_status
    }
  }
}"""

DOWNLOAD = """query GetVideoTranscodedUrl($videoId: ID!, $forceOriginal: Boolean) {
  getVideoTranscodedUrl(videoId: $videoId, forceOriginal: $forceOriginal) {
    __typename
    ... on VideoSource { url }
  }
}"""
```

## src/loom_mcp/server.py

```python
import json
import logging
import subprocess
import sys
from functools import wraps
from typing import Annotated

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, StrictFloat, StrictInt, StrictStr

from loom_mcp.client import LoomError, get_video_metadata, get_video_transcript
from loom_mcp.frames import extract_frames
from loom_mcp.parsing import parse_timestamps, parse_video_id

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logging.getLogger("httpx").disabled = True
logging.getLogger("httpcore").disabled = True

server = MCPServer("loom-mcp", log_level="WARNING")
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)
VideoReference = Annotated[
    StrictStr,
    Field(description="HTTPS Loom share URL or 32-character hexadecimal video ID."),
]
Timestamps = Annotated[
    list[StrictStr | StrictInt | StrictFloat],
    Field(
        min_length=1, max_length=10,
        description="1–10 positions: seconds (39, 74.5, or '39') or M:SS ('0:39', '1:14'). "
        "Each must be finite, non-negative, and less than the video duration.",
    ),
]


def safe_tool(function):
    @wraps(function)
    def invoke(*arguments, **keyword_arguments):
        try:
            return function(*arguments, **keyword_arguments)
        except LoomError as error:
            raise ToolError(str(error)) from None
        except httpx.TimeoutException:
            raise ToolError("The Loom request timed out; retry the read operation.") from None
        except httpx.HTTPError:
            raise ToolError("The Loom network request failed; check connectivity and retry.") from None
        except subprocess.TimeoutExpired:
            raise ToolError("Local frame extraction timed out.") from None
        except OSError:
            raise ToolError(
                "Local file or process access failed. Check cache permissions and "
                "/opt/homebrew/bin/ffmpeg."
            ) from None
        except Exception:
            raise ToolError(
                "Unexpected response or local processing failure. The internal Loom API "
                "may have changed; no response body or credentials were logged."
            ) from None
    return invoke


def validated_video_id(video: str) -> str:
    try:
        return parse_video_id(video)
    except ValueError as error:
        raise LoomError(str(error)) from None


@server.tool(annotations=READ_ONLY, structured_output=False)
@safe_tool
def get_video(video: VideoReference) -> str:
    """Read a Loom video's name, owner, duration in seconds, creation date, and description.

    Accepts an HTTPS share URL or video ID. Returns JSON text; unavailable optional
    metadata is null. Does not modify the video.
    """
    return json.dumps(get_video_metadata(validated_video_id(video)), ensure_ascii=False)


@server.tool(annotations=READ_ONLY, structured_output=False)
@safe_tool
def get_transcript(video: VideoReference) -> str:
    """Read a Loom transcript as JSON text with timestamped segments.

    Accepts an HTTPS share URL or video ID. Each segment contains timestamp_seconds,
    text, and speaker (null when unavailable). Reports an error if no transcript is
    available. Does not generate or modify transcripts.
    """
    return json.dumps(get_video_transcript(validated_video_id(video)), ensure_ascii=False)


@server.tool(annotations=READ_ONLY, structured_output=False)
@safe_tool
def get_frames(video: VideoReference, timestamps: Timestamps) -> list[str | Image]:
    """Read still frames at 1–10 timestamps, in input order, scaled to 1280 pixels wide.

    Accepts an HTTPS Loom share URL or video ID. For every timestamp, returns a text
    block with seconds and an absolute PNG path, followed by its MCP image content.
    Files are saved under ~/Library/Caches/loom-mcp/<video_id>/frames/. Downloads and
    reuses a local MP4 cache. Requires an available MP4 export. Does not modify Loom.
    """
    video_id = validated_video_id(video)
    metadata = get_video_metadata(video_id)
    try:
        seconds = parse_timestamps(timestamps, metadata["duration_seconds"])
    except ValueError as error:
        raise LoomError(str(error)) from None
    content = []
    for timestamp, path, image in extract_frames(video_id, seconds):
        content.extend([
            json.dumps({"timestamp_seconds": timestamp, "path": str(path)}),
            Image(data=image, format="png"),
        ])
    return content


def main() -> None:
    server.run(transport="stdio")
```

## tests/test_parsing.py

```python
import unittest

from loom_mcp.parsing import parse_timestamps, parse_video_id


class ParsingTests(unittest.TestCase):
    def test_share_links_and_ids_identify_the_same_video(self):
        video_id = "2d424ca8b7b04839ae7e57086030efb0"
        for value in (
            video_id,
            video_id.upper(),
            f"https://www.loom.com/share/{video_id}?sid=example#t=39",
            f"https://loom.com/share/{video_id}/",
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_video_id(value), video_id)

    def test_untrusted_urls_and_paths_are_rejected(self):
        for value in (
            "../../outside", "", "not-a-video-id",
            "https://loom.com.evil.test/share/2d424ca8b7b04839ae7e57086030efb0",
            "https://evil.test/loom.com/share/2d424ca8b7b04839ae7e57086030efb0",
            "https://user@loom.com/share/2d424ca8b7b04839ae7e57086030efb0",
            "http://loom.com/share/2d424ca8b7b04839ae7e57086030efb0",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_video_id(value)

    def test_timestamps_preserve_seconds_order_and_duplicates(self):
        self.assertEqual(
            parse_timestamps(["0:39", "1:14", "1:39", 0, 39.5, "39", "0:39"], 120),
            [39.0, 74.0, 99.0, 0.0, 39.5, 39.0, 39.0],
        )
        self.assertEqual(parse_timestamps([0] * 10, 1), [0.0] * 10)

    def test_invalid_or_out_of_range_frame_requests_are_rejected(self):
        for values in (
            [], [0] * 11, [-1], [True], [float("nan")], [float("inf")],
            ["1:60"], ["-0:01"], ["1:2"], ["1:02:03"], ["NaN"],
            ["1:39"], [100],
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_timestamps(values, 99)


if __name__ == "__main__":
    unittest.main()
```
