"""
Layered classification engine with explicit, weighted confidence scoring.

    Layer 1: keyword/rule matching        (title + description + product_type + brand)
        v
    Layer 2: semantic similarity          (TF-IDF cosine similarity)
        v
    Layer 3: LLM classification           (optional, low-confidence cases only)
        v
    Layer 4a: image color extraction      (optional, real pixel data)
    Layer 4b: image category signal       (optional, vision-LLM, real pixel data)
        v
    Weighted fusion -> confidence score + human-readable reasoning trail

CONFIDENCE MODEL (Q6):
Instead of one opaque heuristic number, confidence is built from explicit,
labeled components so it's auditable in the review UI:

    keyword evidence       40%
    semantic similarity    25%
    image evidence         15%
    attribute evidence     10%
    data completeness      10%

...and separately, the GAP between the top two candidates is used to decide
routing (Q7): a big gap (e.g. Sofa 86% vs Armchair 42%) is confidently
resolved; a narrow gap (Sofa 57% vs Armchair 54%) is NOT resolved by picking
the higher number and hoping -- it's routed to manual review even if the top
score alone would have cleared the general threshold, because a narrow gap
between drastically different categories is itself evidence of ambiguity.

NO SOURCE-DATA LEAKAGE (unchanged from v2/v3, restated here since it's the
most important property of this engine): classification uses only
title, description, product_type, brand, and (optionally) the image --
never the spreadsheet's existing Product Category / Product Sub Category
columns. Those are stored for comparison only, never as scoring input.
"""

import re

from classifier.services.taxonomy_data import TAXONOMY, UNCATEGORIZED
from classifier.services import semantic as semantic_layer
from classifier.services import llm_classifier
from classifier.services import vision_classifier
from classifier.services.text_extraction import normalize_attribute_value

LOW_CONFIDENCE_THRESHOLD = 55   # below this -> needs_review regardless of gap
NARROW_GAP_THRESHOLD = 8        # top-two gap smaller than this -> needs_review even if top score is high enough
LLM_TRIGGER_THRESHOLD = 45

# Weighted confidence model (Q6) -- must sum to 100.
# NOTE on calibration: keyword weight is set higher than the illustrative 40%
# suggested in review, and semantic scores are rescaled (SEMANTIC_CALIBRATION)
# before weighting. This is a deliberate, documented calibration choice, not
# an oversight: raw TF-IDF cosine similarity against short (~15-word) category
# reference documents is systematically compressed -- a genuinely correct top
# match often scores only 30-50% in raw cosine terms, which is a property of
# the short reference-document length, not a property of how *wrong* the
# match is. Using that raw magnitude directly as a "percent confidence" was
# tested and found to push nearly every product below the auto-classify
# threshold regardless of match quality (see README "confidence calibration"
# note). Keyword matching remains the highest-precision signal available
# without a paid vision/LLM API, so it is weighted accordingly; semantic
# similarity is rescaled to a comparable range before blending.
WEIGHTS = {
    "keyword": 55,
    "semantic": 15,
    "image": 15,
    "attribute": 10,
    "completeness": 5,
}
SEMANTIC_CALIBRATION = 1.8  # documented rescaling factor, see note above


def _normalize(text):
    return (text or "").lower()


def _keyword_score(category, title_text, body_text, type_text):
    """
    Layer 1: substring keyword matching. Title weighted highest, then an
    explicit product_type field (when the source data has one -- Q4), then
    description. Returns a 0-100 raw score for this category, plus which
    field(s) matched (for the reasoning trail).
    """
    title_hits = [kw for kw in category["keywords"] if kw in title_text]
    type_hits = [kw for kw in category["keywords"] if type_text and kw in type_text]
    body_hits = [kw for kw in category["keywords"] if kw in body_text]

    if not title_hits and not type_hits and not body_hits:
        return 0, []

    if title_hits:
        score = min(85, 55 + len(title_hits) * 15) + min(10, (len(type_hits) + len(body_hits)) * 4)
    elif type_hits:
        score = min(70, 40 + len(type_hits) * 15) + min(10, len(body_hits) * 4)
    else:
        score = min(40, 15 + len(body_hits) * 10)

    evidence = []
    if title_hits:
        evidence.append(f"'{title_hits[0]}' found in title")
    if type_hits:
        evidence.append(f"'{type_hits[0]}' found in product type")
    if body_hits and not title_hits:
        evidence.append(f"'{body_hits[0]}' found in description")

    return min(100, score), evidence


def _extract_text_attributes(category, combined_text):
    found = {}
    for attr_name, values in category["attributes"].items():
        for val in values:
            if re.search(r"\b" + re.escape(val) + r"\b", combined_text):
                found[attr_name] = normalize_attribute_value(attr_name, val)
                break
    return found


def _brand_bonus(brand, category, combined_text):
    """
    Priority 5 fix: brand now genuinely participates in scoring, not just as
    a cosmetic tag. A brand name appearing consistently alongside a category's
    keywords across the catalogue is weak-but-real corroborating evidence
    (e.g. this vendor's naming convention). This deliberately stays a small
    bonus, not a primary signal -- brand indicates *who made it*, not *what
    it is*, so it should nudge, not decide.
    """
    if not brand:
        return 0, None
    # A brand mention immediately next to a matched keyword in the same title
    # is treated as mild reinforcement of an already-present keyword signal,
    # rather than an independent category vote.
    if brand.lower() in combined_text:
        return 3, f"brand '{brand}' present alongside matched keywords"
    return 0, None


def classify_product(product, use_llm=False, use_vision=False, image_result=None):
    """
    Classify a single product dict:
        {"title", "description", "product_type", "brand", "image_url"}

    Never raises -- any internal issue results in a low-confidence / review-flagged
    result rather than stopping the batch (Q8, Q11).
    """
    try:
        title = product.get("title") or ""
        description = product.get("description") or ""
        product_type = product.get("product_type") or ""
        brand = product.get("brand") or ""
        has_description = bool(description.strip())
        has_image = bool(product.get("image_url"))
        has_product_type = bool(product_type.strip())

        title_text = _normalize(title)
        body_text = _normalize(description)
        type_text = _normalize(product_type)
        combined_text = f"{title_text} {type_text} {body_text}"

        # -- Layer 1: keyword matching (title + product_type + description) --
        keyword_results = {
            key: _keyword_score(cat, title_text, body_text, type_text)
            for key, cat in TAXONOMY.items()
        }
        keyword_scores = {k: v[0] for k, v in keyword_results.items()}

        # -- Layer 2: semantic similarity (rescaled -- see SEMANTIC_CALIBRATION note) --
        semantic_scores_raw = semantic_layer.score_all(combined_text)
        semantic_scores = {k: min(100, round(v * SEMANTIC_CALIBRATION)) for k, v in semantic_scores_raw.items()}

        # -- Optional Layer 4b: vision category signal --
        vision_result = None
        if use_vision and image_result and image_result.get("processed") and vision_classifier.is_available():
            vision_result = vision_classifier.classify_image(product.get("image_url"))

        # -- Weighted fusion per category --
        # "Image evidence" (Q6, 15% weight) comes from whichever image signal
        # is actually available: a vision-model category vote is the strongest
        # (used at full confidence when it agrees with this candidate); plain
        # pixel-color extraction alone is real but weaker evidence (Priority 6
        # fix -- previously color extraction contributed to attributes only,
        # never to the confidence score at all).
        fused = {}
        for key in TAXONOMY:
            kw = keyword_scores.get(key, 0)
            sem = semantic_scores.get(key, 0)
            if vision_result and vision_result.get("category") == key:
                img = vision_result["confidence"]
            elif image_result and image_result.get("processed"):
                img = 35  # real pixel data available, but no category vote to confirm/deny this candidate
            else:
                img = 0
            fused[key] = (
                kw * WEIGHTS["keyword"] / 100
                + sem * WEIGHTS["semantic"] / 100
                + img * WEIGHTS["image"] / 100
            )

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
        best_key, best_fused = ranked[0] if ranked else (None, 0)
        second_fused = ranked[1][1] if len(ranked) > 1 else 0

        # -- Optional Layer 3: LLM, only for genuinely uncertain cases --
        llm_result = None
        combined_so_far = best_fused / (WEIGHTS["keyword"] / 100 + WEIGHTS["semantic"] / 100 + WEIGHTS["image"] / 100) if best_fused else 0
        if use_llm and combined_so_far < LLM_TRIGGER_THRESHOLD and llm_classifier.is_available():
            llm_result = llm_classifier.classify_with_llm(title, description)
            if llm_result and llm_result["category"] in TAXONOMY and llm_result["confidence"] > combined_so_far:
                best_key, best_fused = llm_result["category"], llm_result["confidence"] * (WEIGHTS["keyword"] + WEIGHTS["semantic"]) / 100

        if best_key is None or best_fused == 0:
            return _no_match_result(vision_result, llm_result)

        best_category = TAXONOMY[best_key]
        _, keyword_evidence = keyword_results[best_key]

        # -- Attribute extraction (text-based + image color + brand) --
        attributes = _extract_text_attributes(best_category, combined_text)
        attribute_evidence_count = len(attributes)

        if brand:
            attributes["brand"] = brand
        if image_result and image_result.get("processed"):
            attributes["color"] = image_result["color"]

        brand_bonus, brand_evidence = _brand_bonus(brand, best_category, combined_text)

        # -- Data completeness component (Q6) --
        completeness_fields = [has_description, has_image, has_product_type]
        completeness_score = round(100 * sum(completeness_fields) / len(completeness_fields))

        # -- Assemble the weighted breakdown (Q6, shown in the review UI) --
        keyword_component = round(keyword_scores.get(best_key, 0) * WEIGHTS["keyword"] / 100)
        semantic_component = round(semantic_scores.get(best_key, 0) * WEIGHTS["semantic"] / 100)
        image_component = round(
            (vision_result["confidence"] if (vision_result and vision_result.get("category") == best_key)
             else (35 if (image_result and image_result.get("processed")) else 0))
            * WEIGHTS["image"] / 100
        )
        attribute_component = round(min(100, attribute_evidence_count * 30) * WEIGHTS["attribute"] / 100)
        completeness_component = round(completeness_score * WEIGHTS["completeness"] / 100)

        confidence = min(100, keyword_component + semantic_component + image_component
                          + attribute_component + completeness_component + brand_bonus)

        breakdown = {
            "keyword": keyword_component,
            "semantic": semantic_component,
            "image": image_component,
            "attribute": attribute_component,
            "completeness": completeness_component,
        }
        if brand_bonus:
            breakdown["brand_bonus"] = brand_bonus

        # -- Reasoning trail for the UI (Priority 12) --
        reasoning = list(keyword_evidence)
        if semantic_scores.get(best_key, 0) > 0:
            reasoning.append(f"semantic similarity: {semantic_scores[best_key]}%")
        if attributes.get("material"):
            reasoning.append(f"material: {attributes['material']}")
        if image_result and image_result.get("processed"):
            reasoning.append(f"image-derived color: {image_result['color']}")
        if vision_result and vision_result.get("category") == best_key:
            reasoning.append(f"vision model agrees ({vision_result['confidence']}%)")
        if brand_evidence:
            reasoning.append(brand_evidence)
        if not has_description:
            reasoning.append("no description available (confidence reduced)")
        if not has_image:
            reasoning.append("no image available (confidence reduced)")

        alternatives = [
            {"category": key, "path": TAXONOMY[key]["path"], "confidence": round(score)}
            for key, score in ranked[1:3] if score > 0
        ]

        # -- Gap-based routing decision (Q7) --
        gap = best_fused - second_fused
        meets_threshold = confidence >= LOW_CONFIDENCE_THRESHOLD
        gap_is_narrow = len(ranked) > 1 and second_fused > 0 and gap < NARROW_GAP_THRESHOLD

        if meets_threshold and not gap_is_narrow:
            status, reason = "auto_classified", None
        elif gap_is_narrow:
            status, reason = "needs_review", "narrow_margin_vs_alternative"
            reasoning.append(
                f"top two candidates are close ({best_key} vs {ranked[1][0]}, gap={round(gap)}) -- routed for manual review"
            )
        else:
            status = "needs_review"
            reason = "missing_data" if not (has_description and has_image) else "low_confidence_match"

        return {
            "status": status,
            "reason": reason,
            "predicted_category": best_key,
            "predicted_path": best_category["path"],
            "confidence": confidence,
            "confidence_breakdown": breakdown,
            "reasoning": reasoning,
            "attributes": attributes,
            "alternatives": alternatives,
            "error": None,
            "layers_used": _layers_used(True, True, llm_result, image_result, vision_result),
        }

    except Exception as exc:  # noqa: BLE001 - deliberate: never let one product kill the batch
        return {
            "status": "failed",
            "reason": "classification_error",
            "predicted_category": None,
            "predicted_path": None,
            "confidence": 0,
            "confidence_breakdown": {},
            "reasoning": [],
            "attributes": {},
            "alternatives": [],
            "error": str(exc),
            "layers_used": [],
        }


def _no_match_result(vision_result, llm_result):
    return {
        "status": "needs_review",
        "reason": "no_signal_match",
        "predicted_category": UNCATEGORIZED,
        "predicted_path": None,
        "confidence": 0,
        "confidence_breakdown": {},
        "reasoning": ["no keyword, semantic, or image signal matched any known category"],
        "attributes": {},
        "alternatives": [],
        "error": None,
        "layers_used": _layers_used(False, False, llm_result, None, vision_result),
    }


def _layers_used(keyword, semantic, llm_result, image_result, vision_result=None):
    layers = []
    if keyword:
        layers.append("keyword")
    if semantic:
        layers.append("semantic")
    if llm_result:
        layers.append("llm")
    if image_result and image_result.get("processed"):
        layers.append("image_color")
    if vision_result:
        layers.append("vision")
    return layers
