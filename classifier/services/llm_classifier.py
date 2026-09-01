"""
Optional LLM classification layer -- Layer 3 of the pipeline, used only for
products where Layer 1 (keywords) + Layer 2 (semantic similarity) disagree
or both score low. This keeps API costs down: most products never reach
this layer (Q10 - reduce total calls needed).

This layer is OFF by default and has not been executed in this sandbox
(no internet access here to reach any LLM API). It activates automatically,
with no code changes, if an API key is present in the environment:

    export ANTHROPIC_API_KEY=sk-...
    python manage.py classify_catalogue "Product List.xlsx" --with-llm

If no key is set, `is_available()` returns False and the caller (engine.py)
skips this layer entirely -- classification still works end-to-end without it.

The code below uses the standard Anthropic Python SDK request shape. It has
been written carefully and reviewed, but -- unlike the keyword and semantic
layers -- it is unverified by an actual API call, since none was possible
here. Treat it as a real, ready-to-test integration point, not a confirmed
working feature, until you've run it once with a live key.
"""

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
