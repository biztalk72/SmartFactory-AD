"""Anomaly Detection engine using Anomalib.

Supports PatchCore and EfficientAD models. Loads a trained model checkpoint
and runs inference on single images, returning anomaly score + heatmap.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy imports to avoid loading torch at module level
_torch = None
_anomalib = None


def _import_deps():
    global _torch, _anomalib
    if _torch is None:
        import torch
        _torch = torch
    if _anomalib is None:
        import anomalib
        _anomalib = anomalib


@dataclass
class ADResult:
    """Result of anomaly detection inference."""
    anomaly_score: float          # Normalized 0‥1
    is_anomaly: bool
    heatmap: Optional[np.ndarray]  # H×W uint8 heatmap (colormap applied)
    inference_time_ms: float
    model_name: str


class AnomalyDetector:
    """Singleton wrapper around an Anomalib model for inference."""

    _instance: Optional["AnomalyDetector"] = None

    def __init__(self):
        self._model = None
        self._engine = None
        self._model_name: str = ""
        self._device: str = "cpu"
        self._threshold: float = 0.5
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "AnomalyDetector":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def model_name(self) -> str:
        return self._model_name

    def load_model(
        self,
        model_name: str = "patchcore",
        checkpoint_path: Optional[str] = None,
        device: str = "cpu",
        category: str = "bottle",
    ) -> None:
        """Load an Anomalib model for inference.

        If no checkpoint is provided, creates a fresh (untrained) model
        which can still be used for a demo but won't produce meaningful scores.
        """
        _import_deps()
        import torch

        self._device = device
        self._model_name = model_name

        try:
            if checkpoint_path and Path(checkpoint_path).exists():
                # Load from trained checkpoint via Anomalib Engine
                from anomalib.engine import Engine
                from anomalib.models import Patchcore, EfficientAd

                model_cls = Patchcore if model_name == "patchcore" else EfficientAd
                self._model = model_cls.load_from_checkpoint(checkpoint_path)
                self._model.eval()
                self._model.to(torch.device(device))
                self._loaded = True
                logger.info("Loaded %s checkpoint from %s", model_name, checkpoint_path)
            else:
                # Fallback: create default model (demo mode — not trained)
                from anomalib.models import Patchcore, EfficientAd

                model_cls = Patchcore if model_name == "patchcore" else EfficientAd
                self._model = model_cls()
                self._model.eval()
                self._loaded = True
                logger.warning(
                    "No checkpoint found — running %s in DEMO mode (untrained).",
                    model_name,
                )
        except Exception as e:
            logger.error("Failed to load AD model: %s", e)
            self._loaded = False
            raise

    def predict(self, image: Image.Image, threshold: float = 0.5) -> ADResult:
        """Run anomaly detection on a PIL Image.

        Returns ADResult with score, binary decision, and heatmap.
        """
        _import_deps()
        import torch
        import torchvision.transforms.functional as TF

        if not self._loaded or self._model is None:
            raise RuntimeError("AD model not loaded. Call load_model() first.")

        start = time.perf_counter()

        # Preprocess
        img_tensor = TF.to_tensor(image.convert("RGB").resize((256, 256)))
        img_tensor = img_tensor.unsqueeze(0)  # batch dim

        # Inference
        with torch.no_grad():
            try:
                output = self._model(img_tensor)
            except Exception:
                # Fallback for untrained demo model
                return ADResult(
                    anomaly_score=0.0,
                    is_anomaly=False,
                    heatmap=None,
                    inference_time_ms=(time.perf_counter() - start) * 1000,
                    model_name=self._model_name,
                )

        elapsed = (time.perf_counter() - start) * 1000

        # Extract score
        if hasattr(output, "pred_score"):
            score = float(output.pred_score.cpu().item())
        elif isinstance(output, dict) and "pred_score" in output:
            score = float(output["pred_score"].cpu().item())
        else:
            score = 0.0

        # Clamp to 0‥1
        score = max(0.0, min(1.0, score))

        # Extract anomaly map for heatmap
        heatmap = None
        anomaly_map = None
        if hasattr(output, "anomaly_map"):
            anomaly_map = output.anomaly_map
        elif isinstance(output, dict) and "anomaly_map" in output:
            anomaly_map = output["anomaly_map"]

        if anomaly_map is not None:
            heatmap = self._anomaly_map_to_heatmap(anomaly_map)

        return ADResult(
            anomaly_score=score,
            is_anomaly=score >= threshold,
            heatmap=heatmap,
            inference_time_ms=elapsed,
            model_name=self._model_name,
        )

    @staticmethod
    def _anomaly_map_to_heatmap(anomaly_map) -> np.ndarray:
        """Convert anomaly map tensor to a colorized uint8 heatmap."""
        import cv2

        amap = anomaly_map.squeeze().cpu().numpy()
        # Normalize to 0‥255
        amap_min, amap_max = amap.min(), amap.max()
        if amap_max - amap_min > 1e-6:
            amap = (amap - amap_min) / (amap_max - amap_min)
        else:
            amap = np.zeros_like(amap)
        amap_uint8 = (amap * 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(amap_uint8, cv2.COLORMAP_JET)
        return heatmap

    def predict_from_bytes(self, image_bytes: bytes, threshold: float = 0.5) -> ADResult:
        """Convenience: run prediction from raw image bytes."""
        image = Image.open(io.BytesIO(image_bytes))
        return self.predict(image, threshold=threshold)


def heatmap_to_bytes(heatmap: np.ndarray, fmt: str = "png") -> bytes:
    """Convert numpy heatmap to PNG bytes."""
    img = Image.fromarray(heatmap[..., ::-1])  # BGR→RGB
    buf = io.BytesIO()
    img.save(buf, format=fmt.upper())
    return buf.getvalue()
