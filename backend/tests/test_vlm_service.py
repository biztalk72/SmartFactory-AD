"""Unit tests for the VLM service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.vlm_service import VLMResult, VLMService


# ── _parse_response ──


class TestParseResponse:
    """Test JSON/text parsing of raw VLM responses."""

    def test_valid_json(self):
        raw = json.dumps({
            "defect_type": "scratch",
            "location": "center",
            "severity": "HIGH",
            "cause": "tool wear",
            "recommended_action": "replace tool",
            "explanation": "A scratch was found.",
        })
        result = VLMService._parse_response(raw, "gpt-4o", 150.0)

        assert result.defect_type == "scratch"
        assert result.location == "center"
        assert result.severity == "HIGH"
        assert result.cause == "tool wear"
        assert result.recommended_action == "replace tool"
        assert result.full_explanation == "A scratch was found."
        assert result.vlm_model == "gpt-4o"
        assert result.generation_time_ms == 150.0

    def test_json_with_markdown_fences(self):
        """VLMs sometimes wrap JSON in ```json ... ``` fences."""
        inner = json.dumps({
            "defect_type": "dent",
            "location": "top-right",
            "severity": "MEDIUM",
            "cause": "impact",
            "recommended_action": "inspect upstream",
            "explanation": "Small dent on top-right corner.",
        })
        raw = f"```json\n{inner}\n```"
        result = VLMService._parse_response(raw, "gpt-4o", 100.0)

        assert result.defect_type == "dent"
        assert result.severity == "MEDIUM"

    def test_json_with_plain_backtick_fences(self):
        inner = json.dumps({"defect_type": "crack", "explanation": "cracked"})
        raw = f"```\n{inner}\n```"
        result = VLMService._parse_response(raw, "model", 50.0)
        assert result.defect_type == "crack"

    def test_invalid_json_uses_raw_as_explanation(self):
        raw = "This is not JSON. The product has a scratch."
        result = VLMService._parse_response(raw, "model", 50.0)

        assert result.defect_type == ""
        assert result.full_explanation == raw

    def test_empty_response(self):
        result = VLMService._parse_response("", "model", 10.0)

        assert result.full_explanation == "VLM returned empty response."
        assert result.vlm_model == "model"

    def test_partial_json_fields(self):
        """JSON with only some fields should fill what's available."""
        raw = json.dumps({"defect_type": "contamination", "severity": "CRITICAL"})
        result = VLMService._parse_response(raw, "model", 25.0)

        assert result.defect_type == "contamination"
        assert result.severity == "CRITICAL"
        assert result.location == ""
        assert result.cause == ""

    def test_preserves_raw_response(self):
        raw = json.dumps({"defect_type": "x"})
        result = VLMService._parse_response(raw, "m", 1.0)
        assert result.raw_response == raw


# ── Stub backend ──


class TestStubBackend:
    def test_stub_high_score_critical(self):
        result = VLMService._explain_stub("bottle", 0.9)

        assert result.severity == "CRITICAL"
        assert result.vlm_model == "stub"
        assert "bottle" in result.full_explanation
        assert "0.900" in result.full_explanation

    def test_stub_medium_score(self):
        result = VLMService._explain_stub("capsule", 0.55)
        assert result.severity == "MEDIUM"

    def test_stub_high_score(self):
        result = VLMService._explain_stub("screw", 0.7)
        assert result.severity == "HIGH"

    def test_stub_always_returns_vlmresult(self):
        result = VLMService._explain_stub("unknown", 0.0)
        assert isinstance(result, VLMResult)
        assert result.defect_type == "unknown"
        assert result.recommended_action == "Manual inspection recommended."


# ── _img_to_b64 ──


class TestImgToB64:
    def test_produces_valid_base64(self, rgb_image):
        import base64

        b64 = VLMService._img_to_b64(rgb_image)
        assert isinstance(b64, str)
        # Should decode without error
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0
        # Should be valid PNG
        img = Image.open(__import__("io").BytesIO(decoded))
        assert img.format == "PNG"


# ── Provider routing ──


class TestProviderRouting:
    def setup_method(self):
        VLMService._instance = None

    def test_stub_provider_when_no_api_key(self, rgb_image):
        """With no API key and provider='openai', should fall back to stub."""
        with patch("app.services.vlm_service.get_settings") as mock_settings:
            s = MagicMock()
            s.vlm_provider = "openai"
            s.openai_api_key = ""
            mock_settings.return_value = s

            svc = VLMService()
            svc._init_provider()

            assert svc._provider == "stub"

    def test_stub_explain_returns_vlmresult(self, rgb_image):
        """Stub provider should produce a valid VLMResult."""
        svc = VLMService()
        svc._provider = "stub"

        result = svc.explain(rgb_image, heatmap=None, category="test", anomaly_score=0.7)

        assert isinstance(result, VLMResult)
        assert result.severity == "HIGH"
        assert result.vlm_model == "stub"

    def test_explain_dispatches_to_openai(self, rgb_image):
        """When provider is 'openai', explain() should call _explain_openai."""
        svc = VLMService()
        svc._provider = "openai"
        svc._explain_openai = MagicMock(return_value=VLMResult(vlm_model="gpt-4o"))

        result = svc.explain(rgb_image, heatmap=None, category="x", anomaly_score=0.8)
        svc._explain_openai.assert_called_once()
        assert result.vlm_model == "gpt-4o"

    def test_explain_dispatches_to_local(self, rgb_image):
        """When provider is 'local', explain() should call _explain_local."""
        svc = VLMService()
        svc._provider = "local"
        svc._explain_local = MagicMock(return_value=VLMResult(vlm_model="qwen"))

        result = svc.explain(rgb_image, heatmap=None, category="x", anomaly_score=0.6)
        svc._explain_local.assert_called_once()
        assert result.vlm_model == "qwen"


# ── Integration: AD result → VLM ──


class TestADtoVLMIntegration:
    """Verify that an AD anomaly result can be fed into VLM stub correctly."""

    def test_anomaly_triggers_vlm_stub(self, rgb_image, anomaly_ad_result):
        svc = VLMService()
        svc._provider = "stub"

        result = svc.explain(
            image=rgb_image,
            heatmap=Image.fromarray(anomaly_ad_result.heatmap[..., ::-1]),
            category="bottle",
            anomaly_score=anomaly_ad_result.anomaly_score,
            threshold=0.5,
        )

        assert isinstance(result, VLMResult)
        assert result.severity == "CRITICAL"  # 0.85 > 0.8
        assert "bottle" in result.full_explanation

    def test_normal_score_through_vlm(self, rgb_image, normal_ad_result):
        svc = VLMService()
        svc._provider = "stub"

        result = svc.explain(
            image=rgb_image,
            heatmap=None,
            category="capsule",
            anomaly_score=normal_ad_result.anomaly_score,
            threshold=0.5,
        )
        # Even a normal score through stub produces MEDIUM
        assert result.severity == "MEDIUM"
