import json
import os

from classifier.services.taxonomy_data import TAXONOMY

_category_choices_text = "\n".join(
    f"- {key}: {cat['path']}" for key, cat in TAXONOMY.items()
)


def is_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def classify_with_llm(title, description):
    """
    Returns {"category": <key>, "confidence": 0-100, "attributes": {...}}
    or None if the call fails/is unavailable -- caller falls back to the
    keyword/semantic result rather than blocking on this layer (Q8).
    """
    if not is_available():
        return None

    try:
        import anthropic  # imported lazily so the package is only required if this layer is used

        client = anthropic.Anthropic()
        prompt = f"""Classify this product into exactly one of these Shopify taxonomy categories:

{_category_choices_text}

Product title: {title}
Product description: {description}

Respond with ONLY a JSON object, no other text:
{{"category": "<one of the category keys above>", "confidence": <0-100 integer>, "attributes": {{"color": "...", "material": "..."}}}}
If uncertain, lower the confidence rather than guessing a category key that doesn't fit."""

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text)

        if parsed.get("category") not in TAXONOMY:
            return None  # model hallucinated a category key -- don't trust it silently

        return parsed

    except Exception:  # noqa: BLE001 - an LLM call failing must not stop the batch (Q8)
        return None
