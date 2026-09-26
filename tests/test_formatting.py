import unittest

from keylimits.formatting import (
    humanize,
    progress_bar,
    relative_time,
    render_table,
)


class HumanizeTests(unittest.TestCase):
    def test_scales(self):
        self.assertEqual(humanize(1_500_000), "1.5M")
        self.assertEqual(humanize(2_000), "2K")
        self.assertEqual(humanize(3_000_000_000), "3B")

    def test_small_and_invalid(self):
        self.assertEqual(humanize(42), "42")
        self.assertEqual(humanize(None), "None")


class TableTests(unittest.TestCase):
    def test_alignment(self):
        table = render_table([["a", "1"], ["bbb", "22"]], ["name", "n"])
        lines = table.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("name"))


class ProgressBarTests(unittest.TestCase):
    def test_width_matches(self):
        self.assertEqual(len(progress_bar(50, width=10)), 10)

    def test_none_is_empty(self):
        self.assertEqual(len(progress_bar(None, width=8)), 8)

    def test_full_remaining_when_untouched(self):
        # 0% used -> every cell filled when drawing "remaining".
        bar = progress_bar(0, width=12)
        self.assertEqual(bar.count("\u2588") + bar.count("#"), 12)

    def test_empty_remaining_when_exhausted(self):
        bar = progress_bar(100, width=12)
        self.assertEqual(bar.count("\u2588") + bar.count("#"), 0)


class RelativeTimeTests(unittest.TestCase):
    def test_formats_hours(self):
        import datetime

        now = datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)
        future = "2026-09-28T07:00:00+00:00"
        self.assertEqual(relative_time(future, now), "19h")


if __name__ == "__main__":
    unittest.main()