# [< id=TEST-001 parent=REQ-001, SRC-001 >>>
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from telemetry import TelemetryPipeline

def test_telemetry_rate_10hz():
    pipe = TelemetryPipeline(rate_hz=10)
    assert pipe.rate_hz == 10


# >]
