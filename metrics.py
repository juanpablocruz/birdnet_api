
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_COUNT = Counter(
    "birdnet_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "birdnet_request_latency_seconds",
    "HTTP request latency (seconds)",
    ["method", "endpoint"],
)

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Record start time
        method = request.method
        endpoint = request.url.path  # or use request.scope["endpoint"].__name__ if you want the function name

        with REQUEST_LATENCY.labels(method=method, endpoint=endpoint).time():
            response: Response = await call_next(request)

        # After response is ready, increment count with status code
        status_code = response.status_code
        REQUEST_COUNT.labels(
            method=method, endpoint=endpoint, http_status=str(status_code)
        ).inc()
        return response

async def metrics_endpoint():
    """
    Return Prometheus metrics as plain text.
    """
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
