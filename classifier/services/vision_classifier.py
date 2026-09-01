"""
Optional vision classification layer -- Layer 4b, a genuine image-based
*category* signal, distinct from the pixel-color extraction in
image_analysis.py (which only ever produced an attribute, never a category
vote -- that was the specific weakness flagged in review Priority 6).

This module sends the actual product photo to a vision-capable LLM and asks
it to pick the closest taxonomy category, exactly the same pattern already
used for the optional text LLM layer (llm_classifier.py). The result is
fused into engine.py's weighted scoring as a real, independent vote (15% of
the total confidence weight -- see WEIGHTS in engine.py), not just used to
tag an attribute.

Like llm_classifier.py, this is OFF by default and requires network + an
API key neither of which are available in the sandbox this was built in.
It activates automatically, with no code changes, once ANTHROPIC_API_KEY is
set:

    export ANTHROPIC_API_KEY=sk-...
    python manage.py classify_catalogue "Product List.xlsx" --with-images --with-vision

Written carefully against the standard Anthropic SDK multimodal message
shape, but -- like llm_classifier.py -- unverified by an actual API call.
Treat it as a real, ready-to-test integration point, not a confirmed
working feature, until you've run it once with a live key.
"""

import base64
import json
import os

import requests

from classifier.services.taxonomy_data import TAXONOMY

_category_choices_text = "\n".join(
    f"- {key}: {cat['path']}" for key, cat in TAXONOMY.items()
)


def is_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def classify_image(image_url):
    """
    Returns {"category": <key>, "confidence": 0-100} or None if unavailable/failed.
    Caller (engine.py) treats this as one more vote in the weighted fusion,
    never as the sole decision -- so a failure here just means this layer
    contributes nothing, not that classification stops (Q8).
    """
    if not is_available() or not image_url:
        return None

    try:
        import anthropic

        # Download the image ourselves so we can pass raw bytes -- some
        # vision APIs also accept a bare URL, but base64 is the most
        # portable path across providers/model versions.
        img_response = requests.get(image_url, timeout=8)
        img_response.raise_for_status()
        media_type = img_response.headers.get("Content-Type", "image/jpeg").split(";")[0]
        image_b64 = base64.b64encode(img_response.content).decode("utf-8")

        client = anthropic.Anthropic()
        prompt = f"""Look at this product photo and classify it into exactly one of these categories:

{_category_choices_text}

Respond with ONLY a JSON object, no other text:
{{"category": "<one of the category keys above>", "confidence": <0-100 integer>}}
If the image doesn't clearly match any category, use a low confidence rather than guessing."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = response.content[0].text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)

        if parsed.get("category") not in TAXONOMY:
            return None  # don't trust a hallucinated category key

        return parsed

    except Exception:  # noqa: BLE001 - a vision call failing must not stop the batch (Q8)
        return None
