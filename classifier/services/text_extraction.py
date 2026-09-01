"""
Small text-extraction and normalization helpers shared across the pipeline.
"""

import re

_BRAND_PATTERN = re.compile(r"\bby\s+([A-Z][\w&]+(?:\s+[A-Z][\w&]+){0,2})\s*$")

# Priority 11: normalize raw keyword-matched attribute values to a consistent,
# presentable vocabulary before they're stored/shown -- e.g. "grey" and "gray"
# should never appear as two different values in the UI or database.
_NORMALIZATION_MAP = {
    "grey": "Gray", "gray": "Gray",
    "white": "White", "black": "Black", "beige": "Beige", "brown": "Brown",
    "walnut": "Walnut", "natural": "Natural", "blue": "Blue", "navy": "Navy",
    "green": "Green", "red": "Red", "gold": "Gold", "brass": "Brass",
    "bronze": "Bronze", "chrome": "Chrome",
    "leather": "Leather", "bonded leather": "Bonded Leather", "fabric": "Fabric",
    "velvet": "Velvet", "linen": "Linen", "polyester": "Polyester",
    "upholstered": "Upholstered", "wood": "Wood", "metal": "Metal",
    "glass": "Glass", "marble": "Marble", "rattan": "Rattan", "wicker": "Wicker",
    "aluminum": "Aluminum", "teak": "Teak", "rope": "Rope", "mesh": "Mesh",
    "vinyl": "Vinyl", "plastic": "Plastic", "engineered wood": "Engineered Wood",
}


def extract_brand(title):
    """
    Extract a brand name from a product title, e.g. "Empress Sofa by Modway" -> "Modway".

    This is genuine extraction from unstructured text, not a lookup against a
    pre-existing structured "Brand" column -- the provided catalogue has no
    such column. Falls back to "" if no "by <Brand>" pattern is found, which
    the caller should treat the same as any other missing field (Q2).
    """
    if not title:
        return ""
    match = _BRAND_PATTERN.search(title.strip())
    return match.group(1).strip() if match else ""


def normalize_attribute_value(attribute_name, raw_value):
    """
    Normalize a raw, lowercase keyword match (e.g. "grey", "bonded leather")
    to a consistent display form (e.g. "Gray", "Bonded Leather") -- Priority 11.
    Falls back to title-casing anything not in the explicit map, so an
    unrecognized value still displays reasonably rather than raw/lowercase.
    """
    key = raw_value.strip().lower()
    return _NORMALIZATION_MAP.get(key, raw_value.strip().title())

