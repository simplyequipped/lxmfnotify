# Reticulum, the LXMF router, recipient resolution and delivery.
#
# simplyequipped

import os
import random
import sys
import threading
import time

import RNS
import LXMF

RESOLVE_WAIT = 30       # seconds to wait for a path at startup
DRAIN_WAIT = 30         # seconds to wait for pending deliveries at exit
QUEUE_MAX = 100         # results held per unresolved address
ANNOUNCE_MIN = 90 * 60  # nnounce at a random interval between 90 and 300 minutes
ANNOUNCE_MAX = 300 * 60


class Recipient:
    def __init__(self, dest_hash):
        self.hash = dest_hash
        self.dest = None
        self.queue = []

    def name(self):
        return RNS.prettyhexrep(self.hash)


class Sender:
    def __init__(self, addresses, config_dir, rns_config, name, propagation_node,
                 announce, verbose, log):
        self.recipients = [Recipient(a) for a in addresses]
        self.config_dir = config_dir
        self.rns_config = rns_config
        self.name = name
        self.propagation_node = propagation_node
        self.announce = announce
        self.verbose = verbose
        self.log = log
        self.pending = set()
        self.lock = threading.Lock()
        self.stopping = False

    def start(self):
        os.makedirs(self.config_dir, mode=0o700, exist_ok=True)

        # RNS logs with print(). stdout is the pipeline's, so everything
        # printed in this process goes to stderr.
        sys.stdout = sys.stderr
        RNS.Reticulum(configdir=self.rns_config, loglevel=RNS.LOG_NOTICE if self.verbose else RNS.LOG_ERROR)

        path = os.path.join(self.config_dir, "identity")
        if os.path.isfile(path):
            self.identity = RNS.Identity.from_file(path)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(path)

        self.router = LXMF.LXMRouter(identity=self.identity, storagepath=os.path.join(self.config_dir, "lxmf"))
        self.source = self.router.register_delivery_identity(self.identity, display_name=self.name)
        if self.propagation_node:
            self.router.set_outbound_propagation_node(self.propagation_node)

        if self.announce:
            self.router.announce(self.source.hash)
            threading.Thread(target=self._announce_loop, daemon=True).start()

        for r in self.recipients:
            self.resolve(r, RESOLVE_WAIT)

    def _announce_loop(self):
        while not self.stopping:
            time.sleep(random.uniform(ANNOUNCE_MIN, ANNOUNCE_MAX))
            if not self.stopping:
                self.router.announce(self.source.hash)
                if self.verbose:
                    self.log("announced " + RNS.prettyhexrep(self.source.hash))

    def resolve(self, r, wait=0):
        if r.dest:
            return True
        identity = RNS.Identity.recall(r.hash)
        if identity is None:
            RNS.Transport.request_path(r.hash)
            deadline = time.time() + wait
            while identity is None and time.time() < deadline:
                time.sleep(0.5)
                if RNS.Transport.has_path(r.hash):
                    identity = RNS.Identity.recall(r.hash)
        if identity is None:
            self.log("no path to %s yet" % r.name())
            return False
        r.dest = RNS.Destination(identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
        return True

    def send(self, text):
        for r in self.recipients:
            if not self.resolve(r):
                r.queue.append(text)
                del r.queue[:-QUEUE_MAX]
                continue
            queued, r.queue = r.queue, []
            for t in queued:
                self._send_one(r, t)
            self._send_one(r, text)

    def _send_one(self, r, text):
        lxm = LXMF.LXMessage(r.dest, self.source, text, desired_method=LXMF.LXMessage.DIRECT)
        lxm.register_delivery_callback(self._delivered)
        lxm.register_failed_callback(self._failed)
        lxm.retry_propagated = bool(self.propagation_node)
        with self.lock:
            self.pending.add(lxm)
        if self.verbose:
            self.log("sending %d bytes to %s" % (len(text.encode("utf-8")), r.name()))
        self.router.handle_outbound(lxm)

    def _delivered(self, lxm):
        with self.lock:
            self.pending.discard(lxm)
        if self.verbose:
            self.log("delivered to " + RNS.prettyhexrep(lxm.destination_hash))

    def _failed(self, lxm):
        if lxm.retry_propagated:
            # resend the same message through the propagation node
            lxm.retry_propagated = False
            lxm.delivery_attempts = 0
            if hasattr(lxm, "next_delivery_attempt"):
                del lxm.next_delivery_attempt
            lxm.packed = None
            lxm.desired_method = LXMF.LXMessage.PROPAGATED
            if self.verbose:
                self.log("direct delivery to %s failed, sending via propagation node" % RNS.prettyhexrep(lxm.destination_hash))
            self.router.handle_outbound(lxm)
            return
        with self.lock:
            self.pending.discard(lxm)
        self.log("delivery to %s failed, message dropped" % RNS.prettyhexrep(lxm.destination_hash))

    def drain(self, timeout=DRAIN_WAIT):
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.lock:
                if not self.pending:
                    return True
            time.sleep(0.5)
        with self.lock:
            n = len(self.pending)
        if n:
            self.log("%d message(s) still pending at exit" % n)
        return False

    def shutdown(self):
        self.stopping = True
        self.router.exit_handler()
