from typing import Optional
from pydantic import BaseModel, Field


class PredictionParams(BaseModel):
    """
    Optional request fields for lat, lon, date, and min_confidence threshold.
    BirdNET uses latitude/longitude to adjust species list internally; date lets you
    specify the recording date (format YYYY-MM-DD).  If omitted, defaults to today’s date.
    """
    lat: float = Field(..., description="Latitude of recording (e.g. 35.4244)")
    lon: float = Field(..., description="Longitude of recording (e.g. -120.7463)")
    date: Optional[str] = Field(
        None,
        description="Date of recording in YYYY-MM-DD (default: today)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    min_conf: float = Field(
        0.25, description="Minimum confidence threshold (0–1). Lower ⇒ more detections."
    )
