# Slugs

`slugify(text, max_length=None)` lowercases `text`, drops punctuation and joins
the words with hyphens.

```python
import textkit

title = "Hello, World! A Guide to textkit"
slug = textkit.slugify(title)
print(slug)
```

```python
>>> slug
'hello-world-a-guide-to-textkit'
```

## Limiting the length

`max_length` cuts the slug to at most that many characters and never leaves a
trailing hyphen:

```python
>>> textkit.slugify(title, max_length=12)
'hello-world'
```

## Errors

`slugify` accepts only strings:

```python
>>> textkit.slugify(42)
Traceback (most recent call last):
    ...
TypeError: slugify() expects str, got int
```
