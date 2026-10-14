"""
Ollama Client with API Key Pool & Rotation for HelixGuard.
Supports Ollama Cloud and self-hosted instances with multi-key round-robin,
automatic failover on rate limits (HTTP 429) or authentication errors,
and graceful fallback to deterministic execution.

Default Model: gemma4:31b
"""

import os
import json
import logging
import threading
from typing import List, Optional, Dict, Any, Tuple
import httpx

logger = logging.getLogger("helixguard.llm_client")


class OllamaKeyPool:
    """
    Thread-safe API key pool for Ollama Cloud or API-gated instances.
    Provides round-robin rotation and automatic failover when a key hits rate limits.
    """

    def __init__(self, keys: Optional[List[str]] = None) -> None:
        if keys is not None:
            self._keys = [k.strip() for k in keys if k.strip()]
        else:
            raw_keys = os.getenv("OLLAMA_API_KEYS", "") or os.getenv("OLLAMA_API_KEY", "")
            self._keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        
        self._index = 0
        self._lock = threading.Lock()

    @property
    def has_keys(self) -> bool:
        return len(self._keys) > 0

    @property
    def count(self) -> int:
        return len(self._keys)

    def get_current_key(self) -> Optional[str]:
        with self._lock:
            if not self._keys:
                return None
            return self._keys[self._index % len(self._keys)]

    def rotate_key(self) -> Optional[str]:
        with self._lock:
            if not self._keys:
                return None
            self._index = (self._index + 1) % len(self._keys)
            return self._keys[self._index]

    def get_headers(self, key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        active_key = key if key is not None else self.get_current_key()
        if active_key:
            headers["Authorization"] = f"Bearer {active_key}"
        return headers


class OllamaClient:
    """
    Client for Ollama with key pooling, retries, and configurable model.
    Default model is gemma4:31b.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        key_pool: Optional[OllamaKeyPool] = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma4:31b")
        self.key_pool = key_pool or OllamaKeyPool()
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        prompt: str,
        format_json: bool = False,
        timeout: Optional[float] = None,
    ) -> Optional[str]:
        """
        Sends a generation prompt to Ollama, rotating through the key pool if
        a rate limit (429) or auth error occurs. Returns response text or None on failure.
        """
        effective_timeout = timeout or self.timeout_seconds
        attempts = max(1, self.key_pool.count)

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"

        for attempt in range(attempts):
            current_key = self.key_pool.get_current_key()
            headers = self.key_pool.get_headers(current_key)

            try:
                with httpx.Client(timeout=effective_timeout) as client:
                    resp = client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                        headers=headers,
                    )

                    # Successful response
                    if resp.status_code == 200:
                        data = resp.json()
                        return data.get("response", "").strip()

                    # Rate limited or auth failed -> rotate key and retry
                    elif resp.status_code in (429, 401, 403) and self.key_pool.has_keys:
                        logger.warning(
                            "Ollama returned HTTP %d with key %s. Rotating to next key in pool.",
                            resp.status_code,
                            f"...{current_key[-4:]}" if current_key and len(current_key) > 4 else "key",
                        )
                        self.key_pool.rotate_key()
                        continue

                    else:
                        logger.warning(
                            "Ollama generate request failed with HTTP %d: %s",
                            resp.status_code,
                            resp.text[:200],
                        )
                        return None

            except Exception as exc:
                logger.debug("Ollama request failed (%s): %s", type(exc).__name__, exc)
                if self.key_pool.has_keys and attempt < attempts - 1:
                    self.key_pool.rotate_key()
                    continue
                return None

        return None


# Global default client instance
default_llm_client = OllamaClient()
