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
            ["1:39"], [100], [10**400], ["9" * 400 + ":00"],
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_timestamps(values, 99)


if __name__ == "__main__":
    unittest.main()
