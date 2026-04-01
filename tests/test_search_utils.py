from __future__ import annotations

from app.models import TitleMetadata
from app.search_utils import build_tv_episode_result_matcher, build_tv_search_aliases
from tests.conftest import build_search_result


def test_tv_search_aliases_drop_risky_short_prefix_aliases() -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Blue",
        original_title="Bluey",
        local_titles=["Blue"],
        aliases=["Bluey", "Blue"],
        year=2018,
        source="czdb",
        source_ids={"czdb": 28067},
    )

    aliases = build_tv_search_aliases(
        show_name="Bluey",
        request_query="Bluey",
        title_metadata=metadata,
    )

    assert aliases == ["Bluey"]


def test_tv_search_aliases_keep_multiword_localized_titles() -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Ovecka Shaun",
        original_title="Shaun the Sheep",
        local_titles=["Ovecka Shaun", "Vesela farma"],
        aliases=["Shaun the Sheep", "Vesela farma"],
        year=2007,
        source="czdb",
        source_ids={"czdb": 101},
    )

    aliases = build_tv_search_aliases(
        show_name="Shaun the Sheep",
        request_query="Shaun the Sheep",
        title_metadata=metadata,
    )

    assert aliases == ["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"]
    assert metadata.aliases == ["Shaun the Sheep", "Vesela farma"]


def test_tv_episode_result_matcher_rejects_unrelated_blue_titles() -> None:
    metadata = TitleMetadata(
        kind="tv",
        canonical_title="Blue",
        original_title="Bluey",
        local_titles=["Blue"],
        aliases=["Bluey", "Blue"],
        year=2018,
        source="czdb",
        source_ids={"czdb": 28067},
    )
    matcher = build_tv_episode_result_matcher(
        show_name="Bluey",
        request_query="Bluey",
        title_metadata=metadata,
        season=2,
        episode=1,
    )

    assert matcher(build_search_result(file_id=1, title="Bluey S02E01 Dance Mode"), "Bluey S02E01") is True
    assert matcher(build_search_result(file_id=2, title="Blue S02E01 SK TIT MKV"), "Bluey S02E01") is True
    assert matcher(build_search_result(file_id=3, title="Blue Bloods S02E01 mkv"), "Bluey S02E01") is False
    assert matcher(build_search_result(file_id=4, title="Blue Lights S02E01 (2024) sk tit mkv"), "Bluey S02E01") is False
    assert matcher(build_search_result(file_id=5, title="Project Blue Book S02E01 HD CZ dabing mkv"), "Bluey S02E01") is False
    assert matcher(build_search_result(file_id=6, title="Bluey S02E02 Dance Mode"), "Bluey S02E01") is False
