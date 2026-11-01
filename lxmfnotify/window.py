# Pass results straight through, or collect them for a timed window.
#
# simplyequipped

import threading


class Window:
    # interval 0: send(result) at once. interval N: results collect until
    # flush(), which sends them joined with newlines as one text.

    def __init__(self, interval, send):
        self.interval = interval
        self.send = send
        self.items = []
        self.lock = threading.Lock()

    def add(self, result):
        if self.interval == 0:
            self.send(result)
            return
        with self.lock:
            self.items.append(result)

    def flush(self):
        with self.lock:
            items, self.items = self.items, []
        if items:
            self.send("\n".join(items))
