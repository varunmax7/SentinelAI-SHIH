"""Structured-output LLM client, over OpenRouter.

A small direct client rather than a LangChain chat model, for two reasons:

  * `langchain-openai` requires Python >= 3.10 and this venv is 3.9, so the
    usual `ChatOpenAI(base_url=...)` route is not available here.
  * OpenRouter serves reasoning and non-reasoning models behind one API, and
    the reasoning ones put their chain of thought in a separate `reasoning`
    field while `content` can come back empty if `max_tokens` is small. That
    quirk is worth handling explicitly rather than burying in an adapter.

The contract is deliberately narrow: hand it a Pydantic schema and a prompt,
get back a validated instance or `None`. `None` always means "fall back to the
deterministic path" - this module never raises into the graph.
"""

import json
import re

import requests

from . import config as twin_config

ENDPOINT = 'https://openrouter.ai/api/v1/chat/completions'

# OpenRouter asks for these so usage shows up attributed rather than anonymous.
_HEADERS_EXTRA = {
    'HTTP-Referer': 'https://sentinel-ai.local',
    'X-Title': 'Sentinel AI Urban Digital Twin',
}


class StructuredLLM(object):
    """Calls one model and validates the reply against a Pydantic schema."""

    def __init__(self, api_key=None, model=None, timeout=None, max_tokens=2000):
        self.api_key = api_key or twin_config.LLM_API_KEY
        self.model = model or twin_config.AGENT_MODEL
        self.timeout = timeout or twin_config.LLM_TIMEOUT_S
        self.max_tokens = max_tokens
        self.calls = 0
        self.tokens = 0
        self.cost = 0.0
        self.last_error = None

    def available(self):
        return bool(self.api_key)

    def invoke(self, schema, prompt, system=None):
        """Prompt -> validated `schema` instance, or None."""
        if not self.available():
            return None

        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        # strict=True first. Some models reject a strict JSON schema they
        # cannot satisfy exactly; retrying non-strict gets a usable answer from
        # those rather than dropping straight to the offline fallback.
        for strict in (True, False):
            payload = {
                'model': self.model,
                # Extraction and summarisation, not creative writing.
                'temperature': 0,
                'max_tokens': self.max_tokens,
                'messages': messages,
                'response_format': {
                    'type': 'json_schema',
                    'json_schema': {
                        'name': schema.__name__,
                        'strict': strict,
                        'schema': schema.model_json_schema(),
                    },
                },
            }
            parsed = self._attempt(schema, payload)
            if parsed is not None:
                return parsed
        return None

    def _attempt(self, schema, payload):
        try:
            self.calls += 1
            response = requests.post(
                ENDPOINT,
                headers=dict(_HEADERS_EXTRA,
                             **{'Authorization': 'Bearer %s' % self.api_key,
                                'Content-Type': 'application/json'}),
                json=payload,
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_error = '%s: %s' % (type(exc).__name__, exc)
            return None

        if response.status_code != 200:
            self.last_error = 'HTTP %d: %s' % (response.status_code, response.text[:200])
            return None

        try:
            body = response.json()
        except ValueError:
            self.last_error = 'response was not JSON'
            return None

        usage = body.get('usage') or {}
        self.tokens += usage.get('total_tokens') or 0
        self.cost += usage.get('cost') or 0.0

        choices = body.get('choices') or []
        if not choices:
            self.last_error = body.get('error', {}).get('message', 'no choices returned')
            return None

        content = (choices[0].get('message') or {}).get('content')
        if not content:
            # A reasoning model that spent its whole budget thinking. Say so
            # precisely: "empty reply" would send someone hunting the wrong bug.
            self.last_error = ('model returned no content (reasoning models can '
                               'consume the whole max_tokens budget - raise it '
                               'or use a non-reasoning model)')
            return None

        return self._validate(schema, content)

    def _validate(self, schema, content):
        text = _strip_fences(content)
        try:
            return schema.model_validate_json(text)
        except Exception:  # noqa: BLE001
            pass
        # Some models wrap the object in prose despite response_format. Salvage
        # the outermost JSON object rather than discarding a good answer.
        match = re.search(r'\{.*\}', text, re.S)
        if match:
            try:
                return schema.model_validate(json.loads(match.group(0)))
            except Exception as exc:  # noqa: BLE001
                self.last_error = 'schema validation failed: %s' % str(exc)[:160]
                return None
        self.last_error = 'no JSON object in the reply'
        return None

    def stats(self):
        return {'calls': self.calls, 'tokens': self.tokens,
                'cost_usd': round(self.cost, 6), 'model': self.model,
                'last_error': self.last_error}


def _strip_fences(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return text.strip()
