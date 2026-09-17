---
name: mail-triage-typesafe
description: Attach an optional, calibrated urgency/reply/nature label to an email a bot is already triaging via Composio's Gmail toolkit. Use when a personal agent categorizes inbox mail and wants a second, confidence-scored opinion alongside its own judgment -- never in place of it.
---

# Mail triage with TypeSafe

`typesafe-classify`, shipped next to this file, calls TypeSafe (a typed-
judgment API) to label one email with `urgency`, `requires_reply`, and
`nature`. It is a **decoration**, not a decision: your own triage logic runs
exactly as it does today, and this only *adds* a secondary label when
TypeSafe answers with high confidence.

## When to use it

After you have already formed your own category for an email (via whatever
rule or judgment you normally use), optionally call:

```bash
SKILL="$(git rev-parse --show-toplevel)/.agents/skills/mail-triage-typesafe/typesafe-classify"
"$SKILL" --subject "$SUBJECT" --sender "$SENDER" --snippet "$SNIPPET"
```

- On a confident answer, it prints one line of JSON:
  `{"urgency": "now", "requires_reply": "yes", "nature": "actionable"}`.
  Attach these as secondary fields (e.g. `typesafe_urgency`,
  `typesafe_requires_reply`, `typesafe_nature`) alongside your own category
  field -- never overwrite your own field with them.
- On every fallback path (disabled, no key, network error, timeout, low
  confidence, or two failures in this run tripping the breaker), it prints
  **nothing** and exits 0. Treat empty output exactly like never having
  called it: proceed with your own categorization, unchanged.

Do not gate any action (archiving, flagging, auto-replying) on this output
alone. It is advisory only.

## Privacy -- what gets sent

Only three fields ever leave this process, and only when the flag below is
on:

- `--subject` verbatim
- `--sender`'s domain only (the local part before `@` is stripped before the
  request is built)
- `--snippet`, redacted first: quoted-reply lines (`>` prefixed, and
  everything after an `On ... wrote:` line) are stripped, then the result is
  capped at 500 characters

No attachments, no headers, no full body, no thread history. Pass the
shortest snippet that captures the email's own new content -- do not paste
an entire thread into `--snippet`.

## Enabling it

Off by default. A bot that never sets `RAKAZO_TYPESAFE_ENABLED` behaves
exactly as if this skill did not exist.

| Variable | Default | Purpose |
|---|---|---|
| `RAKAZO_TYPESAFE_ENABLED` | unset (off) | `1`/`true`/`yes`/`on` turns it on |
| `RAKAZO_TYPESAFE_API_KEY` | unset | explicit key, wins over Keychain |
| `RAKAZO_TYPESAFE_TIMEOUT_SECS` | `2.0` | per-call timeout, no retry |
| `RAKAZO_TYPESAFE_MIN_CONFIDENCE` | `0.9` | floor below which an answer is discarded |

Without `RAKAZO_TYPESAFE_API_KEY`, it falls back to the macOS Keychain item
`typesafe-api-key` for the current user. **Never** put a real key in a
commit, a script default, or chat output -- this is a public repository (see
`AGENTS.md`).

## Why this shape

Rakazo's own `AGENTS.md` already requires every external service to be
optional and behind a provider-neutral interface, with vendor specifics
confined to an adapter. This skill IS that adapter: the only file that
touches TypeSafe's API is `typesafe-classify`, and removing TypeSafe
entirely is delete this directory, delete the one call site that invokes
it, delete two env vars -- no change to how mail is actually triaged today.

TypeSafe is run on free early-adopter credits with no guaranteed price or
duration, so nothing in this skill is allowed to become load-bearing: a
caller that never invokes it, or that ignores empty output, must see
identical behavior to a caller that does.
