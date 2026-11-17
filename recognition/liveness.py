import math
import time


class TemporalLiveness:
    """Academic-level multi-frame consistency and motion check."""

    def __init__(self, required_frames=2, ttl_seconds=2.5):
        self.required_frames = required_frames
        self.ttl_seconds = ttl_seconds
        self._tracks = {}

    def observe(self, session_id, face_index, box):
        now = time.monotonic()
        key = (session_id, face_index)
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        previous = self._tracks.get(key)
        if previous is None or now - previous["time"] > self.ttl_seconds:
            self._tracks[key] = {"time": now, "center": center, "frames": 1, "moved": False}
            return False
        distance = math.dist(center, previous["center"])
        moved = previous["moved"] or distance >= 1.0
        frames = previous["frames"] + 1
        self._tracks[key] = {"time": now, "center": center, "frames": frames, "moved": moved}
        return frames >= self.required_frames and moved


liveness = TemporalLiveness()
