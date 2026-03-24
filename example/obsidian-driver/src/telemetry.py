# [< id=SRC-001 type=SRC parent=REQ-001 >>>
class TelemetryPipeline:
    def __init__(self, rate_hz=10):
        self.rate_hz = rate_hz

    def push(self, data):
        # Non-blocking push to queue
        pass


# >]
