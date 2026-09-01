"""
A small subset of the Shopify Product Taxonomy (Home & Garden > Furniture branch),
hand-mapped for this prototype. In production this would be generated once from
Shopify's published taxonomy files (see the reference link in the assignment)
and stored in the Category/Attribute/AttributeValue tables described in the
written answers (Q5), not hardcoded like this.

Each category carries:
  - path: the full Shopify taxonomy path (for display / GID lookup)
  - keywords: signal words used by the rule-based matcher (Layer 1 / Layer 2
    from written answer Q1) to score a product against this category
  - attributes: which attribute keys are relevant for this category, each with
    a small controlled vocabulary of expected values used for attribute
    extraction from free text
"""

TAXONOMY = {
    "sofas": {
        "path": "Home & Garden > Furniture > Sofas",
        "keywords": ["sofa", "loveseat", "sectional", "couch", "settee"],
        "attributes": {
            "color": ["white", "gray", "grey", "black", "blue", "beige", "green", "red", "brown", "navy"],
            "material": ["leather", "fabric", "velvet", "linen", "polyester", "bonded leather", "upholstered"],
        },
    },
    "armchairs": {
        "path": "Home & Garden > Furniture > Chairs > Armchairs",
        "keywords": ["armchair", "accent chair", "lounge chair", "chaise"],
        "attributes": {
            "color": ["white", "gray", "grey", "black", "blue", "beige", "green", "red", "brown", "navy"],
            "material": ["leather", "fabric", "velvet", "linen", "polyester", "wood", "rattan"],
        },
    },
    "dining_chairs": {
        "path": "Home & Garden > Furniture > Chairs > Dining Chairs",
        "keywords": ["dining chair", "side chair"],
        "attributes": {
            "color": ["white", "gray", "grey", "black", "walnut", "natural", "beige"],
            "material": ["wood", "metal", "rattan", "plastic", "upholstered"],
        },
    },
    "stools": {
        "path": "Home & Garden > Furniture > Chairs > Stools",
        "keywords": ["bar stool", "counter stool", "stool"],
        "attributes": {
            "color": ["white", "gray", "grey", "black", "walnut", "natural", "beige"],
            "material": ["wood", "metal", "rattan", "plastic", "upholstered"],
        },
    },
    "tables": {
        "path": "Home & Garden > Furniture > Tables",
        "keywords": ["table", "desk", "nightstand", "console"],
        "attributes": {
            "color": ["white", "black", "walnut", "natural", "gray", "brown"],
            "material": ["wood", "glass", "metal", "marble", "rattan"],
        },
    },
    "beds": {
        "path": "Home & Garden > Furniture > Bedroom Furniture > Beds",
        "keywords": ["bed frame", "headboard", "platform bed", " bed "],
        "attributes": {
            "color": ["white", "black", "walnut", "gray", "natural"],
            "material": ["wood", "upholstered", "metal", "rattan"],
        },
    },
    "storage_case_goods": {
        "path": "Home & Garden > Furniture > Bedroom Furniture > Dressers & Chests",
        "keywords": ["dresser", "chest", "cabinet", "case good", "wardrobe"],
        "attributes": {
            "color": ["white", "black", "walnut", "natural", "gray"],
            "material": ["wood", "engineered wood", "metal"],
        },
    },
    "lighting": {
        "path": "Home & Garden > Lighting",
        "keywords": ["lamp", "chandelier", "pendant light", "ceiling light", "sconce"],
        "attributes": {
            "color": ["black", "brass", "gold", "white", "bronze", "chrome"],
            "material": ["metal", "glass", "fabric shade", "wood"],
        },
    },
    "office_chairs": {
        "path": "Home & Garden > Furniture > Office Furniture > Office Chairs",
        "keywords": ["office chair", "task chair", "desk chair", "gaming chair"],
        "attributes": {
            "color": ["black", "white", "gray", "blue"],
            "material": ["mesh", "leather", "fabric", "vinyl"],
        },
    },
    "vanities": {
        "path": "Home & Garden > Furniture > Bathroom Furniture > Vanities",
        "keywords": ["vanity", "bathroom cabinet", "sink cabinet"],
        "attributes": {
            "color": ["white", "black", "walnut", "gray", "natural"],
            "material": ["wood", "engineered wood", "marble"],
        },
    },
    "outdoor_furniture": {
        "path": "Home & Garden > Furniture > Outdoor Furniture",
        "keywords": ["outdoor", "patio", "daybed", "lounge set", "sectional sofa outdoor"],
        "attributes": {
            "color": ["white", "black", "gray", "natural", "beige"],
            "material": ["rattan", "wicker", "aluminum", "teak", "rope"],
        },
    },
    "decor": {
        "path": "Home & Garden > Decor",
        "keywords": ["mirror", "wall art", "pillow", "throw", "decor", "rug"],
        "attributes": {
            "color": ["white", "black", "gray", "multi", "beige"],
            "material": ["fabric", "glass", "wood", "metal"],
        },
    },
}

# Fallback for products where no keyword rule fires at all.
UNCATEGORIZED = "uncategorized"
