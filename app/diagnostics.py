from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-Id"


def new_request_id() -> str:
    return uuid4().hex[:12]


def get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return str(request_id)
    header_value = str(request.headers.get("x-request-id") or "").strip()
    return header_value or new_request_id()


def build_error_payload(
    request: Request,
    *,
    error: str,
    error_code: str,
    hint: str | None = None,
    retryable: bool | None = None,
    details: str | None = None,
    **extra: object,
) -> dict:
    payload: dict[str, object] = {
        "error": error,
        "error_code": error_code,
        "request_id": get_request_id(request),
    }
    if hint:
        payload["hint"] = hint
    if retryable is not None:
        payload["retryable"] = bool(retryable)
    if details:
        payload["details"] = details
    payload.update(extra)
    return payload


def error_response(
    request: Request,
    *,
    status_code: int,
    error: str,
    error_code: str,
    hint: str | None = None,
    retryable: bool | None = None,
    details: str | None = None,
    **extra: object,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_error_payload(
            request,
            error=error,
            error_code=error_code,
            hint=hint,
            retryable=retryable,
            details=details,
            **extra,
        ),
    )
