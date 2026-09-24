"""On-demand vision captioning of real ground imagery.

Live webcam coverage is a hard external ceiling, not something this codebase
can widen: Bengaluru has exactly one registered public Windy webcam and
Hyderabad has two, verified directly against Windy's API out to a 100 km
search radius (see ingest/streetview.py's module docstring). Every cell in a
city that shares a webcam necessarily shows the SAME frame - there is no
second camera to show instead.

What genuinely differs cell to cell is which real photo is nearest (live
webcam vs. archival street-level shot), and what is actually visible in it
right now. This module reads that out with a vision-language model, so two
different locations get two different, real, location-grounded sentences
even on the (common) occasions where the underlying photo is shared or
sparse. It is a caption of what the model sees in that one frame - it is not
a hazard detector and never gates or overrides anything computed elsewhere.

Shares one provider chain with the report-photo grader in
utils.py::_validate_image_processing - see `vision_routes` there for which
models are tried, in what order, and which were checked and rejected. OpenAI
leads (billed, verified), the free OpenRouter models back it up, so a billing
or quota wall degrades to a free caption rather than to no caption.

Called lazily, once per drawer open, never on the scheduled compute pass
across ~1800 cells - that would multiply into real, ongoing API cost for a
feature that is a nice-to-have overlay, not a scoring input.

Returns either a caption dict or an `{'error', 'reason'}` dict. The two
failures it distinguishes are worth keeping apart: a provider thumbnail that
404s and a model that will not answer need completely different fixes, and
reporting the first as the second sent an operator hunting a model problem
that was really a dead CDN URL.
"""

import io
import os
import time

import requests

# Up to 2 keys x 2 models = 4 attempts (see caption_ground_image), vs. the
# 2-attempt budget utils.py's report-photo path uses - given more room here
# so a dead first key doesn't starve the still-live second key's attempts.
# A dead key itself fails fast (~0.5s, see the 401 branch below), so this
# mostly buys headroom for genuine free-tier saturation on the live key.
TOTAL_BUDGET_SECONDS = 28
FIRST_TRY_DEADLINE_SECONDS = 8
HARD_DEADLINE_SECONDS = 14


PROMPT = (
    "You are looking at a real street-level or webcam photo from a city "
    "digital twin used for disaster monitoring. Describe ONLY what is "
    "actually visible in THIS image - weather, standing water/flooding, "
    "smoke/fire, crowding, traffic, road condition. Do not guess at things "
    "not visible. Reply with ONLY this compact JSON object, no prose, no "
    "markdown fencing: "
    '{"caption": "one short sentence on exactly what the image shows", '
    '"hazard_visible": true or false, '
    '"hazard_label": "short label of the hazard if visible, else null"}'
)


def vision_available():
    from utils import vision_routes

    return bool(vision_routes())


def caption_ground_image(image_url, label=None):
    """A short, honest, model-generated reading of one real photo/frame.

    `None` on any failure - missing key, download failure, both models
    unreachable, or a reply with no parseable caption. Never raises: this is
    an optional overlay on imagery that must keep rendering without it.
    """
    if not image_url:
        return None
    from utils import mark_vision_model_dead, vision_request_kwargs, vision_routes

    routes = vision_routes()
    if not routes:
        return None

    # A dead provider thumbnail and a dead model are different failures with
    # different fixes, and reporting the first as the second sent an operator
    # looking at the model for a problem that was a 404 on KartaView's CDN.
    # Verified: of two KartaView URLs, one served 334 KB and the other 404'd.
    try:
        image_bytes, mime_type = _fetch_and_downscale(image_url)
    except Exception as exc:  # noqa: BLE001 - a fetch failure just means no caption
        return {'error': 'image_unfetchable',
                'reason': 'The provider no longer serves this image (%s).'
                          % type(exc).__name__}
    if not image_bytes:
        return {'error': 'image_unfetchable',
                'reason': 'The provider returned an empty image.'}

    import base64
    from utils import _extract_json_object, _post_with_deadline  # reuse, don't duplicate

    image_b64 = base64.b64encode(image_bytes).decode('utf-8')

    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    dead_keys = set()
    for index, (provider, api_key, model_id) in enumerate(routes):
        if api_key in dead_keys:
            continue
        is_last = index == len(routes) - 1
        remaining = deadline - time.monotonic()
        if remaining < 2:
            break
        cap = HARD_DEADLINE_SECONDS if is_last else FIRST_TRY_DEADLINE_SECONDS
        attempt_deadline = min(cap, remaining)

        # Provider-shaped, because the two APIs differ in ways that each
        # fail silently. The old body here hard-coded max_tokens=300 against
        # a *reasoning* model, which spent the whole allowance thinking and
        # returned content=None - the actual cause of the "Vision model call
        # failed or timed out" an analyst saw. See vision_request_kwargs.
        request_kwargs = vision_request_kwargs(
            provider, api_key, model_id, PROMPT, mime_type, image_b64,
            attempt_deadline)

        try:
            response = _post_with_deadline(request_kwargs, attempt_deadline)
        except TimeoutError:
            continue
        except Exception:  # noqa: BLE001
            continue

        if response.status_code == 401:
            # This key is dead - skip its remaining model candidates instead
            # of burning budget re-proving the same failure.
            dead_keys.add(api_key)
            continue
        if response.status_code in (403, 404):
            # Retired or gated - it will answer the same way every time.
            mark_vision_model_dead(model_id)
            continue
        if response.status_code != 200:
            continue
        try:
            body = response.json()
        except ValueError:
            continue
        choices = body.get('choices') or []
        if not choices:
            continue
        message = choices[0].get('message') or {}
        parsed = (_extract_json_object(message.get('content'))
                  or _extract_json_object(message.get('reasoning')))
        if not parsed:
            continue
        caption = (parsed.get('caption') or '').strip()
        if not caption:
            continue
        # Models asked for 'label or null' sometimes emit the literal string
        # "null" rather than JSON null - a truthy value that would otherwise
        # render as a real hazard label.
        hazard_label = parsed.get('hazard_label')
        if isinstance(hazard_label, str) and hazard_label.strip().lower() in ('', 'null', 'none', 'n/a'):
            hazard_label = None
        return {
            'caption': caption,
            'hazard_visible': bool(parsed.get('hazard_visible', False)),
            'hazard_label': hazard_label,
            'model': model_id,
            'label': label,
        }
    return {'error': 'model_failed',
            'reason': 'No vision model returned a usable answer within the time budget.'}


def _fetch_and_downscale(image_url, max_dimension=640, jpeg_quality=70, timeout=10):
    """Same downscale-before-send discipline as the report-photo path
    (utils.py::_downscale_image_for_upload) - the model needs no more
    resolution than this to describe a scene, and it is the single biggest
    lever on request latency."""
    response = requests.get(image_url, timeout=timeout)
    response.raise_for_status()
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(response.content))
        img = img.convert('RGB')
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=jpeg_quality, optimize=True)
        return buf.getvalue(), 'image/jpeg'
    except Exception:  # noqa: BLE001 - send the original bytes rather than fail
        content_type = (response.headers.get('Content-Type') or 'image/jpeg').split(';')[0]
        return response.content, content_type or 'image/jpeg'
