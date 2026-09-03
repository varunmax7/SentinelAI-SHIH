# Image Processing Integration (NVIDIA NIM Vision)

## Goal

When a user submits an online hazard report with a photo, the photo currently
contributes nothing to the AI accuracy score — `analyze_media()` in `app.py`
just returns a hardcoded score per hazard type. This adds a **real** image
processing step using an NVIDIA NIM vision-language model, and folds its
result into the accuracy engine as a **4th parameter**, alongside the
existing three:

| # | Parameter | Source | Old weight | New weight |
|---|-----------|--------|-----------|-----------|
| 1 | Weather/Early-Warning heatmap density | `_validate_heatmap_match` | 33% | 25% |
| 2 | Live climate alignment | `_validate_climate_alignment` | 33% | 25% |
| 3 | User quality/credibility | `_calculate_user_quality_score` | 34% | 25% |
| 4 | **Image processing (NVIDIA NIM)** | `_validate_image_processing` (new) | — | 25% |

## Flow

1. User submits a report with a photo → saved to `static/uploads/` as
   `report.image_file` (already happens today, unchanged).
2. `analyze_report_with_ai(report)` calls the renamed
   `validate_report_accuracy_4params(report)`.
3. That function calls the new `_validate_image_processing(report)`:
   - Reads the image file from disk, base64-encodes it.
   - Sends it to OpenRouter's chat completions API
     (`https://openrouter.ai/api/v1/chat/completions`) using the NVIDIA
     Nemotron vision-reasoning model
     (`nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` by default,
     configurable via `NVIDIA_VISION_MODEL`), as an OpenAI-style chat
     completion with the image embedded as a base64 data URI.
   - The prompt asks the model to first describe what it actually sees in
     the photo (this becomes the `caption` — "what it saw"), then compare
     that against the reporter's claimed `hazard_type`, and end its
     response with strict JSON:
     `{"caption": str, "matches_hazard": bool, "confidence": 0-1, "detected_hazard": str, "reasoning": str}`.
   - Because Nemotron is a *reasoning* model, it may emit `<think>...</think>`
     chain-of-thought or surrounding prose despite instructions — the
     response is stripped of `<think>` blocks and the JSON object is pulled
     out with a regex rather than assumed to be the entire message body.
   - The response is parsed into a `score` (0-1), a `caption` (kept
     verbatim so "what it saw" is preserved), and a human-readable
     `analysis` string that embeds the caption — matching the shape used by
     the other 3 parameter functions so it drops cleanly into the existing
     pattern, and flows through to `report.ai_analysis` since
     `analyze_report_with_ai` folds every parameter's `analysis` string
     into the text it stores on the report.
4. If there's no image, no API key configured, the request times out, or the
   API errors — fall back to a neutral score (0.5) with an explanatory
   analysis string, exactly like the existing parameters do on failure. This
   is a scoring signal, not a hard gate — it must never crash report
   submission or verification.
5. `validate_report_accuracy_4params` averages all four scores at 25% each
   and returns `parameter_4_image_processing` alongside the existing three
   parameter keys, plus the same `overall_accuracy` / `accuracy_percent` /
   `detailed_analysis` shape as before.
6. `analyze_report_with_ai` in `app.py` no longer needs its separate/legacy
   "Media Analysis" heuristic step (`analyze_media`) — that hardcoded
   per-hazard-type guess is superseded by the real NIM-based parameter 4.
   The flash-message breakdown and the `/api/report/<id>/accuracy_4param`
   JSON endpoint (renamed from `accuracy_3param`) are updated to include the
   image processing parameter.

## Configuration

New environment variables (added to `.env`, documented in README):

- `NVIDIA_API_KEY` — required. This actually holds an **OpenRouter** API key
  (`sk-or-v1-...` from https://openrouter.ai/keys), kept under this name for
  continuity with the original setup. `OPENROUTER_API_KEY` is also accepted
  as a fallback if set instead. Without either, parameter 4 always falls
  back to the neutral 0.5 score with analysis
  `"Image processing unavailable: NVIDIA_API_KEY not configured"`.
- `NVIDIA_VISION_MODEL` — optional, defaults to
  `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`.

## Why this model/endpoint

The model is NVIDIA's Nemotron omni vision-reasoning model, served through
OpenRouter's free tier rather than NVIDIA's own `build.nvidia.com` NIM
catalog (OpenRouter uses `provider/model-name` IDs and `sk-or-v1-...` keys,
which is what's actually configured). OpenRouter exposes an
OpenAI-API-compatible `chat/completions` endpoint — no separate SDK, just
`requests`, matching how `_validate_climate_alignment` already calls
Open-Meteo with plain `requests`. A VLM (rather than a narrow classifier)
lets one prompt do hazard-type verification for every `hazard_type` in the
app (tsunami, storm_surge, high_waves, coastal_flooding, abnormal_tide,
swell_surge) without hardcoding a model per category.

## Naming/compatibility notes

- `validate_report_accuracy_3params` → `validate_report_accuracy_4params`
  (only referenced internally in `utils.py`/`app.py`; no template or JS
  depends on the old name, confirmed by repo-wide grep).
- Route `/api/report/<id>/accuracy_3param` → `/api/report/<id>/accuracy_4param`
  (not called from any frontend JS/template today, safe to rename).
- Existing keys `parameter_1_heatmap`, `parameter_2_climate`,
  `parameter_3_user_quality` are unchanged; `parameter_4_image_processing`
  is additive.

## Performance & reliability iteration

The free-tier Nemotron model shares a small worker pool on OpenRouter and
gets saturated often (`ResourceExhausted: Worker local total request limit
reached`), and being a reasoning model it can also legitimately take 20-40s
to answer. Both problems compound with report submission being synchronous,
so `_validate_image_processing` was hardened in a few ways:

- **Image downscaling** (`_downscale_image_for_upload`) — resizes to max
  768px and re-encodes as JPEG (quality 75) via Pillow before upload, since
  phone-camera originals can be several MB and the model doesn't need that
  resolution.
- **Low reasoning effort** — `"reasoning": {"effort": "low"}` in the request
  body trims Nemotron's chain-of-thought length.
- **A real hard deadline** (`_post_with_deadline`, `HARD_DEADLINE_SECONDS = 9`)
  — plain `requests` `timeout=` only bounds the gap *between chunks* of a
  response, not its total duration, so a reply that trickles in slowly can
  sail past it while still taking 30-40s wall-clock. The call is run in a
  worker thread and `future.result(timeout=...)` is used to actually cap
  total time; the abandoned thread finishes or errors on its own rather than
  blocking the caller.
- **Retry only on the cheap failure mode** — OpenRouter's "saturated" error
  comes back as an HTTP 200 with an `{"error": ...}` body in ~1-2s, so that
  case is retried once. A genuine hard-deadline timeout is *not* retried
  against the same model, since the provider is just slow and retrying would
  only double the wait.
- **Fallback model chain** — if the primary model (Nemotron) fails or times
  out, one more attempt is made against `minimax/minimax-m3:free`, a
  different (non-reasoning) VLM behind an independent worker pool. Since
  saturation is model/provider-specific, trying a second model meaningfully
  raises the odds of getting a real analysis instead of the neutral 0.5
  fallback. Whichever model actually answers is reported back in the
  `model` field.

Net effect: typical latency dropped from 20-40s to a few seconds on the
happy path, worst case is bounded at roughly 2× `HARD_DEADLINE_SECONDS`
(~18s) instead of open-ended, and overall success rate improved because a
saturated primary model no longer means an automatic fallback score.

## Severity score

The vision prompt also asks for `severity` (`low`/`medium`/`high`/`critical`)
and `severity_score` (0-1) — how dangerous the photo itself looks, discounted
by 0.3× if the photo doesn't match the claimed hazard at all.
`validate_report_accuracy_4params` blends this with a per-`hazard_type`
baseline severity (`_HAZARD_BASELINE_SEVERITY` — tsunami/storm_surge/
coastal_flooding skew high, abnormal_tide/swell_surge lower) at 70% image /
30% baseline when a usable image analysis exists, or the baseline alone
otherwise. The result (`severity`, `severity_score`, `severity_percent`) is
surfaced in the final AI score text, the submission flash message, and the
`/api/report/<id>/accuracy_4param` JSON response.

## Out of scope

- No new UI. The score already surfaces through the existing flash message
  and JSON endpoint; a dedicated "image processing" widget can be a
  follow-up if wanted.
- No image storage/retention changes — reuses the existing uploaded file.
- No fine-tuning — uses the general-purpose hosted NIM VLM as-is.
