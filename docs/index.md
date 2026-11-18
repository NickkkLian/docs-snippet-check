# textkit

textkit counts words and builds URL slugs. It has three functions:
`word_count`, `top_words` and `slugify`.

Copy the `textkit/` folder next to your code; it has no dependencies.

```bash
python3 -c "import textkit; print(textkit.__all__)"
```

## Count words

```python
import textkit

text = "the cat sat on the mat. The cat left."
count = textkit.word_count(text)
assert count == 9
```

The next block uses `text` from the block above. Words are lowercased before
they are counted:

```python
>>> textkit.top_words(text, 2)
[('the', 3), ('cat', 2)]
```

## Next

- [Counting words](guide/counting.md)
- [Slugs](guide/slugs.md)
