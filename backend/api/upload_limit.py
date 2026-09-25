from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException
from starlette.formparsers import MultiPartException

from services.upload import MAX_UPLOAD_BYTES


# Bound total parsing/storage work, allowing headers and boundaries around a PDF.
MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + 64 * 1024


def too_large():
    return JSONResponse(status_code=413, content={"error": {
        "code": "FILE_TOO_LARGE",
        "message": "Upload request exceeds the 10 MiB file limit plus 64 KiB multipart allowance.",
    }})


class UploadLimitRoute(APIRoute):
    """Limit incoming bytes before FastAPI's multipart parser sees them."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def limited_handler(request: Request):
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > MAX_REQUEST_BYTES:
                        return too_large()
                except ValueError:
                    pass  # Always count actual bytes, regardless of the header.

            received = 0
            exceeded = False

            async def limited_receive():
                nonlocal received, exceeded
                message = await request.receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > MAX_REQUEST_BYTES:
                        exceeded = True
                        # This exception makes the parser close any partial files.
                        raise MultiPartException("Upload request is too large.")
                return message

            bounded_request = Request(request.scope, receive=limited_receive)
            try:
                return await handler(bounded_request)
            except HTTPException:
                # Starlette translates multipart errors to HTTP 400. Preserve
                # other errors and translate only our byte-limit failure to 413.
                if exceeded:
                    return too_large()
                raise

        return limited_handler
