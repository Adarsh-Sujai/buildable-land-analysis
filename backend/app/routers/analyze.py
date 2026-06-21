"""Buildable-area analysis endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas import AnalyzeRequest, AnalyzeResponse
from ..services import ParcelNotFound, run_analysis

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_parcel(req: AnalyzeRequest):
    try:
        return run_analysis(req)
    except ParcelNotFound:
        raise HTTPException(status_code=404, detail=f"parcel '{req.parcel_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
