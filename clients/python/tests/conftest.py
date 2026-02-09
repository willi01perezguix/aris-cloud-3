from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SDK_SRC = BASE_DIR / "aris3_client_sdk" / "src"
CORE_SRC = BASE_DIR / "aris_core_3_app" / "src"
CONTROL_SRC = BASE_DIR / "aris_control_center_app" / "src"

for path in (SDK_SRC, CORE_SRC, CONTROL_SRC):
    sys.path.insert(0, str(path))
