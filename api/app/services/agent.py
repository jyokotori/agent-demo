"""LangGraph-powered reservation agent service."""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Annotated, AsyncIterator, Iterable, Optional, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.core.config import get_settings
from app.services.scheduler import MockScheduler, scheduler_service

SESSION_ID: ContextVar[str] = ContextVar("session_id")
LOGGER = logging.getLogger(__name__)


def keep_latest(previous: Optional[str], new_value: Optional[str]) -> Optional[str]:
    return new_value or previous


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: Annotated[Optional[str], keep_latest]


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Iterable):
        parts: list[str] = []
        for item in content:  # type: ignore[assignment]
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return ""


def _parse_datetime(value: str) -> datetime:
    """Normalize datetime strings for scheduler consumption."""
    if not value:
        raise ValueError("start_time is required")

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:  # noqa: PERF203
        raise ValueError("start_time must be ISO 8601 formatted") from exc

    if parsed.tzinfo is None:
        local_tz = datetime.now().astimezone().tzinfo
        if local_tz is None:
            raise ValueError("Unable to determine local timezone")
        parsed = parsed.replace(tzinfo=local_tz)
    return parsed.astimezone(UTC)


@tool("check_device_availability")
def check_device_availability(start_time: str) -> dict[str, object]:
    """Check if a device is available at the requested ISO 8601 start_time."""

    scheduler: MockScheduler = scheduler_service
    parsed = _parse_datetime(start_time)
    return scheduler.check_availability(start_time=parsed)


@tool("update_reservation_status")
def update_reservation_status(
    action: str,
    start_time: Optional[str] = None,
    reservation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, object]:
    """Confirm or cancel a reservation. action must be either 'confirm' or 'cancel'."""

    scheduler: MockScheduler = scheduler_service
    if action not in {"confirm", "cancel"}:
        raise ValueError("action must be either 'confirm' or 'cancel'")

    active_session = session_id or SESSION_ID.get()
    if action == "confirm":
        if not start_time:
            raise ValueError("start_time is required to confirm a reservation")
        parsed = _parse_datetime(start_time)
        return scheduler.book_reservation(
            session_id=active_session, start_time=parsed
        )
    if not reservation_id:
        raise ValueError("reservation_id is required to cancel a reservation")
    return scheduler.cancel_reservation(
        reservation_id=reservation_id, session_id=active_session
    )


class ReservationAgent:
    """Wrapper around a LangGraph agent that manages conversational state."""

    def __init__(self, scheduler: MockScheduler) -> None:
        self._settings = get_settings()
        self._scheduler = scheduler
        self._memory = MemorySaver()
        self._tools = [
            check_device_availability,
            update_reservation_status,
        ]
        self._tool_node = ToolNode(self._tools)
        self._model = ChatOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            model=self._settings.openai_model,
            temperature=0.4,
            streaming=True,
        ).bind_tools(self._tools)
        self._system_prompt = SystemMessage(
            content=(
                "You are an efficient reservation assistant for lab equipment. "
                "Always call `check_device_availability` to verify a slot before claiming it is free. "
                "Only call `update_reservation_status` with action='confirm' when the user explicitly asks you to book a time, and include the exact start time in ISO 8601 format. "
                "If the user only wants to know availability, only report the tool results—do not attempt to book anything. "
                "Use action='cancel' on `update_reservation_status` only when the user wants to cancel an existing reservation. "
                "Treat times without timezone as the user's local time and never hallucinate availability beyond tool outputs."
            )
        )
        self._initialized_sessions: set[str] = set()
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)

        def call_model(state: AgentState) -> AgentState:
            response = self._model.invoke(state["messages"])
            return {"messages": [response]}

        def call_tools(state: AgentState) -> AgentState:
            last_message = state["messages"][-1]
            if not isinstance(last_message, AIMessage):
                return {}
            result = self._tool_node.invoke(state)
            if isinstance(result, dict):
                return {"messages": result.get("messages", [])}
            if isinstance(result, list):
                return {"messages": result}
            return {}

        def should_continue(state: AgentState):
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                return "tools"
            return END

        graph.add_node("agent", call_model)
        graph.add_node("tools", call_tools)
        graph.set_entry_point("agent")
        graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        return graph.compile(checkpointer=self._memory)

    async def stream_conversation(
        self, *, session_id: str, user_message: str
    ) -> AsyncIterator[dict[str, object]]:
        """Stream agent tokens and tool results for a user turn."""

        graph_config = {"configurable": {"thread_id": session_id}}
        payload_messages: list[BaseMessage] = []
        if session_id not in self._initialized_sessions:
            payload_messages.append(self._system_prompt)
            self._initialized_sessions.add(session_id)

        payload_messages.append(HumanMessage(content=user_message))
        state_input: AgentState = {
            "messages": payload_messages,
            "session_id": session_id,
        }

        LOGGER.debug(
            "stream start",
            extra={
                "event": "agent.stream",
                "session_id": session_id,
                "message": user_message,
            },
        )
        token = SESSION_ID.set(session_id)
        try:
            async for event in self._graph.astream_events(
                state_input, config=graph_config, version="v2"
            ):
                async for payload in self._translate_event(event):
                    if payload:
                        LOGGER.debug(
                            "stream event",
                            extra={
                                "event": "agent.stream.event",
                                "session_id": session_id,
                                "payload_type": payload.get("type"),
                            },
                        )
                    yield payload
        finally:
            SESSION_ID.reset(token)
            LOGGER.debug(
                "stream end",
                extra={"event": "agent.stream", "session_id": session_id},
            )

    async def _translate_event(self, event: dict[str, object]) -> AsyncIterator[dict[str, object]]:
        event_type = event.get("event")
        name = event.get("name")

        if event_type == "on_chat_model_stream":
            data = event.get("data", {})
            chunk = data.get("chunk") if isinstance(data, dict) else None
            text = _extract_text(getattr(chunk, "content", "") if chunk else "")
            if text:
                yield {"type": "token", "content": text}
            return

        if event_type == "on_chat_model_end":
            data = event.get("data", {})
            output = data.get("output") if isinstance(data, dict) else None
            if output:
                text = _extract_text(getattr(output, "content", ""))
                if text:
                    yield {"type": "message", "content": text}
            return

        if event_type == "on_tool_end" and name:
            data = event.get("data", {})
            output = data.get("output") if isinstance(data, dict) else None
            if output:
                if isinstance(output, ToolMessage):
                    payload = output.content
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except json.JSONDecodeError:
                            pass
                    output_data = payload
                else:
                    output_data = output
                yield {
                    "type": "tool",
                    "tool_name": name,
                    "output": output_data,
                }
            return

        if event_type == "on_graph_end":
            yield {"type": "done"}
            return
        return

    async def apply_action(
        self,
        *,
        session_id: str,
        action: str,
        reservation_id: Optional[str] = None,
        start_time: Optional[str] = None,
    ) -> dict[str, object]:
        """Invoke the confirmation/cancellation tool and return the agent reply."""

        graph_config = {"configurable": {"thread_id": session_id}}
        LOGGER.debug(
            "apply action",
            extra={
                "event": "agent.action",
                "session_id": session_id,
                "action": action,
                "reservation_id": reservation_id,
                "start_time": start_time,
            },
        )
        token = SESSION_ID.set(session_id)
        try:
            if action == "confirm":
                if not start_time:
                    raise ValueError("start_time is required to confirm a reservation")
                parsed = _parse_datetime(start_time)
                scheduler_result = self._scheduler.book_reservation(
                    session_id=session_id, start_time=parsed
                )
                user_instruction = (
                    "用户已点击确认预约按钮，请向用户确认预约结果并提供下一步建议。"
                )
            else:
                if not reservation_id:
                    raise ValueError("reservation_id is required to cancel a reservation")
                scheduler_result = self._scheduler.cancel_reservation(
                    reservation_id=reservation_id, session_id=session_id
                )
                user_instruction = (
                    "用户已取消此次预约，请向用户确认取消结果并询问是否需要新预约。"
                )

            messages: list[BaseMessage] = []
            if session_id not in self._initialized_sessions:
                messages.append(self._system_prompt)
                self._initialized_sessions.add(session_id)

            messages.extend(
                [
                    HumanMessage(
                        content=json.dumps(
                            {
                                "action": action,
                                "start_time": start_time,
                                "reservation_id": reservation_id,
                                "result": scheduler_result,
                            }
                        )
                    ),
                    HumanMessage(content=user_instruction),
                ]
            )

            response_state = await self._graph.ainvoke(
                {"messages": messages, "session_id": session_id},
                config=graph_config,
            )
            final_message: Optional[BaseMessage] = None
            for message in reversed(response_state["messages"]):
                if isinstance(message, AIMessage):
                    final_message = message
                    break
            text = _extract_text(final_message.content) if final_message else ""
            LOGGER.debug(
                "apply action completed",
                extra={
                    "event": "agent.action",
                    "session_id": session_id,
                    "action": action,
                    "result_success": scheduler_result.get("success"),
                },
            )
            return {"scheduler": scheduler_result, "assistant_message": text}
        finally:
            SESSION_ID.reset(token)


agent_service = ReservationAgent(scheduler_service)
