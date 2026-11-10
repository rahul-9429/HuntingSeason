from typing import Optional

Band = tuple[int, Optional[int]]

STAGE_BANDS: dict[str, Band] = {
    "seed": (1, 200),
    "series a": (1, 200),
    "growth": (201, 5000),
    "series b": (201, 5000),
    "public": (5001, None),
}


def band_for(stage: str) -> Optional[Band]:
    label = " ".join(stage.lower().split())
    for keyword, band in STAGE_BANDS.items():
        if keyword in label:
            return band
    return None


def in_band(employee_count: int, band: Band) -> bool:
    low, high = band
    return low <= employee_count and (high is None or employee_count <= high)


def fits(stages: list[str], employee_count: Optional[int]) -> bool:
    if not stages or employee_count is None:
        return True
    bands = [band for band in map(band_for, stages) if band is not None]
    if not bands:
        return True
    return any(in_band(employee_count, band) for band in bands)
