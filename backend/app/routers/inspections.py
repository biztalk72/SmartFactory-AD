from uuid import UUID
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import InspectionResult
from app.schemas.schemas import InspectionResultResponse

router = APIRouter(prefix="/inspections", tags=["Inspections"])


@router.get("/", response_model=List[InspectionResultResponse])
async def list_inspections(
    station_id: Optional[UUID] = None,
    is_anomaly: Optional[bool] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    query = select(InspectionResult)
    filters = []
    if station_id:
        filters.append(InspectionResult.station_id == station_id)
    if is_anomaly is not None:
        filters.append(InspectionResult.is_anomaly == is_anomaly)
    if start_date:
        filters.append(InspectionResult.created_at >= start_date)
    if end_date:
        filters.append(InspectionResult.created_at <= end_date)
    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(InspectionResult.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{result_id}", response_model=InspectionResultResponse)
async def get_inspection(result_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InspectionResult).where(InspectionResult.id == result_id)
    )
    inspection = result.scalar_one_or_none()
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection result not found")
    return inspection
