"""Equipment telemetry router — Equipment Digital Twin Agent entry point.

Receives sensor readings from physical equipment (vibration, temperature,
current draw, cycle-time, robot/AMR state, etc.) and:
  1. Computes deviation from baseline
  2. Flags anomalies when deviation exceeds the station threshold
  3. Persists to equipment_readings table
  4. Triggers an Alert when anomaly is detected

This is the Physical AI ingestion layer for the AiU Platform Equipment
Digital Twin Agent, bridging factory-floor sensor data to the domain
reasoning layer (LangGraph preventive maintenance agent).

Physical AI research references:
  - 알씨케이: reliability strategy for Physical AI deployments
  - 에이디링크: industrial edge hardware (ADLink) sensor integration
  - 아세테크: robot logistics state monitoring
  - ASUS Ascent GX10: on-premise edge inference accelerator
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import Alert, AlertChannel, EquipmentReading, InspectionStation, SeverityLevel
from app.schemas.schemas import EquipmentReadingCreate, EquipmentReadingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipment", tags=["Equipment Telemetry"])


# ── Helpers ──


def _compute_deviation(value: float, baseline: float) -> float:
    """Return percentage deviation from baseline.  Zero baseline → 0.0."""
    if abs(baseline) < 1e-9:
        return 0.0
    return (value - baseline) / abs(baseline) * 100.0


def _is_anomaly(deviation_pct: float, threshold_pct: float = 20.0) -> bool:
    """Flag as anomaly when absolute deviation exceeds threshold_pct (default 20%)."""
    return abs(deviation_pct) > threshold_pct


# ── Endpoints ──


@router.post("/readings", response_model=EquipmentReadingResponse, status_code=201)
async def ingest_reading(
    payload: EquipmentReadingCreate,
    anomaly_threshold_pct: float = Query(
        default=20.0,
        description="Deviation threshold (%) above which reading is flagged anomalous",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single sensor telemetry reading from a piece of equipment.

    Computes deviation from baseline (if provided), flags anomaly, creates an
    Alert record for dashboard / MQTT notification, and returns the persisted
    reading.

    **Sensor types:** vibration | temperature | current | cycle_time |
    robot_state | custom

    **Typical callers:**
    - Edge Agent Runtime (MQTT bridge → REST)
    - PLC SCADA adapter
    - AMR / robot controller webhook
    """
    reading_id = uuid.uuid4()
    recorded_at = payload.recorded_at or datetime.utcnow()

    # Resolve optional station UUID
    station_uuid: Optional[uuid.UUID] = None
    station_obj: Optional[InspectionStation] = None
    if payload.station_id:
        try:
            station_uuid = uuid.UUID(payload.station_id)
            res = await db.execute(
                select(InspectionStation).where(InspectionStation.id == station_uuid)
            )
            station_obj = res.scalar_one_or_none()
        except ValueError:
            logger.warning("Invalid station_id UUID: %s — continuing without station link", payload.station_id)

    # Compute deviation and anomaly flag
    deviation_pct: Optional[float] = None
    anomaly = False
    if payload.baseline_value is not None:
        deviation_pct = _compute_deviation(payload.value, payload.baseline_value)
        anomaly = _is_anomaly(deviation_pct, anomaly_threshold_pct)

    reading = EquipmentReading(
        id=reading_id,
        station_id=station_uuid,
        equipment_id=payload.equipment_id,
        equipment_name=payload.equipment_name,
        line_name=payload.line_name or (station_obj.line_name if station_obj else ""),
        sensor_type=payload.sensor_type,
        sensor_unit=payload.sensor_unit,
        value=payload.value,
        baseline_value=payload.baseline_value,
        deviation_pct=deviation_pct,
        is_anomaly=anomaly,
        alert_triggered=False,
        lot_number=payload.lot_number,
        raw_payload=payload.raw_payload,
        recorded_at=recorded_at,
    )
    db.add(reading)

    # Create Alert when anomaly detected
    if anomaly:
        severity = (
            SeverityLevel.CRITICAL if abs(deviation_pct or 0) > 50
            else SeverityLevel.WARNING
        )
        alert = Alert(
            station_id=station_uuid,
            severity=severity,
            channel=AlertChannel.DASHBOARD,
            title=f"Equipment anomaly: {payload.equipment_name or payload.equipment_id} — {payload.sensor_type}",
            message=(
                f"Sensor reading {payload.value:.3f} {payload.sensor_unit} deviates "
                f"{deviation_pct:+.1f}% from baseline {payload.baseline_value:.3f} "
                f"{payload.sensor_unit}. Threshold: ±{anomaly_threshold_pct:.0f}%. "
                f"Equipment: {payload.equipment_id} | Line: {reading.line_name} | "
                f"Recorded: {recorded_at.isoformat()}"
            ),
        )
        db.add(alert)
        reading.alert_triggered = True
        logger.warning(
            "Equipment anomaly — %s [%s]: %.3f %s (baseline %.3f, dev %+.1f%%)",
            payload.equipment_id, payload.sensor_type,
            payload.value, payload.sensor_unit,
            payload.baseline_value or 0, deviation_pct or 0,
        )

    await db.commit()
    await db.refresh(reading)
    return reading


@router.get("/readings", response_model=List[EquipmentReadingResponse])
async def list_readings(
    equipment_id: Optional[str] = None,
    line_name: Optional[str] = None,
    sensor_type: Optional[str] = None,
    is_anomaly: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Query equipment telemetry readings with optional filters."""
    q = select(EquipmentReading)
    if equipment_id:
        q = q.where(EquipmentReading.equipment_id == equipment_id)
    if line_name:
        q = q.where(EquipmentReading.line_name == line_name)
    if sensor_type:
        q = q.where(EquipmentReading.sensor_type == sensor_type)
    if is_anomaly is not None:
        q = q.where(EquipmentReading.is_anomaly == is_anomaly)
    if start_date:
        q = q.where(EquipmentReading.recorded_at >= start_date)
    if end_date:
        q = q.where(EquipmentReading.recorded_at <= end_date)
    q = q.order_by(EquipmentReading.recorded_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()
