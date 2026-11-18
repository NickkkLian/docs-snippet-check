"""textkit: three small text helpers. This is the example project the docs run against."""
import re
from collections import Counter

__all__ = ["word_count", "top_words", "slugify"]

_WORD = re.compile(r"[a-z0-9']+")


def _words(text):
    return _WORD.findall(text.lower())


def word_count(text):
    """Return the number of words in `text`."""
    return len(_words(text))


def top_words(text, n=3):
    """Return the `n` most frequent words as (word, count) pairs.

    Words are lowercased. Ties keep the order in which the words first appear.
    """
    return Counter(_words(text)).most_common(n)


def slugify(text, max_length=None):
    """Turn `text` into a URL slug: lowercase words joined by hyphens.

    `max_length` cuts the slug to at most that many characters.
    """
    if not isinstance(text, str):
        raise TypeError(f"slugify() expects str, got {type(text).__name__}")
    slug = "-".join(re.findall(r"[a-z0-9]+", text.lower()))
    if max_length is not None:
        slug = slug[:max_length].strip("-")
    return slug
