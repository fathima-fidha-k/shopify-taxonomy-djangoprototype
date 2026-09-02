from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from classifier.services.taxonomy_data import TAXONOMY

_category_keys = list(TAXONOMY.keys())


def _reference_text(category):
    """Build a short reference document per category from its name, keywords, and attribute values."""
    parts = [category["path"].replace(">", " ")] + category["keywords"]
    for values in category["attributes"].values():
        parts.extend(values)
    return " ".join(parts)


_reference_corpus = [_reference_text(TAXONOMY[k]) for k in _category_keys]

# Fit once at import time -- 11 short documents, negligible cost.
_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
_category_matrix = _vectorizer.fit_transform(_reference_corpus)


def score_all(product_text):
    """
    Returns {category_key: score_0_to_100} for every taxonomy category,
    based on cosine similarity between the product's text and each
    category's reference text.
    """
    if not product_text.strip():
        return {k: 0 for k in _category_keys}

    product_vec = _vectorizer.transform([product_text])
    similarities = cosine_similarity(product_vec, _category_matrix)[0]

    return {
        key: round(float(sim) * 100)
        for key, sim in zip(_category_keys, similarities)
    }
