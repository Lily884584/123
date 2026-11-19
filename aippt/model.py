"""Configurable model client for later phases.

Phase 3 uses this only when AIPPT_MODEL_* env vars are set.
Without credentials, analyzers run locally and do not call the network.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class ModelClient(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return model text for a single turn."""


@dataclass(frozen=True)
class ModelConfig:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0


def load_model_config() -> ModelConfig | None:
    """Read AIPPT_MODEL_BASE_URL, AIPPT_MODEL_API_KEY, AIPPT_MODEL_NAME."""

    base_url = (os.environ.get("AIPPT_MODEL_BASE_URL") or "").strip()
    api_key = (os.environ.get("AIPPT_MODEL_API_KEY") or "").strip()
    model = (os.environ.get("AIPPT_MODEL_NAME") or "").strip()
    if not base_url or not api_key or not model:
        return None
    timeout_raw = (os.environ.get("AIPPT_MODEL_TIMEOUT") or "60").strip()
    try:
        timeout = float(timeout_raw)
    except ValueError:
        timeout = 60.0
    return ModelConfig(
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        timeout_seconds=timeout,
    )


def get_model_client() -> ModelClient | None:
    config = load_model_config()
    if config is None:
        return None
    return OpenAICompatibleClient(config)


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(self, config: ModelConfig) -> None:
        self._config = config

    def complete(self, *, system: str, user: str) -> str:
        url = f"{self._config.base_url}/chat/completions"
        payload = {
            "model": self._config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._config.timeout_seconds
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"model request failed: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("model response missing message content") from exc
