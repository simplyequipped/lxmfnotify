import io
import os
import stat
import tempfile
import unittest

from lxmfnotify import reader
from lxmfnotify.reader import Matcher, Reader, run_pipe


def script(body):
    f = tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh")
    f.write("#!/bin/sh\n" + body + "\n")
    f.close()
    os.chmod(f.name, stat.S_IRWXU)
    return f.name


class PipeTests(unittest.TestCase):
    def setUp(self):
        self.logged = []
        self.files = []

    def tearDown(self):
        for f in self.files:
            os.unlink(f)

    def make(self, body):
        path = script(body)
        self.files.append(path)
        return path

    def test_uppercases(self):
        p = self.make("tr a-z A-Z")
        self.assertEqual(run_pipe(p, "hello", self.logged.append), "HELLO")
        self.assertEqual(self.logged, [])

    def test_empty_output_drops(self):
        p = self.make("cat > /dev/null")
        self.assertIsNone(run_pipe(p, "hello", self.logged.append))
        self.assertEqual(self.logged, [])

    def test_nonzero_exit_drops_and_logs(self):
        p = self.make("echo oops >&2; exit 3")
        self.assertIsNone(run_pipe(p, "hello", self.logged.append))
        self.assertEqual(len(self.logged), 1)
        self.assertIn("exit 3", self.logged[0])
        self.assertIn("oops", self.logged[0])

    def test_timeout_kills_and_drops(self):
        p = self.make("sleep 5")
        old = reader.PIPE_TIMEOUT
        reader.PIPE_TIMEOUT = 1
        try:
            self.assertIsNone(run_pipe(p, "hello", self.logged.append))
        finally:
            reader.PIPE_TIMEOUT = old
        self.assertEqual(len(self.logged), 1)
        self.assertIn("killed", self.logged[0])

    def test_reader_end_to_end(self):
        p = os.path.join(os.path.dirname(__file__), "..", "examples", "js8mon-parse")
        stream = io.BytesIO(
            b"033215 -12  0.3   7.078512 normal N0CALL: HELLO\n"
            b"033230  -4 -0.1   7.078512 normal W1AW: NOPE\r\n"
            b"033245  -4 -0.1   7.078512 normal N0CALL: BYE")
        results = []
        ended = []
        r = Reader(stream, Matcher(["N0CALL"]), p, results.append,
                   lambda: ended.append(True), self.logged.append)
        r.start()
        r.join(10)
        self.assertEqual(results, ["N0CALL: HELLO", "N0CALL: BYE"])
        self.assertEqual(ended, [True])


if __name__ == "__main__":
    unittest.main()
