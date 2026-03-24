# [< id=TEST-001 type=TEST parent=REQ-001 parent=SRC-001 >>>
def test_telemetry_rate_10hz():
    pipe = TelemetryPipeline(rate_hz=10)
    assert pipe.rate_hz == 10


# >]
