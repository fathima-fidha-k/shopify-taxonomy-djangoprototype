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
