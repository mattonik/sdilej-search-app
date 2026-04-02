from __future__ import annotations

import threading

from .sdilej_client import SdilejClient
from .search_utils import (
    build_tv_episode_result_scorer,
    build_tv_search_aliases,
    search_tv_episode_results,
    select_effective_tv_search_aliases,
)
from .storage import Storage


class TvSearchWorker:
    def __init__(
        self,
        storage: Storage,
        poll_seconds: float = 2.0,
        client_factory=SdilejClient,
    ) -> None:
        self.storage = storage
        self.poll_seconds = poll_seconds
        self.client_factory = client_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="tv-search-worker", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            job = self.storage.claim_next_tv_search_job()
            if not job:
                self._stop_event.wait(self.poll_seconds)
                continue
            self._process_job(job)

    def _process_job(self, job: dict) -> None:
        job_id = int(job["id"])
        client = self.client_factory(timeout_seconds=30)
        show = job.get("show") or {}
        aliases = list(job.get("aliases") or [])
        search_aliases = list(job.get("search_aliases") or [])
        show_name = str(show.get("name") or job.get("show_name") or "").strip()
        if not aliases and show_name:
            aliases = [show_name]
        if not search_aliases:
            search_aliases = build_tv_search_aliases(
                show_name=show_name,
                request_query=aliases[0] if aliases else show_name,
                title_metadata=job.get("title_metadata"),
            )
        if not search_aliases and show_name:
            search_aliases = [show_name]
        search_aliases = select_effective_tv_search_aliases(
            client=client,
            show_name=show_name,
            search_aliases=search_aliases,
            category=str(job.get("category") or "video"),
        )

        try:
            for episode in self.storage.list_pending_tv_search_episodes(job_id):
                if self._stop_event.is_set() or self.storage.is_tv_search_job_canceled(job_id):
                    return

                season_number = int(episode["season_number"])
                episode_number = int(episode["episode_number"])
                if not self.storage.mark_tv_search_episode_running(job_id, season_number, episode_number):
                    continue

                result_scorer = build_tv_episode_result_scorer(
                    show_aliases=search_aliases,
                    season=season_number,
                    episode=episode_number,
                    episode_name=episode.get("episode_name"),
                )
                aggregated = search_tv_episode_results(
                    client=client,
                    show_aliases=search_aliases,
                    season=season_number,
                    episode=episode_number,
                    category=str(job.get("category") or "video"),
                    sort="relevance",
                    language=job.get("language"),
                    language_scope=str(job.get("language_scope") or "any"),
                    strict_dubbing=bool(job.get("strict_dubbing")),
                    release_year=None,
                    max_results_per_query=int(job.get("max_results_per_variant") or 120),
                    result_scorer=result_scorer,
                )
                query_variants = aggregated["expanded_queries"]
                if self.storage.is_tv_search_job_canceled(job_id):
                    return

                self.storage.complete_tv_search_episode(
                    job_id,
                    season_number=season_number,
                    episode_number=episode_number,
                    query_variants=query_variants,
                    query_errors=list(aggregated["query_errors"]),
                    results=list(aggregated["items"]),
                )

            self.storage.finalize_tv_search_job(job_id)
        except Exception as exc:  # noqa: BLE001
            self.storage.fail_tv_search_job(job_id, error=str(exc))
