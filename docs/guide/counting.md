# Counting words

`top_words(text, n=3)` returns the `n` most frequent words as `(word, count)`
pairs, most frequent first. When two words have the same count, the one that
appears first in the text comes first.

```python
import textkit

review = "Great phone. Great screen, great battery, poor camera."
top = textkit.top_words(review)
```

The default `n` is 3, so `top` holds three pairs:

```python
>>> top
[('great', 3), ('phone', 1), ('screen', 1)]
>>> len(top)
3
```

`word_count` and `top_words` agree on what a word is, so the counts add up:

```python
total = sum(count for _, count in textkit.top_words(review, n=100))
assert total == textkit.word_count(review)
```

## Reading from a file

This block needs a file that is not part of the docs, so it is not run:

<!-- snippet: skip -->
```python
with open("reviews.txt") as f:
    print(textkit.top_words(f.read(), n=10))
```
