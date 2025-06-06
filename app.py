from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from deps import limiter
from middleware import MaxSizeMiddleware
from metrics import MetricsMiddleware

from slowapi.middleware import SlowAPIMiddleware
from routes.predict import router as predict_router
from routes.health import router as health_router
from routes.streaming import router as streaming_router

app = FastAPI(
    title="BirdNET Prediction Service",
    description=(
        "Upload a mono audio file (mp3/wav) or raw PCM stream, "
        "and receive BirdNET species detections sorted by confidence."
    ),
    version="1.0.0",
    contact={"name": "Juan Pablo Cruz", "email": "juanpablocruzmaseda@gmail.com"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
)

app.state.limiter = limiter
app.add_middleware(MaxSizeMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too Many Requests", "details": str(exc.detail)},
    )

app.include_router(predict_router)
app.include_router(health_router)
app.include_router(streaming_router, prefix="/ws")
