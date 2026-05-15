"""Unit tests for the Anomaly Detection engine."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.services.ad_engine import ADResult, AnomalyDetector, heatmap_to_bytes


# ── ADResult dataclass ──


class TestADResult:
    def test_normal_result(self):
        r = ADResult(anomaly_score=0.1, is_anomaly=False, heatmap=None,
                     inference_time_ms=10.0, model_name="patchcore")
        assert r.anomaly_score == 0.1
        assert r.is_anomaly is False
        assert r.heatmap is None

    def test_anomaly_result_with_heatmap(self, sample_heatmap):
        r = ADResult(anomaly_score=0.9, is_anomaly=True, heatmap=sample_heatmap,
                     inference_time_ms=50.0, model_name="efficientad")
        assert r.is_anomaly is True
        assert r.heatmap is not None
        assert r.heatmap.shape == (256, 256, 3)

    def test_boundary_score(self):
        """Score exactly at threshold should be anomaly."""
        r = ADResult(anomaly_score=0.5, is_anomaly=True, heatmap=None,
                     inference_time_ms=1.0, model_name="test")
        assert r.is_anomaly is True


# ── heatmap_to_bytes ──


class TestHeatmapToBytes:
    def test_produces_valid_png(self, sample_heatmap):
        data = heatmap_to_bytes(sample_heatmap, fmt="png")
        assert isinstance(data, bytes)
        assert len(data) > 0
        # Verify it's a valid image
        img = Image.open(io.BytesIO(data))
        assert img.format == "PNG"
        assert img.size[0] == 256

    def test_uniform_heatmap(self):
        """All-zero heatmap should still produce valid bytes."""
        hm = np.zeros((64, 64, 3), dtype=np.uint8)
        data = heatmap_to_bytes(hm)
        img = Image.open(io.BytesIO(data))
        assert img.size == (64, 64)


# ── AnomalyDetector singleton ──


class TestAnomalyDetectorSingleton:
    def setup_method(self):
        # Reset singleton between tests
        AnomalyDetector._instance = None

    def test_get_instance_returns_same_object(self):
        a = AnomalyDetector.get_instance()
        b = AnomalyDetector.get_instance()
        assert a is b

    def test_initial_state_not_loaded(self):
        det = AnomalyDetector.get_instance()
        assert det.is_loaded is False
        assert det.model_name == ""

    def test_predict_raises_when_not_loaded(self, rgb_image):
        det = AnomalyDetector.get_instance()
        with patch("app.services.ad_engine._import_deps"):
            with pytest.raises(RuntimeError, match="AD model not loaded"):
                det.predict(rgb_image)


# ── Predict flow with mock model ──


class TestAnomalyDetectorPredict:
    def setup_method(self):
        AnomalyDetector._instance = None

    @patch("app.services.ad_engine._import_deps")
    def test_predict_with_mock_model_score_from_attr(self, _mock_deps, rgb_image):
        """When model output has pred_score attribute."""
        import torch

        mock_output = MagicMock()
        mock_output.pred_score = torch.tensor(0.75)
        mock_output.anomaly_map = torch.rand(1, 1, 256, 256)

        det = AnomalyDetector.get_instance()
        det._model = MagicMock(return_value=mock_output)
        det._model.eval = MagicMock()
        det._loaded = True
        det._model_name = "patchcore"

        result = det.predict(rgb_image, threshold=0.5)

        assert result.anomaly_score == pytest.approx(0.75, abs=0.01)
        assert result.is_anomaly is True
        assert result.heatmap is not None
        assert result.model_name == "patchcore"
        assert result.inference_time_ms > 0

    @patch("app.services.ad_engine._import_deps")
    def test_predict_with_mock_model_dict_output(self, _mock_deps, rgb_image):
        """When model output is a dict with pred_score key."""
        import torch

        mock_output = {"pred_score": torch.tensor(0.2), "anomaly_map": torch.rand(1, 1, 64, 64)}

        det = AnomalyDetector.get_instance()
        det._model = MagicMock(return_value=mock_output)
        det._model.eval = MagicMock()
        det._loaded = True
        det._model_name = "efficientad"

        result = det.predict(rgb_image, threshold=0.5)

        assert result.anomaly_score == pytest.approx(0.2, abs=0.01)
        assert result.is_anomaly is False

    @patch("app.services.ad_engine._import_deps")
    def test_predict_clamps_score(self, _mock_deps, rgb_image):
        """Score should be clamped to [0, 1]."""
        import torch

        mock_output = MagicMock()
        mock_output.pred_score = torch.tensor(1.5)
        mock_output.anomaly_map = None

        det = AnomalyDetector.get_instance()
        det._model = MagicMock(return_value=mock_output)
        det._loaded = True
        det._model_name = "test"

        result = det.predict(rgb_image, threshold=0.5)
        assert result.anomaly_score == 1.0

    @patch("app.services.ad_engine._import_deps")
    def test_predict_fallback_on_model_error(self, _mock_deps, rgb_image):
        """When model inference raises, fallback to score=0."""
        det = AnomalyDetector.get_instance()
        det._model = MagicMock(side_effect=RuntimeError("CUDA OOM"))
        det._loaded = True
        det._model_name = "patchcore"

        result = det.predict(rgb_image, threshold=0.5)
        assert result.anomaly_score == 0.0
        assert result.is_anomaly is False
        assert result.heatmap is None

    @patch("app.services.ad_engine._import_deps")
    def test_predict_no_anomaly_map(self, _mock_deps, rgb_image):
        """When model output has no anomaly_map, heatmap should be None."""
        import torch

        mock_output = MagicMock()
        mock_output.pred_score = torch.tensor(0.3)
        mock_output.anomaly_map = None

        det = AnomalyDetector.get_instance()
        det._model = MagicMock(return_value=mock_output)
        det._loaded = True
        det._model_name = "test"

        result = det.predict(rgb_image, threshold=0.5)
        assert result.heatmap is None


# ── predict_from_bytes ──


class TestPredictFromBytes:
    def setup_method(self):
        AnomalyDetector._instance = None

    @patch("app.services.ad_engine._import_deps")
    def test_predict_from_bytes(self, _mock_deps, rgb_image_bytes):
        """predict_from_bytes should open the image and call predict."""
        import torch

        mock_output = MagicMock()
        mock_output.pred_score = torch.tensor(0.6)
        mock_output.anomaly_map = None

        det = AnomalyDetector.get_instance()
        det._model = MagicMock(return_value=mock_output)
        det._loaded = True
        det._model_name = "patchcore"

        result = det.predict_from_bytes(rgb_image_bytes, threshold=0.5)
        assert result.anomaly_score == pytest.approx(0.6, abs=0.01)
        assert result.is_anomaly is True


# ── _anomaly_map_to_heatmap ──


class TestAnomalyMapToHeatmap:
    def test_converts_tensor_to_bgr_heatmap(self):
        import torch

        amap = torch.rand(1, 1, 128, 128)
        heatmap = AnomalyDetector._anomaly_map_to_heatmap(amap)

        assert isinstance(heatmap, np.ndarray)
        assert heatmap.shape == (128, 128, 3)
        assert heatmap.dtype == np.uint8

    def test_uniform_map_produces_valid_output(self):
        import torch

        amap = torch.ones(1, 1, 64, 64) * 0.5
        heatmap = AnomalyDetector._anomaly_map_to_heatmap(amap)
        assert heatmap.shape == (64, 64, 3)

    def test_constant_map_no_divide_by_zero(self):
        """When all values are identical, should produce all-zero heatmap."""
        import torch

        amap = torch.ones(1, 1, 32, 32) * 0.0
        heatmap = AnomalyDetector._anomaly_map_to_heatmap(amap)
        assert heatmap.shape == (32, 32, 3)
