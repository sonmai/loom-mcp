import math
import subprocess
import sys
from urllib.parse import urlsplit

import httpx

from loom_mcp import queries
from loom_mcp.keychain import is_valid_session_cookie

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
    if cookie.startswith("connect.sid="):
        raise LoomError("Store only the cookie value, without 'connect.sid='. " + REFRESH_COOKIE)
    if not is_valid_session_cookie(cookie):
        raise LoomError("The Keychain item must contain only the connect.sid value. " + REFRESH_COOKIE)
    return cookie


def check_status(response: httpx.Response, source: str) -> None:
    if response.status_code in {401, 403}:
        raise LoomError(f"{source} denied access; the session may be expired. " + REFRESH_COOKIE)
    if not 200 <= response.status_code < 300:
        raise LoomError(f"{source} returned HTTP {response.status_code}.")


class LoomSession:
    """One Keychain read and one GraphQL connection, shared by the requests of a tool call."""

    def __init__(self):
        self.cookie = read_cookie()
        self.http = httpx.Client(timeout=30, trust_env=False, follow_redirects=False)

    def __enter__(self) -> "LoomSession":
        return self

    def __exit__(self, *exception) -> None:
        self.http.close()

    def graphql(self, operation: str, query: str, variables: dict) -> dict:
        response = self.http.post(
            "https://www.loom.com/graphql",
            headers={
                "content-type": "application/json",
                "apollographql-client-name": "web",
                "x-loom-request-source": "loom_web",
                "cookie": f"connect.sid={self.cookie}",
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


def get_video_metadata(loom: LoomSession, video_id: str) -> dict:
    data = loom.graphql("fetchVideoData", queries.VIDEO, {"id": video_id, "password": None})
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


def get_video_transcript(loom: LoomSession, video_id: str) -> dict:
    data = loom.graphql("fetchVideoTranscript", queries.TRANSCRIPT, {"videoId": video_id})
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


def get_mp4_url(loom: LoomSession, video_id: str) -> str:
    data = loom.graphql(
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
