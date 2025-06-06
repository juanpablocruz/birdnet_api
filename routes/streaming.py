import os
import wave
import tempfile
import asyncio
from datetime import datetime, timezone, date as dtDate
from typing import Annotated, Optional

from birdnetlib import Recording
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from pydantic import BaseModel, Field

from deps import analyzer
from auth import EXPECTED_TOKEN
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter()

def write_temp_wav(data: bytearray, sample_rate: int, channels: int, sample_width: int) -> str:
    """
    Creates a temporary WAV file with the provided PCM data and returns the file path.

    Parameters:
        data: Raw PCM byte buffer.
        sample_rate: Sampling rate in Hz.
        channels: Number of audio channels (1 = mono).
        sample_width: Bytes per sample (2 for 16-bit PCM).

    Returns:
        The path to the created temporary WAV file.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(data)
        return tmp.name
def safe_remove(path: str):
    """
    Removes the specified file path if it exists. Logs a warning on failure.
    """
    try:
        os.remove(path)
    except Exception as e:
        logger.warning("Failed to remove temporary file %s: %s", path, e)

def run_birdnet_on_file(file_path: str, lat: float, lon: float, date: dtDate, min_conf: float) -> list[dict]:
    """
    Runs BirdNET detection on a WAV file and returns a list of detection results.
    """
    rec = Recording(analyzer, file_path, lat=lat, lon=lon, date=date, min_conf=min_conf)
    rec.analyze()
    return rec.detections


class RealtimeInit(BaseModel):
    lat: Annotated[
        float,
        Field(
            ...,
            ge=-90.0,
            le=90.0,
            description="Latitude (–90.0 to +90.0).",
        ),
    ]
    lon: Annotated[
        float,
        Field(
            ...,
            ge=-180.0,
            le=180.0,
            description="Longitude (–180.0 to +180.0).",
        ),
    ]
    date: Optional[datetime] = Field(
        None,
        description="Recording date (YYYY-MM-DD). Defaults to today UTC if omitted.",
    )
    min_conf: Annotated[
        float,
        Field(
            0.25,
            ge=0.0,
            le=1.0,
            description="Confidence threshold (0–1). Default 0.25.",
        ),
    ] = Field(0.25)
    timeout: Annotated[
        float,
        Field(
            30.0,
            ge=1.0,
            description="Max seconds to listen before timing out. Default 30 s.",
        ),
    ] = Field(30.0)


def verify_token_or_close(token: str):
    if token != EXPECTED_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.websocket("/stream")
async def websocket_realtime(
    websocket: WebSocket,
    token: str = Query(..., description="Bearer token for auth"),
):
    """
    WebSocket endpoint for real-time BirdNET “Shazam”-style detection.
    Protocol:
      1) Client connects to ws://<host>/ws/stream?token=<token>.
      2) Server checks the token; if it doesn't match, it closes with 1008.
      3) Client sends init JSON: {lat, lon, [date], [min_conf], [timeout]}.
      4) Server accumulates PCM bytes (48 kHz, 16-bit LE, mono). Each time the buffer
         reaches an additional 3 s (3 s, 6 s, 9 s, …), it runs BirdNET over the ENTIRE buffer
         and sends a message with the detection (or an empty array if nothing is detected).
      5) If `timeout` seconds pass since init without the client closing, the server
         sends {"timeout": true} and closes.
      6) If the client closes the WebSocket, the server also terminates.
    """
    await websocket.accept()

    try:
        verify_token_or_close(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        init_payload = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        init = RealtimeInit(**init_payload)
    except Exception:
        await websocket.send_json({"error": "Invalid init payload"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    lat = init.lat
    lon = init.lon
    min_conf = init.min_conf
    timeout_seconds = init.timeout

    if init.date is None:
        recording_date = datetime.now(timezone.utc).date()
    else:
        recording_date = init.date

    SAMPLE_RATE = 48000       # 48 kHz
    CHANNELS = 1              # mono
    SAMPLE_WIDTH = 2          # 16-bit = 2 bytes/sample
    WINDOW_SECONDS = 3
    WINDOW_BYTES = SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH * WINDOW_SECONDS  # = 288000 bytes
    # First window is 3 s (288000 bytes), then 6 s (576000 bytes), then 9 s, etc.

    buffer = bytearray()
    start_time = datetime.now(timezone.utc)
    next_window_bytes = WINDOW_BYTES  # first 3 s threshold

    try:
        while True:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed >= timeout_seconds:
                await websocket.send_json({"timeout": True})
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                return

            try:
                msg = await asyncio.wait_for(websocket.receive_bytes(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                return

            buffer.extend(msg)
            logger.debug("Received %d bytes, total buffer = %d bytes", len(msg), len(buffer))

            if len(buffer) >= next_window_bytes:
                logger.debug("Buffer ≥ %d → launching BirdNET", next_window_bytes)

                try:
                    wav_path = write_temp_wav(buffer[:next_window_bytes], SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH)
                except Exception as e:
                    await websocket.send_json({"error": f"I/O error: {e}"})
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                    return

                try:
                    detections = run_birdnet_on_file(wav_path, lat, lon, recording_date, min_conf)
                except Exception as e:
                    safe_remove(wav_path)
                    await websocket.send_json({"error": f"BirdNET failed: {e}"})
                    await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                    return
                finally:
                    safe_remove(wav_path)

                logger.debug("BirdNET returned %d detections for window %d s", len(detections), next_window_bytes // WINDOW_BYTES)
                for det in detections:
                    logger.debug("    species = %s, confidence = %.3f", det['scientific_name'], det['confidence'])

                await websocket.send_json({"detections": sorted(detections, key=lambda d: d["confidence"], reverse=True)})

                next_window_bytes += WINDOW_BYTES
                logger.debug("Next window will be %d bytes (%d s)", next_window_bytes, next_window_bytes // WINDOW_BYTES)

    except WebSocketDisconnect:
        return
    except Exception as e:
        await websocket.send_json({"error": f"Server error: {e}"})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return
