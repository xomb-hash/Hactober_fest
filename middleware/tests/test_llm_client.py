"""
Tests for Ollama Client and API Key Pool with gemma4:31b support.
Verifies key pooling, round-robin rotation, 429 failover, Authorization headers,
and seamless fallback to deterministic execution.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
import httpx

from middleware.llm_client import OllamaKeyPool, OllamaClient
from middleware.critic import ContextCritic
from middleware.scout import ScoutAgent


class TestOllamaKeyPool(unittest.TestCase):
    def test_init_with_explicit_keys(self):
        pool = OllamaKeyPool(["key1", " key2 ", "key3 "])
        self.assertTrue(pool.has_keys)
        self.assertEqual(pool.count, 3)
        self.assertEqual(pool.get_current_key(), "key1")

    def test_init_empty(self):
        pool = OllamaKeyPool([])
        self.assertFalse(pool.has_keys)
        self.assertEqual(pool.count, 0)
        self.assertIsNone(pool.get_current_key())
        self.assertIsNone(pool.rotate_key())

    def test_round_robin_rotation(self):
        pool = OllamaKeyPool(["k1", "k2", "k3"])
        self.assertEqual(pool.get_current_key(), "k1")
        self.assertEqual(pool.rotate_key(), "k2")
        self.assertEqual(pool.get_current_key(), "k2")
        self.assertEqual(pool.rotate_key(), "k3")
        self.assertEqual(pool.get_current_key(), "k3")
        self.assertEqual(pool.rotate_key(), "k1")
        self.assertEqual(pool.get_current_key(), "k1")

    @patch.dict(os.environ, {"OLLAMA_API_KEYS": "pool_a, pool_b,pool_c "})
    def test_init_from_env_var(self):
        pool = OllamaKeyPool()
        self.assertEqual(pool.count, 3)
        self.assertEqual(pool.get_current_key(), "pool_a")
        self.assertEqual(pool.rotate_key(), "pool_b")

    def test_get_headers_with_and_without_key(self):
        pool_with_keys = OllamaKeyPool(["secret_key_123"])
        headers = pool_with_keys.get_headers()
        self.assertEqual(headers["Authorization"], "Bearer secret_key_123")
        self.assertEqual(headers["Content-Type"], "application/json")

        pool_empty = OllamaKeyPool([])
        headers_empty = pool_empty.get_headers()
        self.assertNotIn("Authorization", headers_empty)
        self.assertEqual(headers_empty["Content-Type"], "application/json")


class TestOllamaClient(unittest.TestCase):
    def test_default_model_is_gemma4_31b(self):
        client = OllamaClient()
        self.assertEqual(client.model, "gemma4:31b")

    def test_custom_model_and_url(self):
        client = OllamaClient(base_url="http://custom-ollama:11434", model="gemma4:31b")
        self.assertEqual(client.base_url, "http://custom-ollama:11434")
        self.assertEqual(client.model, "gemma4:31b")

    @patch("httpx.Client.post")
    def test_generate_successful(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "ACGT"}
        mock_post.return_value = mock_resp

        pool = OllamaKeyPool(["key1"])
        client = OllamaClient(key_pool=pool, model="gemma4:31b")
        result = client.generate("test prompt")

        self.assertEqual(result, "ACGT")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer key1")
        self.assertEqual(call_kwargs["json"]["model"], "gemma4:31b")

    @patch("httpx.Client.post")
    def test_generate_failover_on_429_rate_limit(self, mock_post):
        # First key hits 429, second key returns 200
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.text = "Rate limit reached"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {"response": "SUCCESS_AFTER_RETRY"}

        mock_post.side_effect = [resp_429, resp_200]

        pool = OllamaKeyPool(["key_exhausted", "key_fresh"])
        client = OllamaClient(key_pool=pool, model="gemma4:31b")

        result = client.generate("test prompt")
        self.assertEqual(result, "SUCCESS_AFTER_RETRY")
        self.assertEqual(mock_post.call_count, 2)
        # Final key in use should have rotated
        self.assertEqual(pool.get_current_key(), "key_fresh")

    @patch("httpx.Client.post")
    def test_generate_all_keys_exhausted_returns_none(self, mock_post):
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.text = "Rate limit reached"
        mock_post.return_value = resp_429

        pool = OllamaKeyPool(["k1", "k2"])
        client = OllamaClient(key_pool=pool, model="gemma4:31b")

        result = client.generate("test prompt")
        self.assertIsNone(result)
        self.assertEqual(mock_post.call_count, 2)

    @patch("httpx.Client.post")
    def test_generate_network_error_graceful_handling(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        pool = OllamaKeyPool(["k1", "k2"])
        client = OllamaClient(key_pool=pool, model="gemma4:31b")

        result = client.generate("test prompt")
        self.assertIsNone(result)


class TestScoutAndCriticWithGemma4(unittest.TestCase):
    def test_scout_defaults_to_gemma4_31b(self):
        scout = ScoutAgent()
        self.assertEqual(scout.client.model, "gemma4:31b")

    def test_critic_defaults_to_gemma4_31b(self):
        critic = ContextCritic()
        self.assertEqual(critic.client.model, "gemma4:31b")

    def test_critic_deterministic_fallback_when_ollama_fails(self):
        critic = ContextCritic()
        # Even with no Ollama server running, deterministic evaluation succeeds
        doc = "Observed sequence: ACGTACGT reference: TGCATGCA"
        ok, reason = critic.evaluate_with_llm(doc, 19, 27, "observed_sequence")
        self.assertTrue(ok)
        self.assertIn("positive field marker", reason.lower())

    def test_scout_deterministic_fallback_when_ollama_fails(self):
        scout = ScoutAgent()
        # Even with no Ollama server running, deterministic regex succeeds
        doc = "Observed sequence: ACGTACGTACGT"
        proposal = scout.propose_with_llm(doc, "observed_sequence")
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.candidate_quote, "ACGTACGTACGT")
