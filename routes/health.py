from datetime import datetime, timezone
from fastapi import APIRouter
from starlette.responses import JSONResponse

from deps import start_time, analyzer
from metrics import metrics_endpoint

router = APIRouter(tags=["monitoring"])

@router.get("/health")
async def health():
    """
    Health check endpoint:
      - status: "ok"
      - uptime_seconds: seconds since app start
      - model_loaded: true if the BirdNET Analyzer instance exists
    """
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - start_time).total_seconds()
    model_loaded = analyzer is not None
    return JSONResponse(
        content={
            "status": "ok",
            "uptime_seconds": uptime_seconds,
            "model_loaded": model_loaded,
        }
    )

@router.get("/metrics", include_in_schema=False)
async def get_metrics():
    """
    Expose Prometheus metrics (collected by MetricsMiddleware).
    """
    return await metrics_endpoint()
