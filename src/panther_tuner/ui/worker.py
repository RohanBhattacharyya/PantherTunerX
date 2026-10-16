"""A single ordered I/O worker: no overlapping writes or unbounded telemetry queue."""

import queue

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    completed = Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.jobs = queue.Queue()

    def submit(self, fn, callback):
        self.jobs.put((fn, callback))

    def run(self):
        while True:
            job = self.jobs.get()
            if job is None:
                return
            fn, callback = job
            try:
                result = fn()
                self.completed.emit(callback, result, None)
            except Exception as e:
                self.completed.emit(callback, None, e)

    def stop(self, cleanup):
        # Skip queued reads when shutting down; the in-flight request has a timeout.
        while True:
            try:
                self.jobs.get_nowait()
            except queue.Empty:
                break
        self.jobs.put((cleanup, lambda *_: None))
        self.jobs.put(None)
