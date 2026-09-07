from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
from insightface.app import FaceAnalysis

from .errors import PipelineError
from .models import FaceScan


class FaceDetector:
    """Thin, lazy wrapper around InsightFace's CPU face detector/encoder."""

    def __init__(self, model_name: str = "buffalo_l") -> None:
        self.model_name = model_name
        self._app: FaceAnalysis | None = None

    def _load(self) -> FaceAnalysis:
        if self._app is None:
            try:
                app = FaceAnalysis(
                    name=self.model_name,
                    providers=["CPUExecutionProvider"],
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
            except Exception as exc:
                raise PipelineError(
                    "InsightFace could not load its model. The first run needs "
                    "internet access to download the model files."
                ) from exc
            self._app = app
        return self._app

    def scan(self, image_path: Path) -> FaceScan:
        if not image_path.is_file():
            raise PipelineError(f"Input image does not exist: {image_path}")

        image = cv2.imread(str(image_path))
        if image is None:
            raise PipelineError(f"Could not decode the input image: {image_path}")

        faces = self._load().get(image)
        if not faces:
            raise PipelineError(
                "No face was detected. Use a clear, front-facing image containing "
                "one authorized subject."
            )

        primary = max(faces, key=lambda face: float(face.det_score))
        bbox = [round(float(value), 2) for value in primary.bbox]
        embedding = getattr(primary, "embedding", None)
        dimensions = int(len(embedding)) if embedding is not None else 0

        return FaceScan(
            detected=True,
            face_count=len(faces),
            primary_face_confidence=round(float(primary.det_score), 5),
            bounding_box=bbox,
            embedding_dimensions=dimensions,
            detector=f"InsightFace/{self.model_name}",
        )