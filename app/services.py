from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from .downloader import DownloadWorker
from .sdilej_client import SdilejClient
from .storage import Storage
from .title_metadata import TitleMetadataResolver
from .tv_search_worker import TvSearchWorker
from .tvmaze_client import TvMazeClient


@dataclass
class ServiceContainer:
    client: SdilejClient
    tv_client: TvMazeClient
    storage: Storage
    worker: DownloadWorker
    metadata_resolver: TitleMetadataResolver
    tv_search_worker: TvSearchWorker


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services
