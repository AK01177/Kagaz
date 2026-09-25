import asyncio
import json

import pytest
from starlette import formparsers

from api import upload_limit
from main import app


def send_chunks(chunks, extra_headers=()):
    """Drive ASGI directly so streaming tests cannot silently buffer the body."""
    messages = []
    reads = 0

    async def run():
        nonlocal reads

        async def receive():
            nonlocal reads
            assert reads < len(chunks), "Application consumed past the request body"
            body = chunks[reads]
            reads += 1
            return {"type": "http.request", "body": body, "more_body": reads < len(chunks)}

        async def send(message):
            messages.append(message)

        await app({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": "/api/documents",
            "raw_path": b"/api/documents", "query_string": b"", "root_path": "",
            "headers": [(b"content-type", b"multipart/form-data; boundary=test"), *extra_headers],
            "client": ("127.0.0.1", 1234), "server": ("test", 80),
        }, receive, send)

    asyncio.run(run())
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(body), reads


def test_oversized_content_length_rejected_without_reading_body():
    status, body, reads = send_chunks([], [
        (b"content-length", str(upload_limit.MAX_REQUEST_BYTES + 1).encode()),
    ])
    assert status == 413
    assert body["error"]["code"] == "FILE_TOO_LARGE"
    assert reads == 0


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_stream_limit_stops_reading_and_closes_partial_files(monkeypatch, headers):
    limit = 2 * 1024 * 1024
    monkeypatch.setattr(upload_limit, "MAX_REQUEST_BYTES", limit)
    opened = []
    original = formparsers.SpooledTemporaryFile

    def track_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", track_file)
    prefix = (b'--test\r\nContent-Disposition: form-data; name="file"; '
              b'filename="huge.pdf"\r\nContent-Type: application/pdf\r\n\r\n')
    chunks = [prefix] + [b"x" * (64 * 1024)] * 40 + [b"\r\n--test--\r\n"]
    status, body, reads = send_chunks(chunks, headers)
    assert status == 413
    assert body["error"]["code"] == "FILE_TOO_LARGE"
    assert reads < len(chunks)
    assert opened
    assert all(file.closed for file in opened)


def test_small_malformed_multipart_keeps_original_error():
    status, body, _ = send_chunks([b"--test\r\nContent-Disposition: form-data\r\n\r\nx\r\n--test--\r\n"])
    assert status == 400
    assert body["error"]["code"] == "HTTP_ERROR"
