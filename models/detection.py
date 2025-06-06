from pydantic import BaseModel, Field

class Detection(BaseModel):
    scientific_name: str = Field(..., description="Scientific name (e.g. Melospiza melodia)")
    common_name: str = Field(..., description="Common name (e.g. Song Sparrow)")
    label: str = Field(..., description="Combined label (scientific + common)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence (0–1)")
    start_time: float = Field(..., description="Segment start time in seconds")
    end_time: float = Field(..., description="Segment end time in seconds")
