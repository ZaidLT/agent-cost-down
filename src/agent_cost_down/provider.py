from __future__ import annotations

import asyncio
import os
import time
from collections import deque

import httpx

from .contracts import Limits, ModelSpec, Usage, canonical


class ProviderFailure(Exception):
    """A sanitized provider failure. Never contains response text or credentials."""


class RateLimiter:
    def __init__(self, rpm: int, tpm: int):
        self.rpm, self.tpm = rpm, tpm
        self.calls = deque()
        self.lock = asyncio.Lock()

    async def acquire(self, tokens: int):
        if tokens > self.tpm:
            raise ProviderFailure("One bounded request exceeds the configured token allowance")
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.calls and now - self.calls[0][0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.rpm and sum(x[1] for x in self.calls) + tokens <= self.tpm:
                    self.calls.append((now, tokens))
                    return
                await asyncio.sleep(max(0.01, 60 - (now - self.calls[0][0])))


class DurableRateLimiter:
    def __init__(self, db, rpm, tpm):
        self.db, self.rpm, self.tpm = db, rpm, tpm

    async def acquire(self, tokens):
        while True:
            delay = self.db.rate_delay(tokens, self.rpm, self.tpm)
            if not delay:
                return
            await asyncio.sleep(delay)


def maximum_cost(config):
    limits = config.limits
    # UTF-8 bytes plus protocol overhead conservatively bound input tokens.
    return (
        sum(
            (
                (limits.request_bytes + 4096) * m.input_usd_per_million
                + limits.output_tokens * m.output_usd_per_million
            )
            / 1_000_000
            for m in config.models
        )
        * limits.model_steps
        * (1 + limits.transport_retries)
        * 1.25
    )


class TokenFactory:
    def __init__(self, rpm=1, tpm=100000, client=None, hook=None, limiter=None):
        self.client = client or httpx.AsyncClient(
            base_url="https://api.tokenfactory.nebius.com/v1/",
            headers={"Authorization": "Bearer " + os.environ["NEBIUS_API_KEY"]},
            timeout=httpx.Timeout(600, connect=15),
            follow_redirects=False,
        )
        self.limiter = limiter or RateLimiter(rpm, tpm)
        self.hook = hook

    async def close(self):
        await self.client.aclose()

    async def complete(self, model: ModelSpec, messages, tools, limits: Limits, usage: list):
        body = {
            "model": model.id,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": limits.output_tokens,
            "stream": False,
            **model.settings,
        }
        data = canonical(body).encode()
        if len(data) > limits.request_bytes:
            raise ProviderFailure("Request exceeded the frozen byte limit")
        for attempt in range(1 + limits.transport_retries):
            await self.limiter.acquire(len(data) + 4096 + limits.output_tokens)
            if self.hook:
                self.hook("dispatch", None)
            started = time.monotonic()
            event = Usage(model=model.id, duration_ms=0.0, status="unknown")
            retry_delay = None
            try:
                response = await self.client.post(
                    "chat/completions", content=data, headers={"Content-Type": "application/json"}
                )
                event.request_id = response.headers.get("x-request-id")
                if response.status_code == 429:
                    event.status = "rate_limited"
                    # Do not assume an error was free. Missing usage stays incomplete.
                    retry_delay = min(60.0, max(1.0, float(response.headers.get("retry-after", "2"))))
                    raise ProviderFailure("Provider rate limit")
                if not response.is_success:
                    event.status = "http_error"
                    raise ProviderFailure("Provider rejected the request")
                payload = response.json()
                raw = payload.get("usage") or {}
                incoming, outgoing = raw.get("prompt_tokens"), raw.get("completion_tokens")
                if type(incoming) is int and incoming >= 0 and type(outgoing) is int and outgoing >= 0:
                    event.input_tokens, event.output_tokens = incoming, outgoing
                    event.estimated_usd = (
                        incoming * model.input_usd_per_million + outgoing * model.output_usd_per_million
                    ) / 1_000_000
                event.status = "success"
                message = payload["choices"][0]["message"]
                if not isinstance(message, dict):
                    raise ProviderFailure("Malformed provider response")
                return message
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                event.status = "ambiguous_failure"
                raise ProviderFailure("Provider response unavailable or malformed") from exc
            except asyncio.CancelledError:
                event.status = "interrupted"
                raise
            except ProviderFailure:
                if retry_delay is None or attempt >= limits.transport_retries:
                    raise
            finally:
                event.duration_ms = (time.monotonic() - started) * 1000
                usage.append(event)
                if self.hook:
                    self.hook("usage", event)
            await asyncio.sleep(retry_delay)
