from pydantic import BaseModel
from typing import Optional

class GPSData(BaseModel):
    latitude: float
    longitude: float

class Coordinates(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None

class ReportData(BaseModel):
    transcription: Optional[str] = None
    location: Optional[str] = None
    hazard: Optional[str] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    coordinates: Optional[Coordinates] = None

class ReportResponse(BaseModel):
    status: str
    data: Optional[ReportData] = None
    message: Optional[str] = None
    error_type: Optional[str] = None