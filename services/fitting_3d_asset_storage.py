from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path


class Fitting3DAssetStorage:
    """Owns isolated temporary workspaces for one conversion operation."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else None

    def create_workspace(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="fitting-3d-", dir=self.root))

    @staticmethod
    def safe_filename(name: str) -> str:
        if not name or Path(name).name != name or ".." in Path(name).parts:
            raise ValueError("unsafe filename")
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        if safe in {"", ".", ".."}:
            raise ValueError("unsafe filename")
        return safe

    @staticmethod
    def cleanup(workspace: Path) -> None:
        shutil.rmtree(workspace, ignore_errors=True)
