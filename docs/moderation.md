# Moderation feature

Watches every message for keyword and regex matches, labels what it finds, and
stores it. Heavy labels also delete the message and warn the author in public.

This is **phase 1**. The point of storing full message content is that
`moderation_hits` *is* the training corpus for a fastText classifier later — the
schema is multi-label from day one even though the engine is not.

## Labels

Frozen in `warden/features/moderation/services/labels.py`, not in a table: these
strings become fastText's `__label__` classes, and a label that can drift away
from the trained model without a deploy is a silent footgun. Adding a label means
retraining anyway.

| Label | Meaning | On a hit |
| --- | --- | --- |
| `neutral` | No hit. Cannot be registered — it is the absence of a match | — |
| `negative` | Profanity, insults | recorded |
| `bullying` | Targeted harassment | recorded |
| `crypto` | Coin shilling, wallet-drain bait | recorded |
| `judol` | Online gambling promotion | **deleted + warned** |
| `porn` | Pornographic content and links | **deleted + warned** |
| `sara` | Hate speech on ethnicity, religion, race | **deleted + warned** |
| `scam` | Phishing, fake giveaways, suspicious links | **deleted + warned** |

The four enforced labels are spam/promotion patterns: structured, high precision,
no legitimate reason to be posted. `negative` and `bullying` are plain word lists
whose context the machine never sees — "anjir keren!" is praise — so they are
recorded silently instead of getting someone's message deleted.

When a message hits several enforced labels the warning names the most severe
one, in the order `sara → porn → judol → scam`. All labels are still recorded.

## How matching works

Everything is canonicalised first (`services/normalizer.py`). The direction is
*decode*: `jud0l` → `judol`, never the reverse.

1. NFKD, combining marks dropped — `Melocotón` → `melocoton`
2. `casefold()`
3. Leet map — `0→o 1→i 3→e 4→a 5→s 7→t @→a $→s |→l !→i`
4. Runs of **3 or more** identical characters collapsed to one — `juuudol` →
   `judol`, while `maaf` and `saat` survive untouched

Keywords are stored already normalized and matched with `pyahocorasick`: one pass
over the text finds every keyword at once, however many there are.

**Pass A** scans the normalized text with separators intact, then checks word
boundaries by hand (the character before and after the match must be
non-alphanumeric). This is what keeps `analisis` from matching a keyword `anal`.

**Pass B** scans the same text with every separator removed, which catches
`j u d o l` and `s-l-o-t g-a-c-o-r`. There are no word boundaries left in that
text, so it only runs for keywords whose squeezed form is **5 characters or
longer** (`SQUEEZE_MIN_LEN` in `services/matcher.py`). Short words without
boundaries are exactly what produces false positives.

Regex rules run separately, each against the raw text or the normalized text
depending on its `target` column.

### Known limits

- **Scunthorpe in pass B.** A 5+ character keyword that is a substring of an
  innocent word will fire. Nothing is allowlisted yet, on purpose: the hits table
  is there to tell you *which* terms are actually noisy before you start guessing.
  Raise `SQUEEZE_MIN_LEN` or add an allowlist once the data says so.
- **Shortened URLs are not resolved.** Resolving `bit.ly/xxx` means making an
  outbound request to an address a stranger controls — the bot's IP is exposed to
  whoever owns the link, and a redirect to `169.254.169.254` or `10.x` is an SSRF.
  The presence of a shortener is itself the `scam` signal, and the message is
  already deleted, so resolving would only change the label, not the outcome.
- **Only `message.content`.** Attachments, embeds, usernames and nicknames are
  not scanned.

## Rules

Both keywords and regex rules are **global** — no `guild_id`. This word list is a
property of the language (Indonesian/English), not of the community, and one bot
instance serves one community (see [Configuration](configuration.md)). Hits still
carry `guild_id`.

Removal is **soft** (`enabled = false`). A mistyped bulk add is undoable, and
re-adding a removed term reactivates the same row rather than making a second one.

### Seeded regex

The migration seeds 12 rules with `created_by = NULL`. They are all
**structured patterns** — URLs, numbers, wallet addresses, generated site names.
Literal words like `bokep`, `maxwin` or `anjing` are keywords, not regex, and the
keyword table deliberately starts empty. `negative`, `bullying` and `sara` get no
seeded regex at all: there is no structure there.

Two of them are knowingly noisy and kept anyway, because a false positive costs
one database row and tells you something:

- `\b[a-z]{3,12}(?:88|89|77|99|303|138|168|4d|slot)\b` — the classic judol site
  name shape (`hoki88`, `dewa303`), which also matches game nicknames
- `\b(?:wa|whatsapp|telp|hub(?:ungi)?)\W{0,3}(?:0|\+?62)8\d{7,11}\b` — a WhatsApp
  number with a call to action, which also matches someone honestly sharing a
  contact

Run `/regex list` to see them all with their ids and notes.

## Commands

Owner (the application owner in the Developer Portal) or a member holding one of
`MODERATION_ADMIN_ROLE_IDS`. All replies are ephemeral.

| Command | What it does |
| --- | --- |
| `/keyword add label:<x> keywords:<a, b, c>` | One keyword or many — same path, comma-separated |
| `/keyword remove label:<x> keywords:<a, b>` | Soft removal. Names anything it could not find |
| `/keyword list [label] [show_disabled]` | Paged embed |
| `/regex add label:<x> pattern:<p> [target] [note]` | `target` defaults to `raw` |
| `/regex remove id:<n>` | By id — patterns are painful to retype. Ids come from `/regex list` |
| `/regex list [label] [show_disabled]` | Paged embed with ids |
| `/regex test pattern:<p> text:<t>` | Try a pattern against both raw and normalized text before registering it |
| `/label list` | Every label, its keyword/rule counts, and whether it deletes |

Input is normalized on the way in for both `add` and `remove`, so `JUDOL` and
`judol` are the same row — and `remove` cannot silently match nothing because of
casing.

### Pattern validation

`/regex add` refuses a pattern that:

1. is longer than 200 characters,
2. does not compile, or
3. contains a **nested quantifier** — `(a+)+`, `(a*)*`, `(\w+){2,}` — the shape
   behind essentially every accidental ReDoS.

The nested-quantifier check is static, not a timing test. Python's `re` cannot be
interrupted: timing a candidate means running it in a thread that can never be
cancelled, so a pattern that blows up would burn a core until the process dies and
would hang shutdown. There is no safe probe length — `((a+)+)+` is astronomical at
twenty characters. The check misses overlapping alternations like `(a|a)*`; a
subprocess with a hard kill is the only way to catch those, and is the upgrade
path if one ever gets through.

## Storage

Four tables, no foreign keys, consistent with the rest of the schema — see
[Database & migrations](database.md).

`moderation_hits` holds one row per flagged message including its **full text**;
`moderation_hit_matches` holds one row per reason, so a message that trips a
keyword and two regex rules produces three rows across however many labels.

`matched_term` in `moderation_hit_matches` is a copy, not a lookup: a rule can be
removed without old hits losing the reason they were flagged.

Duplicates are not collapsed. The same spam sent fifty times is fifty rows —
frequency is signal, and deduplication belongs in the export (`SELECT DISTINCT`),
not in the write path.

**This table stores members' chat messages permanently.** See the privacy section
in [Configuration](configuration.md).

## Towards fastText

The export the classifier phase needs is one query:

```sql
SELECT h.content, array_agg(DISTINCT m.label) AS labels
FROM moderation_hits h
JOIN moderation_hit_matches m ON m.hit_id = h.id
GROUP BY h.id, h.content;
```

One row per message with all of its labels — the shape of a fastText multi-label
line (`__label__judol __label__scam <text>`). Check the class balance before
training:

```sql
SELECT label, count(DISTINCT hit_id) FROM moderation_hit_matches GROUP BY label;
```

Two things are worth adding *before* training starts, not after:

- **A feedback control for moderators.** Right now every label in the corpus is
  whatever the keyword matcher decided. Train on that and the model learns to
  imitate the word list, mistakes included — it can never get better than its own
  input. A "false positive" button that relabels a hit to `neutral` turns machine
  guesses into gold labels.
- **Negative examples.** Only flagged messages are stored, so there is no
  `neutral` class to train against. Sampling clean messages is a separate privacy
  decision, deliberately not taken yet.

[`pyleetspeak`](https://pypi.org/project/pyleetspeak/) is a candidate for
augmenting the corpus at that point — it generates camouflaged variants of a text,
which is what teaches a model to recognise obfuscation. It is **not** a runtime
dependency and never should be: it only generates, it cannot decode, so there is
nothing in it to call from `on_message`. Check whether it is still maintained
before pulling it in; the last release was December 2022.
