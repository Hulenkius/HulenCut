"""Macro / script recording primitives."""
from collections import deque


class ScriptRecorder:
    def __init__(self):
        self.actions = deque()
        self.is_recording = False

    def start(self):
        self.actions.clear()
        self.is_recording = True

    def stop(self):
        self.is_recording = False

    def log_action(self, action, *args):
        if self.is_recording:
            self.actions.append(" ".join([action] + [str(a) for a in args]))
