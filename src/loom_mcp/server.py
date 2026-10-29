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
                "the ffmpeg installation."
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
