"""One source of paths, independent of CWD and safe for frozen Windows builds."""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
USER_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Logistics"
_default_data = USER_HOME / "database" if FROZEN else RESOURCE_DIR / "database"
DATA_DIR = Path(os.environ.get("LOGISTICS_DATA_DIR", _default_data)).expanduser().resolve()
RUNTIME_DIR = USER_HOME if FROZEN else RESOURCE_DIR / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
APP_VERSION = "2.1.0"
