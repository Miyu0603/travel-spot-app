"""Validation for LLM extraction output.

The model is prompted to return specific enum values, but a prompt is not a
guarantee (AI-01). Postgres stores `region` as a native enum, so a single
hallucinated "Japan" instead of "japan" raises a DataError and loses an
extraction that already paid for Apify, Whisper, GPT and Google Places.

Everything the model returns is therefore normalised here before it reaches the
ORM. Unrecognised values fall back rather than raise: the caller has already
spent the money, so salvaging a usable record beats discarding it.
"""

from pydantic import BaseModel, field_validator, model_validator

from app.models.spot import ContinentEnum, RegionEnum

# Values the model reaches for instead of the ones it was asked to use.
_REGION_ALIASES = {
    "tw": RegionEnum.TAIWAN,
    "台灣": RegionEnum.TAIWAN,
    "臺灣": RegionEnum.TAIWAN,
    "taiwan": RegionEnum.TAIWAN,
    "jp": RegionEnum.JAPAN,
    "日本": RegionEnum.JAPAN,
    "japan": RegionEnum.JAPAN,
}

_TEXT_FIELDS = (
    "title",
    "description",
    "address",
    "business_hours",
    "notes",
    "country",
    "city",
)


def _normalise_region(value: object, country: str = "") -> RegionEnum:
    text = str(value or "").strip().lower()
    for candidate in (text, country.strip().lower()):
        if not candidate:
            continue
        for member in RegionEnum:
            if candidate in (member.value.lower(), member.name.lower()):
                return member
        if candidate in _REGION_ALIASES:
            return _REGION_ALIASES[candidate]
    # "france", "" or anything else: we know it is not Taiwan or Japan, and
    # "international" is the honest answer rather than a guess.
    return RegionEnum.INTERNATIONAL


def _normalise_continent(value: object) -> ContinentEnum | None:
    text = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not text:
        return None
    for member in ContinentEnum:
        if text in (member.value.lower(), member.name.lower()):
            return member
    return None


class ExtractedSpot(BaseModel):
    """One spot as returned by the LLM, coerced into something storable."""

    title: str
    description: str = ""
    address: str = ""
    business_hours: str = ""
    notes: str = ""
    region: RegionEnum = RegionEnum.INTERNATIONAL
    continent: ContinentEnum | None = None
    country: str = ""
    city: str = ""

    @field_validator(*_TEXT_FIELDS, mode="before")
    @classmethod
    def _coerce_text(cls, value: object) -> str:
        # The model sometimes emits null, a number, or a list for a text field.
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item).strip() for item in value if item)
        return str(value).strip()

    @model_validator(mode="before")
    @classmethod
    def _normalise_enums(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalised = dict(data)
        normalised["region"] = _normalise_region(
            normalised.get("region"), str(normalised.get("country") or "")
        )
        normalised["continent"] = _normalise_continent(normalised.get("continent"))
        return normalised

    @model_validator(mode="after")
    def _continent_only_for_international(self) -> "ExtractedSpot":
        # The column exists to qualify "international"; a continent alongside
        # taiwan/japan is noise that the region already implies.
        if self.region is not RegionEnum.INTERNATIONAL:
            object.__setattr__(self, "continent", None)
        return self


def parse_extracted_spots(raw_spots: object) -> tuple[list[dict], int]:
    """Validate the model's spot list.

    Returns the usable spots and how many were discarded, so the caller can say
    so instead of quietly returning fewer results than the post contained.
    """
    if not isinstance(raw_spots, list):
        return [], 0

    usable: list[dict] = []
    discarded = 0
    for raw in raw_spots:
        if not isinstance(raw, dict):
            discarded += 1
            continue
        try:
            spot = ExtractedSpot(**raw)
        except Exception:
            discarded += 1
            continue
        # A spot with no name cannot be shown, searched, or deduplicated.
        if not spot.title:
            discarded += 1
            continue
        usable.append(spot.model_dump())
    return usable, discarded
