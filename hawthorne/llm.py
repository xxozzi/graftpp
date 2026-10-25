"""Thin async OpenAI-compatible chat client (vLLM on Modal) with JSON parsing.

Supports Qwen3 thinking mode: vLLM's `--reasoning-parser qwen3` returns the
<think> block as `reasoning_content` (or `reasoning`) and the answer as `content`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class LLMConfig:
    base_url: str = os.environ.get("HAWTHORNE_BASE_URL", "http://localhost:8000/v1")
    api_key: str = os.environ.get("HAWTHORNE_API_KEY", "hawthorne")
    model: str = os.environ.get("HAWTHORNE_MODEL", "hawthorne")
    # Qwen3 recommended sampling for thinking mode
    temperature: float = 0.6
    top_p: float = 0.95
    top_k: int = 20
    max_tokens: int = 6000
    max_tokens_cap: int = 9500       # ceiling when retrying after truncated thinking
    timeout: float = 600.0
    max_retries: int = 24
    concurrency: int = 48


@dataclass
class LLMResponse:
    text: str                       # final answer content (after </think>)
    parsed: dict | None
    reasoning: str = ""             # thinking content
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency: float = 0.0
    attempts: int = 1
    truncated: bool = False
    finish_reason: str = ""
    fallback_nothink: bool = False


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Best-effort extraction of the first JSON object in a completion."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = _JSON_RE.search(text)
    if not m:
        return None
    cand = m.group(0)
    for attempt in (cand, cand.replace("\n", " ")):
        try:
            return json.loads(attempt)
        except Exception:
            continue
    for i in range(len(cand), max(len(cand) - 300, 0), -1):
        try:
            return json.loads(cand[:i] + "}")
        except Exception:
            continue
    return None


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        limits = httpx.Limits(max_connections=cfg.concurrency + 16,
                              max_keepalive_connections=cfg.concurrency + 16,
                              keepalive_expiry=300.0)
        self._client = httpx.AsyncClient(timeout=cfg.timeout, limits=limits)
        self._sem = asyncio.Semaphore(cfg.concurrency)
        self.errors: dict[str, int] = {}
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_calls = 0
        self.total_truncations = 0

    async def close(self):
        await self._client.aclose()

    async def chat(self, system: str, user: str, *, temperature: float | None = None,
                   max_tokens: int | None = None, seed: int | None = None,
                   require_json: bool = True, thinking: bool = True,
                   extra: dict | None = None) -> LLMResponse:
        max_tok = self.cfg.max_tokens if max_tokens is None else max_tokens
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "top_p": self.cfg.top_p if thinking else 0.8,
            "top_k": self.cfg.top_k,
            "max_tokens": max_tok,
            "chat_template_kwargs": {"enable_thinking": thinking},
        }
        if seed is not None:
            payload["seed"] = seed
        if extra:
            payload.update(extra)
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        last_err: Exception | None = None
        truncated_once = False
        fallback_nothink = False
        n_trunc = 0
        for attempt in range(1, self.cfg.max_retries + 1):
            t0 = time.time()
            try:
                async with self._sem:
                    r = await self._client.post(f"{self.cfg.base_url}/chat/completions",
                                                json=payload, headers=headers)
                if r.status_code >= 500 or r.status_code == 429:
                    raise RuntimeError(f"server {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                data = r.json()
                choice = data["choices"][0]
                msg = choice["message"]
                text = msg.get("content") or ""
                reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
                finish = choice.get("finish_reason", "") or ""
                usage = data.get("usage", {}) or {}
                self.total_prompt_tokens += usage.get("prompt_tokens", 0)
                self.total_completion_tokens += usage.get("completion_tokens", 0)
                parsed = extract_json(text) if require_json else None
                truncated = finish == "length" and (require_json and parsed is None)
                if truncated and attempt < self.cfg.max_retries:
                    # Output ran past the budget.  Bounded escalation:
                    #   thinking call : 1st truncation -> retry once at max_tokens_cap (new seed)
                    #                   2nd truncation -> fall back to non-thinking mode
                    #   non-thinking  : retry with a new seed (loops are seed-dependent)
                    self.total_truncations += 1
                    truncated_once = True
                    n_trunc += 1
                    if seed is not None:
                        payload["seed"] = seed + 1000 * attempt
                    if payload["chat_template_kwargs"]["enable_thinking"]:
                        if n_trunc == 1:
                            payload["max_tokens"] = max(payload["max_tokens"], self.cfg.max_tokens_cap)
                        else:
                            payload["chat_template_kwargs"] = {"enable_thinking": False}
                            payload["max_tokens"] = 800
                            payload["top_p"] = 0.8
                            fallback_nothink = True
                    continue
                if require_json and parsed is None and attempt < self.cfg.max_retries:
                    if seed is not None:
                        payload["seed"] = seed + 1000 * attempt
                    payload["messages"][1] = {
                        "role": "user",
                        "content": user + "\n\nIMPORTANT: your previous reply was not a valid "
                                           "JSON object. Output ONLY the JSON object."}
                    continue
                self.total_calls += 1
                return LLMResponse(text=text, parsed=parsed, reasoning=reasoning,
                                   prompt_tokens=usage.get("prompt_tokens", 0),
                                   completion_tokens=usage.get("completion_tokens", 0),
                                   latency=time.time() - t0, attempts=attempt,
                                   truncated=truncated_once, finish_reason=finish,
                                   fallback_nothink=fallback_nothink)
            except Exception as e:
                # 4xx (except 429) is deterministic (e.g. context overflow): retrying the same payload can't help
                if isinstance(e, httpx.HTTPStatusError) and 400 <= e.response.status_code < 500:
                    raise
                last_err = e
                key = type(e).__name__ + ":" + str(e)[:60]
                self.errors[key] = self.errors.get(key, 0) + 1
                n_err = sum(self.errors.values())
                if n_err in (1, 10, 100) or n_err % 500 == 0:
                    print(f"[llm] {n_err} errors so far; latest: {key}", flush=True)
                await asyncio.sleep(min(2 * 1.5 ** attempt, 20))
        raise RuntimeError(f"LLM call failed after {self.cfg.max_retries} attempts: {last_err}")
