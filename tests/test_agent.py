"""Tests for agent.py — AIAgent protocol conversion and tool loops."""
import json
from unittest.mock import MagicMock, patch

import pytest

from agent import AIAgent
from deck import Deck
from registry import ToolRegistry


@pytest.fixture
def anthropic_config():
    return {
        "provider": "anthropic",
        "model": "claude-test",
        "api_key": "test-key",
        "max_iterations": 5,
        "system_prompt": "You are a test assistant.",
    }


@pytest.fixture
def openai_config():
    return {
        "provider": "openai",
        "model": "gpt-test",
        "api_key": "test-key",
        "max_iterations": 5,
        "system_prompt": "You are a test assistant.",
    }


class TestAgentInit:
    @patch("anthropic.Anthropic")
    def test_init_anthropic(self, mock_anthropic, anthropic_config):
        agent = AIAgent(anthropic_config)
        assert agent._protocol == "anthropic"
        mock_anthropic.assert_called_once_with(api_key="test-key", base_url=None)

    @patch("openai.OpenAI")
    def test_init_openai(self, mock_openai, openai_config):
        agent = AIAgent(openai_config)
        assert agent._protocol == "openai"
        mock_openai.assert_called_once_with(api_key="test-key", base_url=None)


class TestToolSchemaCache:
    @patch("anthropic.Anthropic")
    def test_build_tools_caching(self, mock_anthropic, anthropic_config):
        r = ToolRegistry()
        r.register("tool_a", "TA", {"properties": {}}, lambda **kw: "ok")
        agent = AIAgent(anthropic_config)
        t1 = agent._build_tools(["tool_a"])
        t2 = agent._build_tools(["tool_a"])
        assert t1 is t2  # same cached object


class TestMessageConversion:
    @patch("anthropic.Anthropic")
    def test_to_api_messages_anthropic_tool_result(self, mock_anthropic, anthropic_config):
        agent = AIAgent(anthropic_config)
        msgs = [{"role": "tool", "tool_call_id": "tc1", "content": "ok"}]
        api = agent._to_api_messages(msgs)
        assert api[0]["role"] == "user"
        assert api[0]["content"][0]["type"] == "tool_result"

    @patch("openai.OpenAI")
    def test_to_api_messages_openai_tool_result(self, mock_openai, openai_config):
        agent = AIAgent(openai_config)
        msgs = [{"role": "tool", "tool_call_id": "tc1", "content": "ok"}]
        api = agent._to_api_messages(msgs)
        assert api[0]["role"] == "tool"
        assert api[0]["tool_call_id"] == "tc1"

    @patch("anthropic.Anthropic")
    def test_to_api_messages_anthropic_assistant_with_tool_calls(self, mock_anthropic, anthropic_config):
        agent = AIAgent(anthropic_config)
        msgs = [{"role": "assistant", "content": "thinking", "tool_calls": [{"id": "tc1", "name": "t", "arguments": {"x": 1}}]}]
        api = agent._to_api_messages(msgs)
        assert api[0]["role"] == "assistant"
        assert api[0]["content"][1]["type"] == "tool_use"


class TestExtractors:
    @patch("anthropic.Anthropic")
    def test_extract_text_anthropic(self, mock_anthropic, anthropic_config):
        agent = AIAgent(anthropic_config)
        msg = MagicMock()
        block = MagicMock()
        block.text = "hello"
        msg.content = [block]
        assert agent._extract_text(msg) == "hello"

    @patch("openai.OpenAI")
    def test_extract_text_openai(self, mock_openai, openai_config):
        agent = AIAgent(openai_config)
        msg = MagicMock()
        msg.content = "hello"
        assert agent._extract_text(msg) == "hello"

    @patch("anthropic.Anthropic")
    def test_extract_tool_calls_anthropic(self, mock_anthropic, anthropic_config):
        agent = AIAgent(anthropic_config)
        msg = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.id = "tc1"
        block.name = "tool_a"
        block.input = {"x": 1}
        msg.content = [block]
        calls = agent._extract_tool_calls(msg)
        assert len(calls) == 1
        assert calls[0]["name"] == "tool_a"
        assert calls[0]["arguments"] == {"x": 1}

    @patch("openai.OpenAI")
    def test_extract_tool_calls_openai(self, mock_openai, openai_config):
        agent = AIAgent(openai_config)
        msg = MagicMock()
        tc = MagicMock()
        tc.id = "tc1"
        tc.function.name = "tool_a"
        tc.function.arguments = '{"x": 1}'
        msg.tool_calls = [tc]
        calls = agent._extract_tool_calls(msg)
        assert calls[0]["arguments"] == {"x": 1}


class TestRunLoop:
    @patch("anthropic.Anthropic")
    def test_run_without_tool_calls(self, mock_anthropic_cls, anthropic_config):
        agent = AIAgent(anthropic_config)
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        agent.client = mock_client

        mock_msg = MagicMock()
        mock_msg.content = []
        mock_client.messages.create.return_value = mock_msg

        result = agent.run([{"role": "user", "content": "hi"}])
        assert result == ""

    @patch("anthropic.Anthropic")
    def test_run_reaches_max_iterations(self, mock_anthropic_cls, anthropic_config):
        agent = AIAgent(anthropic_config)
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        agent.client = mock_client

        # Always return a tool call
        mock_msg = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.id = "tc1"
        block.name = "nonexistent"
        block.input = {}
        block.text = ""  # prevent _extract_text from collecting MagicMock
        mock_msg.content = [block]
        mock_client.messages.create.return_value = mock_msg

        result = agent.run([{"role": "user", "content": "loop"}])
        assert result == "(reached max iterations)"

    @patch("anthropic.Anthropic")
    def test_run_with_deck(self, mock_anthropic_cls, anthropic_config):
        r = ToolRegistry()
        r.register("echo", "Echo", {"properties": {"msg": {"type": "string"}}}, lambda msg: msg)
        agent = AIAgent(anthropic_config)
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        agent.client = mock_client

        # First response has tool call, second response has text
        msg1 = MagicMock()
        b1 = MagicMock()
        b1.type = "tool_use"
        b1.id = "tc1"
        b1.name = "echo"
        b1.input = {"msg": "hello"}
        b1.text = ""  # prevent _extract_text from collecting MagicMock
        msg1.content = [b1]

        msg2 = MagicMock()
        msg2.content = []

        mock_client.messages.create.side_effect = [msg1, msg2]

        deck = Deck(["echo"], r)
        result = agent.run([{"role": "user", "content": "test"}], deck=deck)
        assert result == ""
        # Verify the API was called with tools parameter
        first_call_kwargs = mock_client.messages.create.call_args_list[0].kwargs
        assert "tools" in first_call_kwargs
