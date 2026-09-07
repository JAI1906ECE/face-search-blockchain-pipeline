from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .blockchain import LocalBlockchain, sha256_json
from .face import FaceDetector
from .models import AnchorRecord, FaceScan, SearchResult
from .search import GoogleLensSearch


class FaceSearchPipeline:
    def __init__(self, chain: LocalBlockchain) -> None:
        self.chain = chain
        self.face_detector = FaceDetector()
        self.search_provider = GoogleLensSearch()

    def run(self, image_path: Path) -> tuple[FaceScan, tuple[SearchResult, ...], AnchorRecord]:
        face_scan = self.face_detector.scan(image_path)
        search_results = self.search_provider.search(image_path)
        best_result = search_results[0]
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        payload: dict[str, Any] = {
            "input_image": {
                "file_name": image_path.name,
                "sha256": image_hash,
            },
            "face_scan": face_scan.to_dict(),
            "matching_post": best_result.to_dict(),
            "search_result_count": len(search_results),
            "fingerprint_algorithm": "SHA-256 over canonical JSON metadata",
        }
        payload["fingerprint"] = sha256_json(payload)
        record = self.chain.anchor(payload)
        self.chain.save_payload(record)
        return face_scan, search_results, record