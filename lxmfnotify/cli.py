# Argument parsing, startup checks and wiring.
#
# simplyequipped

import argparse
import os
import re
import signal
import sys
import threading
import time

from .reader import Matcher, Reader, load_pattern_file

HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def log(msg):
    sys.stderr.write("lxmfnotify: %s\n" % msg)
    sys.stderr.flush()


def fail(msg):
    log(msg)
    sys.exit(2)


def parse_hashes(text):
    hashes = []
    for h in text.split(","):
        h = h.strip()
        if not HASH_RE.match(h):
            fail("malformed address: %s" % h)
        hashes.append(bytes.fromhex(h))
    return hashes


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="lxmfnotify",
        description="Read lines from stdin, keep the ones that match, and send "
                    "them to LXMF addresses.")
    p.add_argument("--address", required=True, metavar="HASH[,HASH...]",
                   help="LXMF destination hashes, 32 hex characters each")
    p.add_argument("--match", action="append", default=[], metavar="PATTERN",
                   help="text a line must contain (repeatable)")
    p.add_argument("--match-regex", action="append", default=[], metavar="PATTERN",
                   help="regular expression a line must match (repeatable)")
    p.add_argument("--match-file", action="append", default=[], metavar="PATH",
                   help="file of patterns, one per line, /regex/ for a regular "
                        "expression (repeatable)")
    p.add_argument("--interval", type=int, default=0, metavar="SEC",
                   help="0 sends each match at once, N collects into one "
                        "message every N seconds")
    p.add_argument("--pipe", metavar="PATH",
                   help="program run once per matched line, its stdout is sent")
    p.add_argument("--propagation-node", metavar="HASH",
                   help="LXMF propagation node to use when direct delivery fails")
    p.add_argument("--name", default="lxmfnotify",
                   help="display name announced for this sender")
    p.add_argument("--config", default=os.path.expanduser("~/.lxmfnotify"),
                   metavar="DIR", help="identity and LXMF storage")
    p.add_argument("--rnsconfig", metavar="DIR",
                   help="path to alternative Reticulum config directory")
    p.add_argument("--no-announce", action="store_true",
                   help="do not announce this sender's address")
    p.add_argument("--verbose", action="store_true",
                   help="match, send and delivery events on stderr")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)

    addresses = parse_hashes(args.address)
    node = parse_hashes(args.propagation_node)[0] if args.propagation_node else None
    if args.interval < 0:
        fail("--interval must be 0 or more")

    patterns = list(args.match)
    regexes = list(args.match_regex)
    for path in args.match_file:
        try:
            p, r = load_pattern_file(path)
        except OSError as e:
            fail("cannot read %s: %s" % (path, e.strerror))
        patterns.extend(p)
        regexes.extend(r)
    if any(p == "" for p in patterns + regexes):
        fail("empty pattern")
    try:
        matcher = Matcher(patterns, regexes)
    except re.error as e:
        fail("invalid regex: %s" % e)

    if args.pipe and not os.access(args.pipe, os.X_OK):
        fail("pipe program not executable: %s" % args.pipe)

    from .sender import Sender
    from .window import Window

    sender = Sender(addresses, args.config, args.rnsconfig, args.name, node,
                    not args.no_announce, args.verbose, log)
    sender.start()

    window = Window(args.interval, sender.send)
    done = threading.Event()
    reader = Reader(sys.stdin.buffer, matcher, args.pipe, window.add,
                    done.set, log, args.verbose)

    def on_signal(signum, frame):
        if done.is_set():
            os._exit(1)
        done.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    reader.start()

    if args.interval > 0:
        start = time.monotonic()
        k = 1
        while not done.is_set():
            wait = start + k * args.interval - time.monotonic()
            if wait > 0 and done.wait(wait):
                break
            window.flush()
            k += 1
    else:
        done.wait()

    window.flush()
    sender.drain()
    sender.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
