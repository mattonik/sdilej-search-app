from __future__ import annotations

from app.models import TitleMetadata
from app.search_utils import (
    build_episode_query_variants,
    build_tv_episode_result_scorer,
    build_tv_search_aliases,
    select_effective_tv_search_aliases,
)
from tests.conftest import FakeSdilejClient, build_search_result


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


def test_tv_episode_result_scorer_prefers_exact_show_and_episode_title_matches() -> None:
    scorer = build_tv_episode_result_scorer(
        show_aliases=["Bluey"],
        season=1,
        episode=1,
        episode_name="Magic Xylophone",
    )

    exact_with_title = scorer(build_search_result(file_id=1, title="Bluey S01E01 Magic Xylophone"), "Bluey S01E01")
    exact_plain = scorer(build_search_result(file_id=2, title="Bluey S01E01 1080p FHD"), "Bluey S01E01")
    unrelated = scorer(build_search_result(file_id=3, title="Women in Blue S01E01 CZtit V OBRAZE 1080p mkv"), "Bluey S01E01")
    wrong_episode = scorer(build_search_result(file_id=4, title="Bluey S01E02 Magic Xylophone"), "Bluey S01E01")

    assert exact_with_title is not None
    assert exact_plain is not None
    assert exact_with_title > exact_plain
    assert unrelated is None
    assert wrong_episode is None


def test_tv_episode_result_scorer_only_accepts_weak_single_word_aliases_at_title_start() -> None:
    scorer = build_tv_episode_result_scorer(
        show_aliases=["Bluey", "Blue"],
        season=2,
        episode=1,
        episode_name="Dance Mode",
    )

    bluey_score = scorer(build_search_result(file_id=1, title="Bluey S02E01 Dance Mode"), "Bluey S02E01")
    localized_score = scorer(build_search_result(file_id=2, title="Blue S02E01 SK TIT MKV"), "Bluey S02E01")
    bloods_score = scorer(build_search_result(file_id=3, title="Blue Bloods S02E01 mkv"), "Bluey S02E01")
    lights_score = scorer(build_search_result(file_id=4, title="Blue Lights S02E01 sk tit mkv"), "Bluey S02E01")

    assert bluey_score is not None
    assert localized_score is not None
    assert bluey_score > localized_score
    assert bloods_score is None
    assert lights_score is None


def test_build_episode_query_variants_prefers_short_episode_patterns() -> None:
    assert build_episode_query_variants(["Bluey"], 1, 1) == [
        "Bluey S01E01",
        "Bluey 1x01",
        "Bluey 1x1",
    ]


def test_select_effective_tv_search_aliases_prefers_aliases_with_probe_hits() -> None:
    client = FakeSdilejClient(
        responses_by_query={
            "Shaun the Sheep": [build_search_result(file_id=10, title="Shaun the Sheep collection")],
            "Ovecka Shaun": [],
            "Vesela farma": [build_search_result(file_id=11, title="Vesela farma archiv")],
        }
    )

    aliases = select_effective_tv_search_aliases(
        client=client,
        show_name="Shaun the Sheep",
        search_aliases=["Shaun the Sheep", "Ovecka Shaun", "Vesela farma"],
        category="video",
    )

    assert aliases == ["Shaun the Sheep", "Vesela farma"]
