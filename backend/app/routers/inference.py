"""Inference router — full inspection pipeline.

POST /api/v1/inspect
  1. Upload image
  2. Run Anomaly Detection (AD engine)
  3. Save image + heatmap to MinIO
  4. If anomaly detected → call VLM for explanation
  5. Persist InspectionResult + VLMExplanation to DB
  6. Return combined response
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from PIL import Image

from sqlalchemy import select

from app.core.database import get_db
from app.models.models import InspectionResult, InspectionStation, VLMExplanation, HACCPRecord
from app.services.ad_engine import AnomalyDetector, heatmap_to_bytes
from app.services.vlm_service import VLMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspect", tags=["Inference"])


# ── Response schema ──


class VLMExplanationOut(BaseModel):
    defect_type: str = ""
    location: str = ""
    severity: str = ""
    cause: str = ""
    recommended_action: str = ""
    full_explanation: str = ""
    vlm_model: str = ""
    generation_time_ms: float = 0.0


class InspectionResponse(BaseModel):
    id: str
    station_id: Optional[str] = None
    anomaly_score: float
    is_anomaly: bool
    image_path: str
    heatmap_path: str
    inference_time_ms: float
    model_name: str
    vlm_explanation: Optional[VLMExplanationOut] = None
    created_at: datetime


# ── Helpers ──


def _try_upload(object_name: str, data: bytes, content_type: str = "image/png") -> str:
    """Best-effort upload to MinIO; returns path or empty string on failure."""
    try:
        from app.services.storage import StorageService
        storage = StorageService.get_instance()
        return storage.upload_bytes(object_name, data, content_type)
    except Exception as e:
        logger.warning("MinIO upload failed (%s): %s", object_name, e)
        return object_name  # return logical path even if upload fails


# ── Endpoint ──


@router.post("/", response_model=InspectionResponse)
async def run_inspection(
    file: UploadFile = File(..., description="Inspection image (JPEG/PNG)"),
    station_id: Optional[str] = Form(default=None),
    threshold: float = Form(default=0.5),
    category: str = Form(default="unknown"),
    lot_number: str = Form(default=""),
    serial_number: str = Form(default=""),
    skip_vlm: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
):
    """Run the full inspection pipeline on an uploaded image."""

    # 1. Read image bytes
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result_id = uuid.uuid4()
    ts = datetime.utcnow().strftime("%Y%m%d/%H%M%S")

    # 2. Run AD inference
    detector = AnomalyDetector.get_instance()
    if not detector.is_loaded:
        from app.core.config import get_settings
        settings = get_settings()
        detector.load_model(
            model_name=settings.ad_model,
            checkpoint_path=settings.ad_checkpoint_path or None,
            device=settings.ad_device,
        )

    ad_result = detector.predict(image, threshold=threshold)

    # 3. Upload image + heatmap to storage
    img_key = f"inspections/{ts}/{result_id}/original.png"
    image_path = _try_upload(img_key, image_bytes, content_type=file.content_type or "image/png")

    heatmap_path = ""
    heatmap_pil = None
    if ad_result.heatmap is not None:
        hm_bytes = heatmap_to_bytes(ad_result.heatmap)
        hm_key = f"inspections/{ts}/{result_id}/heatmap.png"
        heatmap_path = _try_upload(hm_key, hm_bytes)
        heatmap_pil = Image.open(io.BytesIO(hm_bytes))

    # 4. Persist InspectionResult
    station_uuid = uuid.UUID(station_id) if station_id else None
    db_result = InspectionResult(
        id=result_id,
        station_id=station_uuid,
        anomaly_score=ad_result.anomaly_score,
        is_anomaly=ad_result.is_anomaly,
        image_path=image_path,
        heatmap_path=heatmap_path,
        lot_number=lot_number,
        serial_number=serial_number,
        inference_time_ms=ad_result.inference_time_ms,
        model_name=ad_result.model_name,
    )
    db.add(db_result)

    # 5. VLM explanation (only for anomalies, unless skipped)
    vlm_out = None
    if ad_result.is_anomaly and not skip_vlm:
        vlm_svc = VLMService.get_instance()
        vlm_result = vlm_svc.explain(
            image=image,
            heatmap=heatmap_pil,
            category=category,
            anomaly_score=ad_result.anomaly_score,
            threshold=threshold,
        )

        db_vlm = VLMExplanation(
            result_id=result_id,
            defect_type=vlm_result.defect_type,
            location=vlm_result.location,
            severity=vlm_result.severity,
            cause=vlm_result.cause,
            recommended_action=vlm_result.recommended_action,
            full_explanation=vlm_result.full_explanation,
            vlm_model=vlm_result.vlm_model,
            generation_time_ms=vlm_result.generation_time_ms,
        )
        db.add(db_vlm)

        vlm_out = VLMExplanationOut(
            defect_type=vlm_result.defect_type,
            location=vlm_result.location,
            severity=vlm_result.severity,
            cause=vlm_result.cause,
            recommended_action=vlm_result.recommended_action,
            full_explanation=vlm_result.full_explanation,
            vlm_model=vlm_result.vlm_model,
            generation_time_ms=vlm_result.generation_time_ms,
        )

    # 6. Auto-create HACCP record if this is a CCP station and an anomaly was found
    #    HACCP Principle 2: Identify Critical Control Points
    #    Principle 4: Establish monitoring procedures → log actual vs critical limit
    if ad_result.is_anomaly and station_uuid:
        station_result = await db.execute(
            select(InspectionStation).where(InspectionStation.id == station_uuid)
        )
        station_obj = station_result.scalar_one_or_none()
        if station_obj and station_obj.is_ccp:
            within_limit = (
                ad_result.anomaly_score <= station_obj.critical_limit
                if station_obj.critical_limit is not None
                else None
            )
            corrective = (
                vlm_out.recommended_action
                if vlm_out and vlm_out.recommended_action
                else "Manual inspection required — CCP deviation detected."
            )
            haccp_rec = HACCPRecord(
                station_id=station_uuid,
                principle=4,  # HACCP Principle 4: Monitoring
                description=(
                    f"Automated CCP monitoring — anomaly detected by {ad_result.model_name}. "
                    f"Defect: {vlm_out.defect_type if vlm_out else 'unknown'}. "
                    f"Location: {vlm_out.location if vlm_out else 'unspecified'}."
                ),
                critical_limit=station_obj.critical_limit,
                actual_value=ad_result.anomaly_score,
                is_within_limit=within_limit,
                corrective_action=corrective,
                verified_by="system:SmartFactory-AD",
            )
            db.add(haccp_rec)
            logger.info(
                "Auto-created HACCP record for CCP station %s (score=%.3f, within_limit=%s)",
                station_uuid, ad_result.anomaly_score, within_limit,
            )

    await db.commit()

    return InspectionResponse(
        id=str(result_id),
        station_id=station_id,
        anomaly_score=ad_result.anomaly_score,
        is_anomaly=ad_result.is_anomaly,
        image_path=image_path,
        heatmap_path=heatmap_path,
        inference_time_ms=ad_result.inference_time_ms,
        model_name=ad_result.model_name,
        vlm_explanation=vlm_out,
        created_at=datetime.utcnow(),
    )
