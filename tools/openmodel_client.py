"""Shared OpenAI-compatible client for the openmodel.ai gateway.

Designed to run from a clean-egress host (or VPN): from the restricted
automation environment the inference path is disrupted (TLS resets / injected
404s) even though GET /v1/models succeeds and the web playground works.

Config precedence (so it coexists with the legacy DEEPSEEK_* scripts):
    OPENMODEL_BASE_URL  > DEEPSEEK_BASE_URL  > https://api.openmodel.ai/v1
    OPENMODEL_MODEL     > DEEPSEEK_MODEL     > deepseek-v4-flash
    OPENMODEL_API_KEY   > DEEPSEEK_API_KEY

Run a smoke test before any bulk job:
    python tools/openmodel_client.py --selftest
    python tools/openmodel_client.py --models
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE = "https://api.openmodel.ai/v1"
DEFAULT_MODEL = "deepseek-v4-flash"


def load_config() -> tuple[str, str]:
    """Return (base_url, model) — non-sensitive request configuration."""
    load_dotenv(dotenv_path=ROOT / ".env")
    base = (os.environ.get("OPENMODEL_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE).rstrip("/")
    model = (os.environ.get("OPENMODEL_MODEL")
             or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL).strip()
    return base, model


def _read_key() -> str:
    """Read the credential in isolation (keeps it out of the tainted URL path)."""
    load_dotenv(dotenv_path=ROOT / ".env")
    key = (os.environ.get("OPENMODEL_API_KEY")
           or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise SystemExit("No OPENMODEL_API_KEY / DEEPSEEK_API_KEY configured in .env")
    return key


class GatewayError(RuntimeError):
    """Raised when the gateway returns its {'success': false, ...} envelope."""


def chat(messages: list[dict], *, temperature: float = 0.0, max_tokens: int = 4000,
         json_object: bool = True, model: str | None = None,
         timeout: int = 120, max_retries: int = 4) -> tuple[str, dict, str]:
    """One chat completion. Returns (content, usage, resolved_model_id).

    Retries on network errors and 5xx with exponential backoff. Surfaces the
    gateway's own 'route not found' / 'no channel' envelope as GatewayError so
    callers get an actionable message instead of a silent hang.
    """
    base, default_model = load_config()
    key = _read_key()
    payload: dict = {
        "model": model or default_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    url = f"{base}/chat/completions"

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} {r.text[:200]}")
            body = r.json()
            if isinstance(body, dict) and body.get("success") is False:
                raise GatewayError(str(body.get("error")))
            if r.status_code != 200:
                raise requests.HTTPError(f"{r.status_code} {str(body)[:200]}")
            content = body["choices"][0]["message"]["content"]
            return content, body.get("usage", {}), body.get("model", payload["model"])
        except GatewayError:
            raise  # config/route problem — retrying will not help
        except (requests.RequestException, KeyError, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"chat failed after {max_retries} attempts: {last_exc}")


def chat_json(messages: list[dict], **kw) -> dict:
    """chat() + json.loads of the content. Strips accidental markdown fences."""
    content, _usage, _model = chat(messages, **kw)
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].lstrip("json").strip() if "```" in text[3:] else text
    return json.loads(text)


def list_models() -> list[str]:
    base, _ = load_config()
    key = _read_key()
    r = requests.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", [])
    return [m.get("id") for m in data]


def _cli() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    base, model = load_config()
    if "--models" in sys.argv:
        print(f"base: {base}")
        for m in list_models():
            print(" ", m)
        return
    # default: --selftest
    print(f"base : {base}\nmodel: {model}")
    t = time.time()
    try:
        content, usage, mid = chat(
            [{"role": "user", "content": "Reply with exactly: OK"}],
            json_object=False, max_tokens=8)
        print(f"OK  {time.time()-t:.1f}s  model={mid}  usage={usage}")
        print(f"reply: {content.strip()!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {time.time()-t:.1f}s  {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
