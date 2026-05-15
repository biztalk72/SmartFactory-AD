from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import InspectionStation
from app.schemas.schemas import StationCreate, StationUpdate, StationResponse

router = APIRouter(prefix="/stations", tags=["Inspection Stations"])


@router.post("/", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(payload: StationCreate, db: AsyncSession = Depends(get_db)):
    station = InspectionStation(**payload.model_dump())
    db.add(station)
    await db.commit()
    await db.refresh(station)
    return station


@router.get("/", response_model=List[StationResponse])
async def list_stations(
    line_name: str | None = None,
    is_ccp: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(InspectionStation).where(InspectionStation.is_active == True)
    if line_name:
        query = query.where(InspectionStation.line_name == line_name)
    if is_ccp is not None:
        query = query.where(InspectionStation.is_ccp == is_ccp)
    result = await db.execute(query.order_by(InspectionStation.created_at.desc()))
    return result.scalars().all()


@router.get("/{station_id}", response_model=StationResponse)
async def get_station(station_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InspectionStation).where(InspectionStation.id == station_id)
    )
    station = result.scalar_one_or_none()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@router.patch("/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: UUID, payload: StationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(InspectionStation).where(InspectionStation.id == station_id)
    )
    station = result.scalar_one_or_none()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(station, field, value)

    await db.commit()
    await db.refresh(station)
    return station


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_station(station_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InspectionStation).where(InspectionStation.id == station_id)
    )
    station = result.scalar_one_or_none()
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    station.is_active = False
    await db.commit()
