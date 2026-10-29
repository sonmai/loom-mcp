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
        try:
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
        except OverflowError:
            raise ValueError("Timestamps must be finite and non-negative.") from None
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Timestamps must be finite and non-negative.")
        if seconds >= duration:
            raise ValueError(
                f"Each timestamp must be less than the video duration ({duration:g} seconds); "
                "the endpoint has no frame."
            )
        timestamps.append(seconds)
    return timestamps
