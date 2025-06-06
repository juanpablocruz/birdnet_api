from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import HTTPException, status

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

class MaxSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """
        Reject any POST to /predict/ endpoints if Content-Length > MAX_UPLOAD_SIZE.
        """
        if request.method == "POST" and request.url.path.startswith("/predict/"):
            content_length = request.headers.get("Content-Length")
            if content_length is not None and int(content_length) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size is {MAX_UPLOAD_SIZE} bytes.",
                )
        return await call_next(request)
