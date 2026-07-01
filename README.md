# Provenance Guard

A backend classification system for creative platforms that need to surface AI-attribution
labels on submitted content. Accepts text submissions, runs them through a two-signal
detection pipeline, returns a confidence score and transparency label, and handles creator
appeals against misclassifications.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the repo root (never commit this):

```
GROQ_API_KEY=your_key_here
```

Start the server:

```bash
python3 app.py
```

The API runs on `http://localhost:5000`.

---

## API Endpoints

### POST /submit

Accepts a piece of text for attribution analysis.

**Request body:**
```json
{
  "text": "The text to analyse (minimum 40 words)",
  "creator_id": "a string identifying the submitting creator"
}
```

**Response:**
```json
{
  "content_id": "uuid",
  "attribution": "likely_ai | uncertain | likely_human",
  "confidence": 0.74,
  "llm_score": 0.80,
  "style_score": 0.63,
  "label": "transparency label text shown to readers"
}
```

### POST /appeal

Allows a creator to contest a classification.

**Request body:**
```json
{
  "content_id": "uuid from the original /submit response",
  "creator_reasoning": "explanation of why the classification is incorrect"
}
```

**Response:**
```json
{
  "content_id": "uuid",
  "status": "under_review",
  "message": "Your appeal has been received and will be reviewed by a human moderator."
}
```

Returns `404` if `content_id` is not found. Returns `409` if an appeal has already been filed.

### GET /log

Returns the most recent audit log entries.

```bash
curl http://localhost:5000/log
```

Filter by status for the human review queue:

```bash
curl "http://localhost:5000/log?status=under_review"
```

---

## Architecture

A submitted text travels through four stages before a response is returned:

1. **Rate limiter** — Flask-Limiter enforces per-IP limits before any detection runs.
2. **Detection pipeline** — Two independent signals run in sequence: the LLM signal
   (Groq API) and the stylometric signal (pure Python). Each returns a score in [0, 1].
3. **Confidence scorer** — The two scores are combined into a single weighted average.
4. **Label generator** — The combined score maps to one of three transparency label
   variants, and a structured audit entry is written.

An appeal updates the existing audit entry in place — `status` flips to `under_review`
and `appeal_reasoning` is appended to the original classification record.

See `planning.md` for the full architecture diagram and design rationale.

---

## Detection Signals

### Signal 1 — LLM semantic assessment (Groq, llama-3.3-70b-versatile)

The model is prompted to estimate the probability that a text is AI-generated, returning
a single float. This captures holistic semantic and stylistic coherence — patterns like
over-balanced sentence structures, formulaic transition phrases, and the absence of the
idiosyncratic tangents and register shifts that characterise authentic human writing.

**What it misses:** Casual AI text written in an informal tone may score lower than
warranted. Highly formal human writing (academic, legal) may score higher.

**Output:** `llm_score` — float in [0.0, 1.0].

### Signal 2 — Stylometric heuristics (pure Python)

Three structural sub-metrics computed without external libraries:

- **Type-token ratio (TTR)** — unique words / total words, capped at the first 200 words.
  AI text tends toward slightly lower vocabulary diversity.
- **Sentence length variance** — standard deviation of per-sentence word counts. AI text
  produces more uniform sentence lengths; human writing varies more.
- **Punctuation density** — count of expressive marks (`;:—–()…`) divided by word count.
  AI text consistently under-uses these marks.

Each sub-metric is normalised to [0, 1] and averaged equally into `style_score`.

**What it misses:** Short casual text with naturally punchy sentences scores high on the
AI side even when human-written, because low sentence-length variance is structurally
indistinguishable from AI uniformity at short lengths.

**Output:** `style_score` — float in [0.0, 1.0].

---

## Confidence Scoring

The two signals are combined as a weighted average:

```
combined_score = (0.65 × llm_score) + (0.35 × style_score)
```

The LLM signal receives 65% weight because it captures holistic semantic patterns the
stylometric signal cannot. The stylometric signal receives 35% — enough to move borderline
cases but not enough to override a confident LLM verdict.

**Thresholds:**

| Score range | Attribution | Meaning |
|---|---|---|
| < 0.35 | `likely_human` | No strong indicators of AI generation |
| 0.35 – 0.65 | `uncertain` | Mixed signals; no confident conclusion |
| ≥ 0.65 | `likely_ai` | Strong indicators of AI generation |

The uncertain band is deliberately wide (30 points). The threshold to reach `likely_ai`
(0.65) is higher than the threshold to exit `likely_human` (0.35) — reaching a positive
AI label requires a stronger signal than reaching a human label, reflecting the higher
cost of a false positive on a creative platform.

**Example scores from calibration testing:**

| Input type | llm_score | style_score | combined | attribution |
|---|---|---|---|---|
| Clearly AI-generated | 0.800 | 0.629 | 0.7400 | likely_ai |
| Clearly human-written | 0.230 | 0.537 | 0.3374 | likely_human |
| Formal human writing | 0.420 | 0.773 | 0.5437 | uncertain |
| Lightly edited AI | 0.230 | 0.706 | 0.3967 | uncertain |

The clearly AI and clearly human inputs produce a combined score difference of ~0.40,
confirming the scoring produces meaningful variation rather than clustering near a midpoint.

---

## Transparency Labels

The label text returned in the API response and displayed to readers. All three variants
are implemented in `_generate_label()` in `app.py`.

**Variant A — High-confidence AI (score ≥ 0.65)**

```
⚠ This content was likely generated with AI assistance.

Our system analysed this submission using two independent methods and found
strong indicators of AI-generated text. This label does not mean the work
has no value — it is provided so you can make an informed decision about
what you're reading.

If you are the creator and believe this is incorrect, you can submit an
appeal below.
```

**Variant B — Uncertain (0.35 ≤ score < 0.65)**

```
ℹ Attribution unclear

Our system found mixed signals in this submission. We could not reliably
determine whether this content was written by a human or generated with AI
assistance. No strong conclusion is drawn either way.

Creators can submit an appeal at any time to provide additional context.
```

**Variant C — High-confidence human (score < 0.35)**

```
✓ This content appears to be human-written.

Our system found no strong indicators of AI generation in this submission.
This is not a guarantee — detection tools are imperfect — but the signals
we measured are consistent with human authorship.
```

**Design notes:** Variant A explicitly states that AI-assisted work is not valueless —
this reduces stigma and adversarial appeals. Variant B says "mixed signals" rather than
"we don't know," which is more accurate about what was actually measured. Variant C hedges
explicitly to set accurate expectations.

---

## Appeals Workflow

Creators submit a `POST /appeal` with their `content_id` and a written explanation. The
system updates the original audit entry — `status` flips to `under_review`, and
`appeal_reasoning` and `appeal_timestamp` are added to the record. No automated
re-classification occurs; a human reviewer queries `GET /log?status=under_review` to
see all pending appeals, with the full original classification context alongside the
creator's reasoning.

Re-submitting an appeal for the same `content_id` returns a `409` to prevent duplicate
review queue entries.

---

## Rate Limiting

Limits applied to `POST /submit`:

- **10 requests per minute per IP**
- **100 requests per day per IP**

**Reasoning:** A real creator submitting their own work would realistically make a few
submissions per session — never 10 within 60 seconds. The per-minute limit is permissive
enough for legitimate use but stops naive flood attacks. The daily cap prevents a slow
drip attack that would evade the per-minute limit while still consuming Groq API credits.

**Observed rate-limit behaviour** (12 rapid requests, limit is 10/minute):

```
400
400
400
400
400
400
400
400
400
400
429
429
```

The first 10 requests return `400` because the test text is under 40 words — the
word-count validation fires before the Groq call. The rate limiter counts all requests
regardless of validation outcome, so requests 11 and 12 correctly return `429 Too Many
Requests`.

---

## Audit Log

Every attribution decision is written as a structured JSON entry. The log is in-memory
for this implementation (resets on server restart). Sample entry with an appeal filed:

```json
{
  "appeal_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
  "appeal_timestamp": "2026-07-01T01:40:02.424545+00:00",
  "attribution": "likely_ai",
  "confidence": 0.7572,
  "content_id": "eb05782a-8de4-4da7-8c7b-1b307ef019c3",
  "creator_id": "test-user-1",
  "label": "⚠ This content was likely generated with AI assistance. ...",
  "llm_score": 0.8,
  "punct_density": 0.0,
  "sent_variance": 6.1101,
  "status": "under_review",
  "style_score": 0.6776,
  "timestamp": "2026-07-01T01:39:14.209796+00:00",
  "ttr": 0.8696
}
```

Every entry captures: `timestamp`, `content_id`, `creator_id`, `attribution`,
`confidence`, `llm_score`, `style_score`, `ttr`, `sent_variance`, `punct_density`,
`label`, `status`, `appeal_reasoning`, `appeal_timestamp`.

---

## Known Limitations

**Short casual writing scores high on stylometric AI indicators.** Casual human writing
with short punchy sentences — "ok so i finally tried that new ramen place downtown and
honestly? underwhelming." — produces low sentence-length variance because the sentence
structure is naturally uniform, not because it resembles AI output. This causes the
stylometric signal to push the combined score upward even when the LLM signal correctly
identifies the text as human. In testing, this nearly pushed a clearly human text into
the `uncertain` zone. The 65/35 weighting and wide uncertain band mitigate this but do
not eliminate it.

**Non-native English speakers writing formally** are at elevated risk of false positives.
Careful, grammatically correct writing with limited expressive punctuation and consistent
sentence length can score AI-like on all three stylometric sub-metrics simultaneously.
The `uncertain` label is likely the correct outcome for this writer rather than
`likely_human`, but `likely_ai` is a real risk on the stylometric side — the LLM signal
is the main defence here.

---

## Spec Reflection

The planning.md spec helped most during confidence scoring calibration. Having the
thresholds (< 0.35, 0.35–0.65, ≥ 0.65) and the asymmetry rationale written down before
implementation meant that when the stylometric signal returned 0.667 for every input
during initial testing, there was a clear standard to debug against — the spec said
`clearly_human` should land below 0.35, so the anchors were wrong, not the thresholds.

The main divergence from the spec was the signal weighting. The spec specified 60/40
(LLM/stylometric), but after calibration against the four test inputs the weighting was
adjusted to 65/35. The stylometric signal has a stronger-than-expected bias toward
flagging short casual text as AI-like, so reducing its weight was necessary to let the
LLM's confident low scores on human text dominate. The planning.md `## AI Tool Plan`
section also specified using it as a prompting guide for code generation, which worked
as intended — providing the exact signal spec and architecture diagram to the AI tool
produced code that matched the planned output format without requiring significant
correction.

---

## AI Usage

**Instance 1 — Flask app skeleton and LLM signal function (Milestone 3).** The detection
signals section and architecture diagram from `planning.md` were provided to Claude, and
it was asked to generate the Flask app skeleton with a `POST /submit` stub and a
`get_llm_score()` function. The output was reviewed before use: the prompt structure and
JSON parsing matched the spec, but the error handling was verified to use a sensible
fallback (0.5) rather than raising. The audit log structure and field names were adjusted
to match the exact schema defined in planning.md.

**Instance 2 — Stylometric signal and combined scorer (Milestone 4).** The Signal 2
section and uncertainty representation section were provided, and Claude was asked to
generate `get_style_score()` and `get_combined_score()`. The initial normalisation anchors
(TTR: 0.55–0.80, variance: 10–35, punct: 0.02–0.10) were generated from the spec but
produced a stylometric signal that returned 0.667 for every input regardless of content.
This was diagnosed by printing sub-scores individually — the anchors were calibrated for
longer texts and all short test inputs were clamping to extreme values that cancelled out.
The anchors were recalibrated empirically (TTR: 0.75–0.92, variance: 4–12, punct: 0–0.04)
and the weighting was adjusted from 60/40 to 65/35 based on observed behaviour.
