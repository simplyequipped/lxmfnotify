# stdin reader, pattern matching and the pipe program.
#
# simplyequipped

import re
import subprocess
import threading

PIPE_TIMEOUT = 10  # seconds a pipe script may run per line


class Matcher:
    # Plain patterns are substrings, regex patterns use re.search. A line
    # matches when any pattern of either kind exists. No patterns at all
    # matches every line.

    def __init__(self, patterns, regexes=()):
        self.patterns = list(patterns)
        self.regexes = [re.compile(r) for r in regexes]

    def matches(self, line):
        if not self.patterns and not self.regexes:
            return True
        return (any(p in line for p in self.patterns) or any(r.search(line) for r in self.regexes))


def load_pattern_file(path):
    # One pattern per line, blank lines and # comments ignored. A line
    # written /like this/ is a regular expression, anything else is text.
    # Returns (patterns, regexes).
    patterns = []
    regexes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            if len(line) >= 2 and line.startswith("/") and line.endswith("/"):
                regexes.append(line[1:-1])
            else:
                patterns.append(line)
    return patterns, regexes


def run_pipe(path, line, log):
    # Runs the script once with the line passed to its stdin
    # Returns to stdout, or None when the line is to be dropped
    try:
        r = subprocess.run([path], input=line + "\n", capture_output=True, text=True, timeout=PIPE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log("pipe %s killed after %d s" % (path, PIPE_TIMEOUT))
        return None
    if r.returncode != 0:
        err = r.stderr.strip().splitlines()
        log("pipe %s exit %d%s" % (path, r.returncode, ": " + err[0] if err else ""))
        return None
    out = r.stdout.rstrip()
    return out if out else None


class Reader(threading.Thread):
    # Reads stream (a binary file object) to EOF, one line at a time

    def __init__(self, stream, matcher, pipe, on_result, on_eof, log, verbose=False):
        super().__init__(daemon=True)
        self.stream = stream
        self.matcher = matcher
        self.pipe = pipe
        self.on_result = on_result
        self.on_eof = on_eof
        self.log = log
        self.verbose = verbose

    def run(self):
        for raw in self.stream:
            line = raw.decode("utf-8", "replace")
            if line.endswith("\n"):
                line = line[:-1]
            if line.endswith("\r"):
                line = line[:-1]
            if not self.matcher.matches(line):
                continue
            if self.verbose:
                self.log("match: " + line)
            result = run_pipe(self.pipe, line, self.log) if self.pipe else line
            if result is not None:
                self.on_result(result)
        self.on_eof()
