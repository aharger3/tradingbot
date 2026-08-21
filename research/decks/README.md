# decks/

Generated deck HTML. **Gitignored — rebuild, never commit.**

```bash
python research/build_deck.py --name omen-5.3-mixed --n 60 --seed 7
```

`build_deck.py` is the only deck generator, and `deck_ui.py` is the only
definition of a card. If you are about to write deck HTML anywhere else, stop:
that is exactly the drift that made every deck look different.

- 60 cards max. The builder refuses more.
- Never repeats a `card_id` already present in `../marks/*.jsonl`.
- The answer key (engine fires per day) lives in `<name>-manifest.jsonl`, never
  in the HTML.

Marks export to `../marks/`. The standard is `Projects/omen-decks.md` in the
vault.

`_retired/` holds the oversized 5.2 decks (200 and 100 cards) kept only so their
browser-stored marks can still be exported.
