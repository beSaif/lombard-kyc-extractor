"""Record what every pipeline step received and produced, so a run can be replayed step by step.

Each step stores its inputs and outputs (`data`), how long it took, and `code`: the dotted names of the
functions that did the work, which the web UI resolves to their source.
"""

import time
from contextlib import contextmanager
from pathlib import Path

import cv2
import numpy as np


class Trace:
    def __init__(self, artifact_dir: Path | None = None, url_prefix: str = ""):
        self.steps: list[dict] = []
        self.artifact_dir = artifact_dir
        self.url_prefix = url_prefix

    @contextmanager
    def step(self, kind: str, title: str, *, doc: str | None = None, code: tuple[str, ...] = (),
             explain: str = ""):
        rec = {"id": len(self.steps), "kind": kind, "title": title, "doc": doc, "code": list(code),
               "explain": explain, "status": "ok", "ms": None, "data": {}}
        self.steps.append(rec)
        start = time.perf_counter()
        try:
            yield rec["data"]
        except Exception as e:
            rec["status"] = "error"
            rec["data"]["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            rec["ms"] = round((time.perf_counter() - start) * 1000, 1)

    def image(self, name: str, img: np.ndarray | None, max_side: int = 1400) -> str | None:
        """Save an image for the UI and return its URL (None when tracing to memory only)."""
        if img is None or self.artifact_dir is None:
            return None
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        scale = min(1.0, max_side / max(img.shape[:2]))
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(self.artifact_dir / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return f"{self.url_prefix}/{name}.jpg"

