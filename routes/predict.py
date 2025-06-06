import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Annotated, List, Optional

from birdnetlib import Recording
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import Field

from deps import analyzer, TMP_DIR, limiter
from auth import verify_bearer_token
from models import Detection

router = APIRouter(prefix="/predict", tags=["predict"])

@router.post(
    "/file",
    summary="Upload a mono audio file and receive one detection per species (highest confidence)",
    response_model=List[Detection],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        200: {"description": "List of detections"},
        400: {"description": "Invalid Request"},
        500: {"description": "Internal Server Error"},
    },
)
@limiter.limit("10/minute")
async def predict_from_file(
    request: Request,
    file: UploadFile = File(
        ...,
        description=(
            "A mono audio file (wav, mp3, etc.). BirdNET expects a single-channel PCM stream. "
            "If you upload stereo, convert to mono first, e.g.: "
            "`ffmpeg -i stereo.wav -ac 1 -ar 48000 mono.wav`"
        ),
    ),
    lat: Annotated[
        float,
        Field(
            ...,
            ge=-90.0,
            le=90.0,
            description="Latitude of recording (between –90.0 and +90.0).",
        ),
    ] = Form(...),
    lon: Annotated[
        float,
        Field(
            ...,
            ge=-180.0,
            le=180.0,
            description="Longitude of recording (between –180.0 and +180.0).",
        ),
    ] = Form(...),
    date: Optional[datetime] = Form(
        None,
        description="Recording date in YYYY-MM-DD format. If omitted, defaults to today (UTC).",
    ),
    min_conf: Annotated[
        float,
        Field(
            0.25,
            ge=0.0,
            le=1.0,
            description="Minimum confidence threshold (0–1). Default 0.25.",
        ),
    ] = Form(0.25),
) -> List[Detection]:
    """
    1) Save uploaded file to a temp path.
    2) If `date` is None, use today's UTC date.
    3) Run BirdNET analysis (raw detections = multiple per species/time segment).
    4) Sort raw detections by confidence (descending).
    5) Group by `scientific_name`, keeping only the highest-confidence detection per species.
    6) Return a list of Detection objects (one per species).
    """
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    tmp_path = os.path.join(TMP_DIR, unique_name)
    try:
        with open(tmp_path, "wb") as out_f:
            shutil.copyfileobj(file.file, out_f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    if date is None:
        recording_date = datetime.now(timezone.utc).date()
    else:
        recording_date = date.date() if isinstance(date, datetime) else date

    try:
        rec = Recording(
            analyzer,
            tmp_path,
            lat=lat,
            lon=lon,
            date=recording_date,
            min_conf=min_conf,
        )
        rec.analyze()
        detections = rec.detections
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"BirdNET analysis failed: {e}")

    os.remove(tmp_path)

    sorted_detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    best_per_species: dict[str, dict] = {}
    for det in sorted_detections:
        species = det["scientific_name"]
        if species not in best_per_species:
            best_per_species[species] = det

    return [Detection(**det) for det in best_per_species.values()]


@router.post(
    "/stream",
    summary="Send raw WAV bytes (mono) and receive one detection per species (highest confidence)",
    response_model=List[Detection],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        200: {"description": "List of BirdNET detections, grouped by species"},
        400: {"description": "Bad request (e.g. invalid date format)"},
        500: {"description": "Internal error during analysis"},
    },
)
@limiter.limit("10/minute")
async def predict_from_stream(
    request: Request,
    data: bytes = File(
        ...,
        description=(
            "Raw WAV byte stream (16-bit little-endian, mono). Must include a valid "
            "WAV header for BirdNET’s ffmpeg/librosa to decode."
        ),
    ),
    lat: Annotated[
        float,
        Field(
            ...,
            ge=-90.0,
            le=90.0,
            description="Latitude of recording (between –90.0 and +90.0).",
        ),
    ] = Form(...),
    lon: Annotated[
        float,
        Field(
            ...,
            ge=-180.0,
            le=180.0,
            description="Longitude of recording (between –180.0 and +180.0).",
        ),
    ] = Form(...),
    date: Optional[datetime] = Form(
        None,
        description="Recording date in YYYY-MM-DD format. If omitted, defaults to today (UTC).",
    ),
    min_conf: Annotated[
        float,
        Field(
            0.25,
            ge=0.0,
            le=1.0,
            description="Minimum confidence threshold (0–1). Default 0.25.",
        ),
    ] = Form(0.25),
) -> List[Detection]:
    """
    1) Write raw WAV bytes to a temp .wav file.
    2) If `date` is None, use today's UTC date.
    3) Run BirdNET analysis (raw detections = multiple per species/time segment).
    4) Sort raw detections by confidence (descending).
    5) Group by `scientific_name`, keeping only the highest-confidence detection per species.
    6) Return a list of Detection objects (one per species).
    """
    unique_name = f"{uuid.uuid4().hex}_stream.wav"
    tmp_path = os.path.join(TMP_DIR, unique_name)
    try:
        with open(tmp_path, "wb") as out_f:
            out_f.write(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save stream data: {e}")

    if date is None:
        recording_date = datetime.now(timezone.utc).date()
    else:
        recording_date = date.date() if isinstance(date, datetime) else date

    try:
        rec = Recording(
            analyzer,
            tmp_path,
            lat=lat,
            lon=lon,
            date=recording_date,
            min_conf=min_conf,
        )
        rec.analyze()
        raw_detections: List[dict] = rec.detections
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"BirdNET analysis failed: {e}")

    os.remove(tmp_path)

    sorted_detections = sorted(raw_detections, key=lambda d: d["confidence"], reverse=True)
    best_per_species: dict[str, dict] = {}
    for det in sorted_detections:
        species = det["scientific_name"]
        if species not in best_per_species:
            best_per_species[species] = det

    return [Detection(**det) for det in best_per_species.values()]
