import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Boolean, Integer, Text, DateTime, ForeignKey, Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# ── Enums ──

import enum


class SeverityLevel(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertChannel(str, enum.Enum):
    DASHBOARD = "DASHBOARD"
    WEBHOOK = "WEBHOOK"
    EMAIL = "EMAIL"
    MQTT = "MQTT"


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"


# ── Models ──


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.OPERATOR)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InspectionStation(Base):
    __tablename__ = "inspection_stations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    line_name = Column(String(200), nullable=False)
    is_ccp = Column(Boolean, default=False)
    camera_url = Column(String(500), default="")
    product_category = Column(String(200), default="")
    anomaly_threshold = Column(Float, default=0.5)
    critical_limit = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    results = relationship("InspectionResult", back_populates="station")
    haccp_records = relationship("HACCPRecord", back_populates="station")


class InspectionResult(Base):
    __tablename__ = "inspection_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("inspection_stations.id"), nullable=False)
    anomaly_score = Column(Float, nullable=False)
    is_anomaly = Column(Boolean, nullable=False)
    image_path = Column(String(500), nullable=False)
    heatmap_path = Column(String(500), default="")
    lot_number = Column(String(100), default="")
    serial_number = Column(String(100), default="")
    inference_time_ms = Column(Float, default=0)
    model_name = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    station = relationship("InspectionStation", back_populates="results")
    vlm_explanation = relationship("VLMExplanation", back_populates="result", uselist=False)
    alerts = relationship("Alert", back_populates="result")


class VLMExplanation(Base):
    __tablename__ = "vlm_explanations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("inspection_results.id"), unique=True, nullable=False)
    defect_type = Column(String(200), default="")
    location = Column(String(200), default="")
    severity = Column(String(50), default="")
    cause = Column(Text, default="")
    recommended_action = Column(Text, default="")
    full_explanation = Column(Text, default="")
    vlm_model = Column(String(100), default="")
    generation_time_ms = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    result = relationship("InspectionResult", back_populates="vlm_explanation")


class HACCPRecord(Base):
    __tablename__ = "haccp_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("inspection_stations.id"), nullable=False)
    principle = Column(Integer, nullable=False)  # 1-7
    description = Column(Text, nullable=False)
    critical_limit = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    is_within_limit = Column(Boolean, nullable=True)
    corrective_action = Column(Text, default="")
    verified_by = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    station = relationship("InspectionStation", back_populates="haccp_records")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id = Column(UUID(as_uuid=True), ForeignKey("inspection_results.id"), nullable=True)
    station_id = Column(UUID(as_uuid=True), ForeignKey("inspection_stations.id"), nullable=True)
    severity = Column(Enum(SeverityLevel), nullable=False)
    channel = Column(Enum(AlertChannel), nullable=False, default=AlertChannel.DASHBOARD)
    title = Column(String(300), nullable=False)
    message = Column(Text, default="")
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(200), default="")
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    result = relationship("InspectionResult", back_populates="alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    username = Column(String(200), default="system")
    action = Column(String(200), nullable=False)
    resource_type = Column(String(100), default="")
    resource_id = Column(String(200), default="")
    details = Column(Text, default="")
    ip_address = Column(String(50), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
