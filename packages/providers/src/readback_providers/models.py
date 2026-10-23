"""The chat model of each provider, and the call path every model request takes.

A request goes: digest, cassette lookup, then (only on a miss in record mode) the budget reservation
and the real call, recorded as a cassette. Nothing calls a provider except through call_model, so a
call that is not counted and not recorded cannot happen.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, message_to_dict, messages_from_dict
from pydantic import SecretStr
from readback_tracing import chat_span, record_usage

from readback_providers.cassettes import CassetteMiss, Store, mode, request_digest
from readback_providers.ledger import Ledger
from readback_providers.registry import Provider


def build_chat_model(p: Provider) -> BaseChatModel:
    """The LangChain integration for a provider. Imported lazily: CI never needs a provider package."""
    model = p.model_id()
    if p.name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model, google_api_key=os.environ[str(p.key_env)], temperature=0, max_retries=1
        )
    if p.name == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, api_key=os.environ[str(p.key_env)], temperature=0, max_retries=1)  # type: ignore[arg-type]
    if p.name in {"openrouter", "sambanova"}:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=SecretStr(os.environ[str(p.key_env)]),
            base_url=p.base_url,
            temperature=0,
            max_retries=1,
        )
    if p.name == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model, base_url=os.environ[str(p.key_env)], temperature=0)
    raise ValueError(f"{p.name} has no chat model")


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cassette_hits: int = 0


@dataclass
class ModelCaller:
    """Calls one provider's model for one turn, through the cassette and the budget."""

    provider: Provider
    ledger: Ledger
    store: Store
    prompt_hash: str
    trace_id: str
    factory: Callable[[Provider], BaseChatModel] = build_chat_model
    usage: Usage = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.usage = Usage()
        self._model: BaseChatModel | None = None

    async def __call__(self, messages: list[BaseMessage], tools: list[dict[str, Any]]) -> AIMessage:
        model_id = self.provider.model_id()
        digest = request_digest(self.provider.name, model_id, self.prompt_hash, messages, tools)
        with chat_span(self.provider.name, model_id) as span:
            span.set_attribute("readback.cassette.digest", digest)
            hit = self.store.get(self.provider.name, digest)
            if hit is not None:
                message = messages_from_dict([hit.response])[0]
                span.set_attribute("readback.cassette", "hit")
                self.usage.cassette_hits += 1
                reported = hit.model_reported
            else:
                if mode() != "record":
                    span.set_attribute("readback.cassette", "miss")
                    raise CassetteMiss(self.provider.name, digest)
                cap = int(self.provider.daily_budget or 0)
                self.ledger.reserve(self.provider.name, model_id, cap, digest, self.trace_id)
                if self._model is None:
                    self._model = self.factory(self.provider)
                bound = self._model.bind_tools(tools) if tools else self._model
                started = time.perf_counter()
                message = await bound.ainvoke(messages)
                span.set_attribute(
                    "readback.model.latency_ms", round((time.perf_counter() - started) * 1000, 1)
                )
                meta = getattr(message, "response_metadata", {}) or {}
                reported = meta.get("model_name") or meta.get("model") or model_id
                self.store.put(
                    self.provider.name, model_id, reported, self.prompt_hash, digest, message_to_dict(message)
                )
                span.set_attribute("readback.cassette", "recorded")
            usage = getattr(message, "usage_metadata", None) or {}
            tin, tout = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
            finish = [str((getattr(message, "response_metadata", {}) or {}).get("finish_reason", "stop"))]
            record_usage(span, reported, tin, tout, finish)
            self.usage.input_tokens += tin
            self.usage.output_tokens += tout
            self.usage.calls += 1
        assert isinstance(message, AIMessage)
        return message

    async def structured(self, messages: list[BaseMessage], schema: type[Any]) -> dict[str, Any] | None:
        """The structured answer: the provider's schema mode where the registry says it has one, the
        tool calling strategy where it does not. Through the same cassette and budget as any call."""
        model_id = self.provider.model_id()
        method = "json_schema" if self.provider.structured == "schema" else "function_calling"
        digest = request_digest(
            self.provider.name,
            model_id,
            self.prompt_hash,
            messages,
            [{"function": {"name": f"structured:{schema.__name__}:{method}"}}],
        )
        with chat_span(self.provider.name, model_id) as span:
            span.set_attribute("readback.cassette.digest", digest)
            span.set_attribute("readback.structured.method", method)
            hit = self.store.get(self.provider.name, digest)
            if hit is not None:
                response = hit.response
                reported = hit.model_reported
                span.set_attribute("readback.cassette", "hit")
                self.usage.cassette_hits += 1
            else:
                if mode() != "record":
                    span.set_attribute("readback.cassette", "miss")
                    raise CassetteMiss(self.provider.name, digest)
                self.ledger.reserve(
                    self.provider.name, model_id, int(self.provider.daily_budget or 0), digest, self.trace_id
                )
                if self._model is None:
                    self._model = self.factory(self.provider)
                runnable = self._model.with_structured_output(schema, method=method, include_raw=True)
                out = await runnable.ainvoke(messages)
                raw = out.get("raw") if isinstance(out, dict) else None
                parsed = out.get("parsed") if isinstance(out, dict) else out
                dump = getattr(parsed, "model_dump", None)
                if callable(dump):
                    parsed = dump()
                meta = getattr(raw, "response_metadata", {}) or {}
                reported = meta.get("model_name") or meta.get("model") or model_id
                response = {
                    "structured": parsed,
                    "raw": message_to_dict(raw) if raw is not None else None,
                    "parsing_error": str(out.get("parsing_error"))
                    if isinstance(out, dict) and out.get("parsing_error")
                    else None,
                }
                self.store.put(self.provider.name, model_id, reported, self.prompt_hash, digest, response)
                span.set_attribute("readback.cassette", "recorded")
            raw_message = messages_from_dict([response["raw"]])[0] if response.get("raw") else None
            usage = getattr(raw_message, "usage_metadata", None) or {}
            tin, tout = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
            record_usage(span, reported, tin, tout, ["stop"])
            self.usage.input_tokens += tin
            self.usage.output_tokens += tout
            self.usage.calls += 1
        structured = response.get("structured")
        return dict(structured) if isinstance(structured, dict) else None
