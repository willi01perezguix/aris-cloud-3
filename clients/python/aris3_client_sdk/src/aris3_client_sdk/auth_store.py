from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_dir

from .models import SessionData


@dataclass
class AuthStore:
    app_name: str = "aris3"
    filename: str = "session.json"

    def _path(self) -> Path:
        base = Path(user_data_dir(self.app_name, "ARIS"))
        base.mkdir(parents=True, exist_ok=True)
        return base / self.filename

    def save(self, session: SessionData) -> None:
        path = self._path()
        data = session.model_dump()
        path.write_text(json.dumps(data, indent=2))
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def load(self) -> SessionData | None:
        path = self._path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            self.clear()
            return None
        try:
            return SessionData(**data)
        except Exception:
            self.clear()
            return None

    def clear(self) -> None:
        path = self._path()
        if path.exists():
            path.unlink()
