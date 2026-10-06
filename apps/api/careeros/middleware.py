"""Bound the actual request stream, including requests without Content-Length."""

from starlette.responses import JSONResponse


class RequestSizeLimit:
    def __init__(self, app, maximum=1024 * 1024):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        header = dict(scope.get("headers", [])).get(b"content-length", b"0")
        try:
            length = int(header)
            if length < 0:
                raise ValueError
        except ValueError:
            return await self.reject(scope, receive, send, 400, "Invalid Content-Length")
        if length > self.maximum:
            return await self.reject(scope, receive, send, 413, "Request too large")
        parts, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            part = message.get("body", b"")
            size += len(part)
            if size > self.maximum:
                return await self.reject(scope, receive, send, 413, "Request too large")
            parts.append(part)
            if not message.get("more_body", False):
                break
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": b"".join(parts), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    async def reject(self, scope, receive, send, status, message):
        response = JSONResponse(
            {"error": {"message": message, "request_id": scope.get("state", {}).get("request_id")}},
            status_code=status,
        )
        await response(scope, receive, send)
