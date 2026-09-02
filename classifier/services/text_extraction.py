"""
Small text-extraction and normalization helpers shared across the pipeline.
"""

import re

_BRAND_PATTERN = re.compile(r"\bby\s+([A-Z][\w&]+(?:\s+[A-Z][\w&]+){0,2})\s*$")
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
    Extract a brand name
    """
    if not title:
        return ""
    match = _BRAND_PATTERN.search(title.strip())
    return match.group(1).strip() if match else ""


def normalize_attribute_value(attribute_name, raw_value):
    """
    Normalize a raw
    """
    key = raw_value.strip().lower()
    return _NORMALIZATION_MAP.get(key, raw_value.strip().title())

