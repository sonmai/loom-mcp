import fcntl
import os
import tempfile
import time
import unittest
from pathlib import Path

from loom_mcp.frames import UNUSED_VIDEO_RETENTION_SECONDS, remove_unused_videos


class CacheTests(unittest.TestCase):
    def test_pruning_removes_only_stale_unlocked_videos(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            stale = time.time() - UNUSED_VIDEO_RETENTION_SECONDS - 60
            for video_id in ("current", "recent", "stale", "busy"):
                (cache / f"{video_id}.mp4").write_bytes(b"mp4")
                (cache / video_id / "frames").mkdir(parents=True)
                if video_id != "recent":
                    os.utime(cache / f"{video_id}.mp4", (stale, stale))
            with (cache / "busy.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                remove_unused_videos(cache, "current")
            self.assertEqual(sorted(path.stem for path in cache.glob("*.mp4")), ["busy", "current", "recent"])
            self.assertFalse((cache / "stale").exists())
            self.assertTrue((cache / "busy" / "frames").is_dir())


if __name__ == "__main__":
    unittest.main()
