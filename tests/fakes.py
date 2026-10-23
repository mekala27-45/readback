"""A scripted chat model: the stand in for a provider in tests, through the real cassette path."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field


class Scripted(BaseChatModel):
    turns: list[AIMessage] = Field(default_factory=list)
    answers: list[Any] = Field(default_factory=list)
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.seen.append(list(messages))
        message = self.turns.pop(0) if self.turns else AIMessage(content="done")
        message.usage_metadata = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        message.response_metadata = {"model_name": "scripted-1", "finish_reason": "stop"}
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, None, **kwargs)

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Scripted:  # type: ignore[override]
        return self

    def with_structured_output(self, schema: Any, *, include_raw: bool = False, **kwargs: Any) -> Any:  # type: ignore[override]
        def run(messages: list[BaseMessage]) -> dict[str, Any]:
            self.seen.append(list(messages))
            parsed = self.answers.pop(0) if self.answers else None
            raw = AIMessage(
                content="",
                usage_metadata={"input_tokens": 50, "output_tokens": 30, "total_tokens": 80},
                response_metadata={"model_name": "scripted-1"},
            )
            return {"raw": raw, "parsed": parsed, "parsing_error": None}

        return RunnableLambda(run)


def call(name: str, args: dict[str, Any], i: int) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"c{i}", "type": "tool_call"}]
    )
