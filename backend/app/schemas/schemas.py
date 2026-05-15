from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


# ── InspectionStation ──


class StationCreate(BaseModel):
    name: str
    description: str = ""
    line_name: str
    is_ccp: bool = False
    camera_url: str = ""
    product_category: str = ""
    anomaly_threshold: float = 0.5
    critical_limit: Optional[float] = None


class StationUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    line_name: Optional[str] = None
    is_ccp: Optional[bool] = None
    camera_url: Optional[str] = None
    product_category: Optional[str] = None
    anomaly_threshold: Optional[float] = None
    critical_limit: Optional[float] = None
    is_active: Optional[bool] = None


class StationResponse(BaseModel):
    id: UUID
    name: str
    description: str
    line_name: str
    is_ccp: bool
    camera_url: str
    product_category: str
    anomaly_threshold: float
    critical_limit: Optional[float]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── InspectionResult ──


class InspectionResultResponse(BaseModel):
    id: UUID
    station_id: UUID
    anomaly_score: float
    is_anomaly: bool
    image_path: str
    heatmap_path: str
    lot_number: str
    serial_number: str
    inference_time_ms: float
    model_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── VLMExplanation ──


class VLMExplanationResponse(BaseModel):
    id: UUID
    result_id: UUID
    defect_type: str
    location: str
    severity: str
    cause: str
    recommended_action: str
    full_explanation: str
    vlm_model: str
    generation_time_ms: float
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Alert ──


class AlertResponse(BaseModel):
    id: UUID
    result_id: Optional[UUID]
    station_id: Optional[UUID]
    severity: str
    channel: str
    title: str
    message: str
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertAcknowledge(BaseModel):
    acknowledged_by: str


# ── HACCP ──


class HACCPRecordResponse(BaseModel):
    id: UUID
    station_id: UUID
    principle: int
    description: str
    critical_limit: Optional[float]
    actual_value: Optional[float]
    is_within_limit: Optional[bool]
    corrective_action: str
    verified_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Health ──


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    services: dict = Field(default_factory=dict)
