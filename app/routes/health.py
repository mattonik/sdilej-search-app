from __future__ import annotations

from fastapi import APIRouter, Request

from ..main import _get_services

router = APIRouter()


@router.get("/healthz")
def healthcheck(request: Request):
    services = _get_services(request)
    return {
        "status": "ok",
        "worker_alive": services.worker.is_alive(),
        "tv_search_worker_alive": services.tv_search_worker.is_alive(),
    }
