"""Shared test fixtures for SmartFactory-AD backend tests."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.services.ad_engine import ADResult


# ── Image Factories ──


@pytest.fixture
def rgb_image() -> Image.Image:
    """Create a simple 256×256 RGB test image."""
    arr = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


@pytest.fixture
def rgb_image_bytes(rgb_image) -> bytes:
    """PNG bytes of the test image."""
    buf = io.BytesIO()
    rgb_image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_heatmap() -> np.ndarray:
    """A synthetic 256×256×3 BGR heatmap array (like cv2.applyColorMap output)."""
    return np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)


# ── AD Engine Mocks ──


@pytest.fixture
def normal_ad_result() -> ADResult:
    """AD result representing a normal (non-anomalous) product."""
    return ADResult(
        anomaly_score=0.1,
        is_anomaly=False,
        heatmap=None,
        inference_time_ms=42.0,
        model_name="patchcore",
    )


@pytest.fixture
def anomaly_ad_result(sample_heatmap) -> ADResult:
    """AD result representing a defective product."""
    return ADResult(
        anomaly_score=0.85,
        is_anomaly=True,
        heatmap=sample_heatmap,
        inference_time_ms=55.0,
        model_name="patchcore",
    )


@pytest.fixture
def mock_detector_normal(normal_ad_result):
    """Patch AnomalyDetector singleton to return a normal result."""
    detector = MagicMock()
    detector.is_loaded = True
    detector.model_name = "patchcore"
    detector.predict.return_value = normal_ad_result
    with patch("app.routers.inference.AnomalyDetector") as cls:
        cls.get_instance.return_value = detector
        yield detector


@pytest.fixture
def mock_detector_anomaly(anomaly_ad_result):
    """Patch AnomalyDetector singleton to return an anomaly result."""
    detector = MagicMock()
    detector.is_loaded = True
    detector.model_name = "patchcore"
    detector.predict.return_value = anomaly_ad_result
    with patch("app.routers.inference.AnomalyDetector") as cls:
        cls.get_instance.return_value = detector
        yield detector


# ── VLM Service Mock ──


@pytest.fixture
def mock_vlm_service():
    """Patch VLMService singleton to return a stub explanation."""
    from app.services.vlm_service import VLMResult

    vlm = MagicMock()
    vlm.explain.return_value = VLMResult(
        defect_type="scratch",
        location="top-left surface",
        severity="HIGH",
        cause="Tooling wear on press die",
        recommended_action="Replace press die insert",
        full_explanation="A linear scratch defect on the top-left surface.",
        vlm_model="stub-test",
        generation_time_ms=100.0,
        raw_response="{}",
    )
    with patch("app.routers.inference.VLMService") as cls:
        cls.get_instance.return_value = vlm
        yield vlm


# ── Storage Mock ──


@pytest.fixture(autouse=True)
def mock_storage():
    """Auto-mock MinIO storage so tests never hit a real bucket."""
    with patch("app.routers.inference._try_upload", side_effect=lambda name, *a, **k: name):
        yield


# ── Database Mock ──


@pytest.fixture
def mock_db():
    """Async mock for SQLAlchemy session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session
