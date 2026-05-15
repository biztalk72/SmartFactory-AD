"""Integration tests for the inference router (POST /api/v1/inspect)."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio
from PIL import Image

from app.services.ad_engine import ADResult
from app.services.vlm_service import VLMResult


# ── Helpers ──


def _make_png_bytes(w: int = 64, h: int = 64) -> bytes:
    arr = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_heatmap(w: int = 64, h: int = 64) -> np.ndarray:
    return np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)


# ── Test class ──


class TestInferenceEndpoint:
    """Tests for run_inspection() via direct function call with mocked deps."""

    @pytest.mark.asyncio
    async def test_normal_image_no_vlm_call(self, mock_db):
        """When AD says normal, VLM should NOT be called."""
        from app.routers.inference import run_inspection

        ad_result = ADResult(
            anomaly_score=0.1, is_anomaly=False, heatmap=None,
            inference_time_ms=30.0, model_name="patchcore",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = True
        mock_det.predict.return_value = ad_result

        mock_vlm = MagicMock()

        image_bytes = _make_png_bytes()
        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=image_bytes)
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService") as vlm_cls, \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            ad_cls.get_instance.return_value = mock_det
            vlm_cls.get_instance.return_value = mock_vlm

            resp = await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="bottle",
                lot_number="LOT001",
                serial_number="",
                skip_vlm=False,
                db=mock_db,
            )

        assert resp.anomaly_score == pytest.approx(0.1)
        assert resp.is_anomaly is False
        assert resp.vlm_explanation is None
        # VLM should not have been called
        mock_vlm.explain.assert_not_called()
        # DB should have 1 add (InspectionResult only, no VLMExplanation)
        assert mock_db.add.call_count == 1
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_anomaly_image_triggers_vlm(self, mock_db):
        """When AD says anomaly, VLM should be called and result persisted."""
        from app.routers.inference import run_inspection

        heatmap = _make_heatmap()
        ad_result = ADResult(
            anomaly_score=0.85, is_anomaly=True, heatmap=heatmap,
            inference_time_ms=55.0, model_name="patchcore",
        )
        vlm_result = VLMResult(
            defect_type="scratch", location="center", severity="HIGH",
            cause="worn tool", recommended_action="replace tool",
            full_explanation="Scratch at center.", vlm_model="stub-test",
            generation_time_ms=120.0, raw_response="{}",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = True
        mock_det.predict.return_value = ad_result

        mock_vlm = MagicMock()
        mock_vlm.explain.return_value = vlm_result

        image_bytes = _make_png_bytes()
        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=image_bytes)
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService") as vlm_cls, \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            ad_cls.get_instance.return_value = mock_det
            vlm_cls.get_instance.return_value = mock_vlm

            resp = await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="bottle",
                lot_number="",
                serial_number="SN42",
                skip_vlm=False,
                db=mock_db,
            )

        assert resp.anomaly_score == pytest.approx(0.85)
        assert resp.is_anomaly is True
        assert resp.vlm_explanation is not None
        assert resp.vlm_explanation.defect_type == "scratch"
        assert resp.vlm_explanation.severity == "HIGH"
        assert resp.vlm_explanation.vlm_model == "stub-test"
        # VLM was called
        mock_vlm.explain.assert_called_once()
        # DB should have 2 adds (InspectionResult + VLMExplanation)
        assert mock_db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_skip_vlm_flag(self, mock_db):
        """When skip_vlm=True, VLM should NOT be called even for anomalies."""
        from app.routers.inference import run_inspection

        ad_result = ADResult(
            anomaly_score=0.9, is_anomaly=True, heatmap=_make_heatmap(),
            inference_time_ms=40.0, model_name="patchcore",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = True
        mock_det.predict.return_value = ad_result

        mock_vlm = MagicMock()

        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=_make_png_bytes())
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService") as vlm_cls, \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            ad_cls.get_instance.return_value = mock_det
            vlm_cls.get_instance.return_value = mock_vlm

            resp = await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="bottle",
                lot_number="",
                serial_number="",
                skip_vlm=True,
                db=mock_db,
            )

        assert resp.is_anomaly is True
        assert resp.vlm_explanation is None
        mock_vlm.explain.assert_not_called()
        assert mock_db.add.call_count == 1  # Only InspectionResult

    @pytest.mark.asyncio
    async def test_empty_file_raises_400(self, mock_db):
        """Empty upload should raise HTTPException 400."""
        from fastapi import HTTPException
        from app.routers.inference import run_inspection

        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=b"")
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector"), \
             patch("app.routers.inference.VLMService"), \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            with pytest.raises(HTTPException) as exc_info:
                await run_inspection(
                    file=upload_file,
                    station_id=None,
                    threshold=0.5,
                    category="test",
                    lot_number="",
                    serial_number="",
                    skip_vlm=False,
                    db=mock_db,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(self, mock_db):
        """Verify all required fields are present in the response."""
        from app.routers.inference import run_inspection

        ad_result = ADResult(
            anomaly_score=0.3, is_anomaly=False, heatmap=None,
            inference_time_ms=20.0, model_name="efficientad",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = True
        mock_det.predict.return_value = ad_result

        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=_make_png_bytes())
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService"), \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            ad_cls.get_instance.return_value = mock_det

            resp = await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="test",
                lot_number="",
                serial_number="",
                skip_vlm=False,
                db=mock_db,
            )

        assert resp.id  # non-empty UUID string
        assert resp.model_name == "efficientad"
        assert resp.inference_time_ms == 20.0
        assert resp.image_path  # non-empty
        assert resp.created_at is not None

    @pytest.mark.asyncio
    async def test_heatmap_stored_when_present(self, mock_db):
        """Heatmap path should be non-empty when AD produces a heatmap."""
        from app.routers.inference import run_inspection

        ad_result = ADResult(
            anomaly_score=0.7, is_anomaly=True, heatmap=_make_heatmap(),
            inference_time_ms=45.0, model_name="patchcore",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = True
        mock_det.predict.return_value = ad_result

        mock_vlm = MagicMock()
        mock_vlm.explain.return_value = VLMResult(vlm_model="stub")

        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=_make_png_bytes())
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService") as vlm_cls, \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n):
            ad_cls.get_instance.return_value = mock_det
            vlm_cls.get_instance.return_value = mock_vlm

            resp = await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="bottle",
                lot_number="",
                serial_number="",
                skip_vlm=False,
                db=mock_db,
            )

        assert resp.heatmap_path != ""
        assert "heatmap" in resp.heatmap_path

    @pytest.mark.asyncio
    async def test_ad_model_lazy_loads_when_not_loaded(self, mock_db):
        """AD model should be loaded on first call if not already loaded."""
        from app.routers.inference import run_inspection

        ad_result = ADResult(
            anomaly_score=0.0, is_anomaly=False, heatmap=None,
            inference_time_ms=10.0, model_name="patchcore",
        )

        mock_det = MagicMock()
        mock_det.is_loaded = False  # Not loaded yet
        mock_det.predict.return_value = ad_result

        upload_file = MagicMock()
        upload_file.read = AsyncMock(return_value=_make_png_bytes())
        upload_file.content_type = "image/png"

        with patch("app.routers.inference.AnomalyDetector") as ad_cls, \
             patch("app.routers.inference.VLMService"), \
             patch("app.routers.inference._try_upload", side_effect=lambda n, *a, **k: n), \
             patch("app.core.config.get_settings") as mock_settings:
            ad_cls.get_instance.return_value = mock_det
            s = MagicMock()
            s.ad_model = "patchcore"
            s.ad_checkpoint_path = ""
            s.ad_device = "cpu"
            mock_settings.return_value = s

            await run_inspection(
                file=upload_file,
                station_id=None,
                threshold=0.5,
                category="test",
                lot_number="",
                serial_number="",
                skip_vlm=True,
                db=mock_db,
            )

        mock_det.load_model.assert_called_once_with(
            model_name="patchcore",
            checkpoint_path=None,
            device="cpu",
        )
