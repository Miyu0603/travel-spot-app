"""Tests for the LLM output validation layer.

Runs standalone, no test framework and no API calls:

    python tests/test_extraction_schema.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.spot import ContinentEnum, RegionEnum  # noqa: E402
from app.schemas.extraction import parse_extracted_spots  # noqa: E402
from app.services.ai_extractor import _spot_list_from  # noqa: E402


def one(raw: dict) -> dict:
    spots, _ = parse_extracted_spots([raw])
    assert spots, f"expected {raw} to survive validation"
    return spots[0]


# --- region normalisation: the failure that used to 500 on Postgres ---

def test_documented_region_values_pass_through():
    for value, expected in [
        ("taiwan", RegionEnum.TAIWAN),
        ("japan", RegionEnum.JAPAN),
        ("international", RegionEnum.INTERNATIONAL),
    ]:
        assert one({"title": "t", "region": value})["region"] is expected


def test_wrong_casing_is_repaired():
    for value in ["Japan", "JAPAN", "  japan  "]:
        assert one({"title": "t", "region": value})["region"] is RegionEnum.JAPAN


def test_chinese_and_short_codes_are_repaired():
    assert one({"title": "t", "region": "日本"})["region"] is RegionEnum.JAPAN
    assert one({"title": "t", "region": "台灣"})["region"] is RegionEnum.TAIWAN
    assert one({"title": "t", "region": "TW"})["region"] is RegionEnum.TAIWAN


def test_unknown_region_falls_back_to_international():
    assert one({"title": "t", "region": "france"})["region"] is RegionEnum.INTERNATIONAL


def test_missing_region_is_inferred_from_country():
    assert one({"title": "t", "region": "", "country": "日本"})["region"] is RegionEnum.JAPAN
    assert one({"title": "t", "country": "Taiwan"})["region"] is RegionEnum.TAIWAN


def test_region_with_no_usable_hint_is_international():
    assert one({"title": "t", "region": "", "country": ""})["region"] is RegionEnum.INTERNATIONAL


# --- continent ---

def test_continent_is_normalised():
    spot = one({"title": "t", "region": "international", "continent": "North America"})
    assert spot["continent"] is ContinentEnum.NORTH_AMERICA


def test_invalid_continent_becomes_none_rather_than_failing():
    spot = one({"title": "t", "region": "international", "continent": "Atlantis"})
    assert spot["continent"] is None


def test_continent_is_cleared_for_non_international_regions():
    spot = one({"title": "t", "region": "japan", "continent": "asia"})
    assert spot["continent"] is None


# --- text fields ---

def test_null_text_fields_become_empty_strings():
    spot = one({"title": "t", "description": None, "address": None, "notes": None})
    assert spot["description"] == "" and spot["address"] == "" and spot["notes"] == ""


def test_list_valued_text_field_is_joined():
    spot = one({"title": "t", "notes": ["需預約", "週一公休"]})
    assert spot["notes"] == "需預約, 週一公休"


def test_non_string_scalar_is_coerced():
    assert one({"title": "t", "city": 101})["city"] == "101"


# --- discarding ---

def test_spot_without_a_title_is_discarded():
    spots, discarded = parse_extracted_spots([{"description": "沒有名字"}])
    assert spots == [] and discarded == 1


def test_blank_title_is_discarded():
    spots, discarded = parse_extracted_spots([{"title": "   "}])
    assert spots == [] and discarded == 1


def test_non_dict_entries_are_discarded():
    spots, discarded = parse_extracted_spots(["just a string", 42, None])
    assert spots == [] and discarded == 3


def test_good_spots_survive_alongside_bad_ones():
    spots, discarded = parse_extracted_spots(
        [{"title": "好景點", "region": "Japan"}, {"description": "無名"}]
    )
    assert len(spots) == 1 and discarded == 1
    assert spots[0]["title"] == "好景點"


def test_non_list_input_yields_nothing():
    assert parse_extracted_spots({"title": "t"}) == ([], 0)
    assert parse_extracted_spots(None) == ([], 0)


# --- unwrapping whatever shape the model returned ---

def test_prompted_shape_is_unwrapped():
    assert _spot_list_from({"spots": [{"title": "a"}]}) == [{"title": "a"}]


def test_alternative_wrapper_key_still_works():
    assert _spot_list_from({"景點": [{"title": "a"}]}) == [{"title": "a"}]


def test_bare_array_still_works():
    assert _spot_list_from([{"title": "a"}]) == [{"title": "a"}]


def test_single_bare_spot_object_is_wrapped():
    assert _spot_list_from({"title": "a"}) == [{"title": "a"}]


def test_empty_result_is_an_empty_list():
    assert _spot_list_from({"spots": []}) == []
    assert _spot_list_from({"unexpected": "shape"}) == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
