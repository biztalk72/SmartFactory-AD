"""Vision-Language Model service for defect explanation.

Supports two backends:
  - "openai"  : OpenAI GPT-4o Vision API
  - "local"   : HuggingFace Transformers (Qwen2.5-VL or similar)

Given a defect image + anomaly heatmap, produces a structured natural-language
explanation covering defect type, location, severity, root cause, and
recommended corrective action.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── System prompt shared across backends ──

SYSTEM_PROMPT = """\
You are an expert manufacturing quality inspector AI.
You will receive an image from a production line and a heatmap highlighting anomalous regions.

Analyze the image and provide a structured JSON response with the following fields:
{
  "defect_type": "<type of defect: scratch, dent, contamination, missing_part, misalignment, discoloration, crack, other>",
  "location": "<where on the product the defect is located, e.g. top-left surface, center edge>",
  "severity": "<LOW | MEDIUM | HIGH | CRITICAL>",
  "cause": "<probable root cause of the defect>",
  "recommended_action": "<what corrective or preventive action should be taken>",
  "explanation": "<1-2 sentence natural language summary of the finding>"
}

Respond ONLY with valid JSON. Do not include markdown fencing."""

USER_PROMPT_TEMPLATE = """\
Product category: {category}
Anomaly score: {score:.3f} (threshold: {threshold:.3f})

The first image is the original inspection photo.
{heatmap_note}
Please analyze and provide a structured defect report."""


@dataclass
class VLMResult:
    """Parsed VLM explanation."""
    defect_type: str = ""
    location: str = ""
    severity: str = ""
    cause: str = ""
    recommended_action: str = ""
    full_explanation: str = ""
    vlm_model: str = ""
    generation_time_ms: float = 0.0
    raw_response: str = ""


class VLMService:
    """Facade for VLM inference."""

    _instance: Optional["VLMService"] = None

    def __init__(self):
        self._provider: str = ""
        self._openai_client = None
        self._local_model = None
        self._local_processor = None

    @classmethod
    def get_instance(cls) -> "VLMService":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_provider()
        return cls._instance

    def _init_provider(self) -> None:
        settings = get_settings()
        self._provider = settings.vlm_provider

        if self._provider == "openai" and settings.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.openai_api_key)
                logger.info("VLM provider: OpenAI (GPT-4o)")
            except ImportError:
                logger.warning("openai package not installed, falling back to stub")
                self._provider = "stub"
        elif self._provider == "local":
            logger.info("VLM provider: local (lazy-loaded on first call)")
        else:
            logger.info("VLM provider: stub (no API key configured)")
            self._provider = "stub"

    # ── Public API ──

    def explain(
        self,
        image: Image.Image,
        heatmap: Optional[Image.Image],
        category: str = "unknown",
        anomaly_score: float = 0.0,
        threshold: float = 0.5,
    ) -> VLMResult:
        """Generate a defect explanation for the given image."""

        if self._provider == "openai":
            return self._explain_openai(image, heatmap, category, anomaly_score, threshold)
        elif self._provider == "local":
            return self._explain_local(image, heatmap, category, anomaly_score, threshold)
        else:
            return self._explain_stub(category, anomaly_score)

    # ── OpenAI backend ──

    def _explain_openai(
        self,
        image: Image.Image,
        heatmap: Optional[Image.Image],
        category: str,
        score: float,
        threshold: float,
    ) -> VLMResult:
        start = time.perf_counter()

        content_parts = []
        # User text
        heatmap_note = "The second image is the anomaly heatmap (red = more anomalous)." if heatmap else ""
        user_text = USER_PROMPT_TEMPLATE.format(
            category=category, score=score, threshold=threshold, heatmap_note=heatmap_note,
        )
        content_parts.append({"type": "text", "text": user_text})

        # Original image
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{self._img_to_b64(image)}"},
        })

        # Heatmap
        if heatmap:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{self._img_to_b64(heatmap)}"},
            })

        try:
            resp = self._openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content_parts},
                ],
                max_tokens=500,
                temperature=0.2,
            )
            raw = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("OpenAI VLM call failed: %s", e)
            raw = ""

        elapsed = (time.perf_counter() - start) * 1000
        return self._parse_response(raw, "gpt-4o", elapsed)

    # ── Local Transformers backend ──

    def _explain_local(
        self,
        image: Image.Image,
        heatmap: Optional[Image.Image],
        category: str,
        score: float,
        threshold: float,
    ) -> VLMResult:
        start = time.perf_counter()

        if self._local_model is None:
            self._load_local_model()

        if self._local_model is None:
            return self._explain_stub(category, score)

        heatmap_note = "The second image is the anomaly heatmap." if heatmap else ""
        user_text = USER_PROMPT_TEMPLATE.format(
            category=category, score=score, threshold=threshold, heatmap_note=heatmap_note,
        )

        prompt = f"{SYSTEM_PROMPT}\n\nUser:\n{user_text}"

        try:
            images = [image]
            if heatmap:
                images.append(heatmap)

            inputs = self._local_processor(
                text=prompt, images=images, return_tensors="pt"
            ).to(self._local_model.device)

            import torch
            with torch.no_grad():
                output_ids = self._local_model.generate(**inputs, max_new_tokens=500)

            raw = self._local_processor.batch_decode(
                output_ids[:, inputs["input_ids"].shape[1]:],
                skip_special_tokens=True,
            )[0].strip()
        except Exception as e:
            logger.error("Local VLM inference failed: %s", e)
            raw = ""

        elapsed = (time.perf_counter() - start) * 1000
        model_name = getattr(self._local_model, "name_or_path", "local-vlm")
        return self._parse_response(raw, model_name, elapsed)

    def _load_local_model(self) -> None:
        """Lazy-load a local VLM (Qwen2.5-VL-7B-Instruct as default)."""
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            import torch

            model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
            device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading local VLM: %s on %s ...", model_id, device)
            self._local_processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
            self._local_model = AutoModelForVision2Seq.from_pretrained(
                model_id,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
                trust_remote_code=True,
            )
            if device == "cpu":
                self._local_model.to(device)
            logger.info("Local VLM loaded.")
        except Exception as e:
            logger.error("Failed to load local VLM: %s", e)
            self._local_model = None

    # ── Stub backend (fallback) ──

    @staticmethod
    def _explain_stub(category: str, score: float) -> VLMResult:
        severity = "CRITICAL" if score > 0.8 else "HIGH" if score > 0.6 else "MEDIUM"
        return VLMResult(
            defect_type="unknown",
            location="unspecified",
            severity=severity,
            cause="Automated analysis unavailable — VLM not configured.",
            recommended_action="Manual inspection recommended.",
            full_explanation=(
                f"Anomaly detected on '{category}' product with score {score:.3f}. "
                "Configure VLM_PROVIDER and API key for detailed AI-powered explanation."
            ),
            vlm_model="stub",
            generation_time_ms=0.0,
            raw_response="",
        )

    # ── Helpers ──

    @staticmethod
    def _img_to_b64(image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def _parse_response(raw: str, model: str, elapsed_ms: float) -> VLMResult:
        """Parse JSON response from VLM into VLMResult."""
        result = VLMResult(vlm_model=model, generation_time_ms=elapsed_ms, raw_response=raw)

        if not raw:
            result.full_explanation = "VLM returned empty response."
            return result

        # Try to parse JSON
        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)
            result.defect_type = data.get("defect_type", "")
            result.location = data.get("location", "")
            result.severity = data.get("severity", "")
            result.cause = data.get("cause", "")
            result.recommended_action = data.get("recommended_action", "")
            result.full_explanation = data.get("explanation", raw)
        except (json.JSONDecodeError, AttributeError):
            # If not valid JSON, use raw text as explanation
            result.full_explanation = raw

        return result
