import unittest

from lxmfnotify.window import Window


class WindowTests(unittest.TestCase):
    def test_interval_zero_passes_through(self):
        sent = []
        w = Window(0, sent.append)
        w.add("one")
        w.add("two")
        self.assertEqual(sent, ["one", "two"])

    def test_interval_collects_until_flush(self):
        sent = []
        w = Window(60, sent.append)
        w.add("one")
        w.add("two")
        self.assertEqual(sent, [])
        w.flush()
        self.assertEqual(sent, ["one\ntwo"])

    def test_empty_window_sends_nothing(self):
        sent = []
        w = Window(60, sent.append)
        w.flush()
        self.assertEqual(sent, [])

    def test_flush_clears(self):
        sent = []
        w = Window(60, sent.append)
        w.add("one")
        w.flush()
        w.flush()
        self.assertEqual(sent, ["one"])


if __name__ == "__main__":
    unittest.main()
