from __future__ import annotations

import responses

from app.title_metadata import CZDB_DETAIL_URL, CZDB_SEARCH_URL, TitleMetadataResolver, build_ordered_aliases, normalize_alias_key
from app.tvmaze_client import TvMazeClient, TvShowSummary


def test_normalize_alias_key_and_ordering() -> None:
    assert normalize_alias_key("Veselá farma!!") == "vesela farma"
    aliases = build_ordered_aliases(
        user_query="Shaun the Sheep",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Vesela farma", "Ovecka Shaun"],
        aliases=["Shaun the Sheep", "Vesela farma", "Na Veselej farme"],
    )
    assert aliases == [
        "Shaun the Sheep",
        "Ovecka Shaun",
        "Vesela farma",
        "Na Veselej farme",
    ]


@responses.activate
def test_movie_metadata_uses_czdb_detail_genres_and_cache(
    storage,
    sample_czdb_movie_response,
    sample_czdb_movie_detail_payload,
) -> None:
    responses.get(CZDB_SEARCH_URL, json=sample_czdb_movie_response)
    responses.get(
        CZDB_DETAIL_URL,
        json=sample_czdb_movie_detail_payload,
        match=[responses.matchers.query_param_matcher({"uid": "9499"})],
    )

    resolver = TitleMetadataResolver(storage=storage, tv_client=TvMazeClient())
    metadata = resolver.resolve_movie("Matrix", 1999)
    cached = resolver.resolve_movie("Matrix", 1999)

    assert metadata.canonical_title == "Matrix"
    assert metadata.original_title == "The Matrix"
    assert metadata.genres == ["Akční", "Sci-Fi"]
    assert metadata.summary == "Neo learns the truth."
    assert metadata.aliases[:2] == ["Matrix", "The Matrix"]
    assert cached.aliases == metadata.aliases
    assert len(responses.calls) == 2


@responses.activate
def test_tv_metadata_merges_czdb_and_tvmaze_akas(
    storage,
    sample_czdb_show_response,
    sample_czdb_show_detail_payload,
    sample_tvmaze_akas_payload,
) -> None:
    responses.get(CZDB_SEARCH_URL, json=sample_czdb_show_response)
    responses.get(
        CZDB_DETAIL_URL,
        json=sample_czdb_show_detail_payload,
        match=[responses.matchers.query_param_matcher({"uid": "202"})],
    )
    responses.get("https://api.tvmaze.com/shows/321/akas", json=sample_tvmaze_akas_payload)

    resolver = TitleMetadataResolver(storage=storage, tv_client=TvMazeClient())
    metadata = resolver.resolve_tv(
        "Shaun the Sheep",
        show=TvShowSummary(
            id=321,
            name="Shaun the Sheep",
            premiered="2007-03-05",
            language="English",
            type="Animation",
            genres=["Comedy", "Children"],
            summary="<p>Shaun leads the flock through playful adventures for children and families.</p>",
        ),
        year=2007,
    )

    assert metadata.kind == "tv"
    assert metadata.canonical_title == "Ovecka Shaun"
    assert "Shaun the Sheep" in metadata.aliases
    assert "Vesela farma" in metadata.aliases
    assert metadata.content_type == "Animation"
    assert metadata.genres == ["Animovaný", "Rodinný", "Komedie", "Comedy", "Children"]
    assert metadata.summary == "Shaun and his flock have playful family adventures on the farm."
    assert metadata.source_ids["tvmaze"] == 321


@responses.activate
def test_tv_metadata_falls_back_when_czdb_has_no_match(storage, sample_tvmaze_akas_payload) -> None:
    responses.get(CZDB_SEARCH_URL, json={"results": [], "response": "False"})
    responses.get("https://api.tvmaze.com/shows/321/akas", json=sample_tvmaze_akas_payload)

    resolver = TitleMetadataResolver(storage=storage, tv_client=TvMazeClient())
    metadata = resolver.resolve_tv(
        "Shaun the Sheep",
        show=TvShowSummary(id=321, name="Shaun the Sheep", premiered="2007-03-05", language="English"),
        year=2007,
    )

    assert metadata.source == "tvmaze"
    assert metadata.canonical_title == "Shaun the Sheep"
    assert metadata.aliases[0] == "Shaun the Sheep"
