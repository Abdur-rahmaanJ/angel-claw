import logging
import os
import json
from typing import List, Dict, Any, Optional

import litellm


logger = logging.getLogger("angel-claw-engine-executor")

from .config import MAX_TURNS, MAX_TOOLS_PER_TURN, MAX_RECURSION_DEPTH


class LlmExecutor:
    """Handles LLM execution, caching, and tool calling."""

    def __init__(self, settings, cache=None):
        self._settings = settings
        self._cache = cache

    async def execute_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        all_tools: Optional[List],
        api_key: Optional[str],
        api_base: Optional[str],
        runtime,
        session_id: str,
        user_id: str,
        credit_service,
    ) -> tuple[str, List[Dict], int]:
        """
        Execute LLM with tool calls.

        Returns:
            tuple: (assistant_content, tool_calls_list, total_tokens)
        """
        turns = 0
        tool_calls_list = []
        assistant_content = ""
        total_tokens = 0

        while turns < MAX_TURNS:
            turns += 1

            cache_key = None
            response = None

            if self._cache:
                cache_key = json.dumps(
                    {
                        "model": model,
                        "messages": messages,
                        "tools": all_tools,
                        "api_base": api_base,
                    },
                    sort_keys=True,
                )
                cached_res = await self._cache.get(cache_key)
                if cached_res:
                    logger.info(f"Using cached LLM response for user {user_id}")
                    response = self._reconstruct_response(cached_res)

            if not response:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    api_base=api_base,
                    tools=all_tools if all_tools else None,
                    tool_choice="auto" if all_tools else None,
                )

                if self._cache and cache_key:
                    resp_message = response.choices[0].message
                    await self._cache.set(
                        cache_key,
                        self._serialize_response(resp_message),
                    )

            if hasattr(response, "usage") and response.usage:
                total_tokens += getattr(response.usage, "total_tokens", 0)

            response_message = response.choices[0].message
            msg_dict = {"role": "assistant", "content": response_message.content}

            self._log_response(response_message)

            if response_message.tool_calls:
                if len(response_message.tool_calls) > MAX_TOOLS_PER_TURN:
                    logger.warning(
                        f"Tool spam detected: {len(response_message.tool_calls)} calls in one turn. Truncating."
                    )
                    response_message.tool_calls = response_message.tool_calls[
                        :MAX_TOOLS_PER_TURN
                    ]

                msg_dict["tool_calls"] = self._serialize_tool_calls(
                    response_message.tool_calls
                )
                tool_calls_list.extend(msg_dict["tool_calls"])

            messages.append(msg_dict)
            assistant_content += response_message.content or ""

            if not response_message.tool_calls:
                break

            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name

                try:
                    function_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    function_args = {}

                allowed, err_msg = await credit_service.check_credits(
                    user_id, "tool_execution"
                )
                if not allowed:
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": err_msg,
                        }
                    )
                    continue

                logger.warning(
                    f"CALLING runtime.call_tool(function_name={function_name}, function_args={function_args}, session_id={session_id})"
                )
                function_result = await runtime.call_tool(
                    function_name, function_args, session_id
                )
                logger.warning(f"call_tool returned: {function_result}")
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": str(function_result),
                    }
                )

                credit_service.deduct_credits(
                    user_id, "tool_execution", {"tool": function_name}
                )

            if not assistant_content.strip() and turns < MAX_TURNS:
                messages.append(
                    {
                        "role": "user",
                        "content": "Please provide a final, natural language response based on the tool results above.",
                    }
                )

        if turns >= MAX_TURNS:
            logger.warning(f"Turn limit reached ({MAX_TURNS}) for user {user_id}")
            assistant_content += "\n\n[SYSTEM: Maximum reasoning turns reached. I've stopped to prevent excessive resource usage.]"

        if not assistant_content.strip() and tool_calls_list:
            assistant_content = (
                "✅ I've processed your request using my available tools."
            )

        return assistant_content, tool_calls_list, total_tokens

    async def execute_streaming(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        all_tools: Optional[List],
        api_key: Optional[str],
        api_base: Optional[str],
        runtime,
        session_id: str,
        user_id: str,
        credit_service,
    ):
        """Execute LLM with streaming."""
        turns = 0
        tool_calls_list = []
        assistant_content = ""
        total_tokens = 0

        messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        while turns < MAX_TURNS:
            turns += 1

            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    api_key=api_key,
                    api_base=api_base,
                    tools=all_tools if all_tools else None,
                    tool_choice="auto" if all_tools else None,
                    stream=True,
                    stream_options={"include_usage": True},
                )

                async for chunk in response:
                    if hasattr(chunk, "usage") and chunk.usage:
                        total_tokens += getattr(chunk.usage, "total_tokens", 0)

                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta
                    if delta.content:
                        assistant_content += delta.content
                        for char in delta.content:
                            yield char

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = getattr(tc, "index", 0)

                            existing = next(
                                (t for t in tool_calls_list if t.get("index") == idx),
                                None,
                            )

                            if existing:
                                if tc.id:
                                    existing["id"] = tc.id
                                if tc.function:
                                    if tc.function.name:
                                        existing["function"]["name"] = tc.function.name
                                        yield f"[TOOL_CALL:{tc.function.name}]"
                                    if tc.function.arguments:
                                        existing["function"]["arguments"] += (
                                            tc.function.arguments
                                        )
                            else:
                                new_tc = {
                                    "index": idx,
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name
                                        if tc.function
                                        else None,
                                        "arguments": tc.function.arguments
                                        if tc.function and tc.function.arguments
                                        else "",
                                    },
                                }
                                tool_calls_list.append(new_tc)
                                if tc.function and tc.function.name:
                                    yield f"[TOOL_CALL:{tc.function.name}]"

                if tool_calls_list:
                    new_tool_calls = [
                        tc
                        for tc in tool_calls_list
                        if not any(m.get("tool_call_id") == tc["id"] for m in messages)
                    ]

                    if new_tool_calls:
                        messages.append(
                            {
                                "role": "assistant",
                                "content": assistant_content or None,
                                "tool_calls": new_tool_calls,
                            }
                        )

                        for tc in new_tool_calls:
                            function_name = tc["function"]["name"]
                            try:
                                function_args = json.loads(tc["function"]["arguments"])
                            except json.JSONDecodeError:
                                function_args = {}

                            allowed, err_msg = await credit_service.check_credits(
                                user_id, "tool_execution"
                            )
                            if not allowed:
                                messages.append(
                                    {
                                        "tool_call_id": tc["id"],
                                        "role": "tool",
                                        "name": function_name,
                                        "content": err_msg,
                                    }
                                )
                                continue

                            function_result = await runtime.call_tool(
                                function_name, function_args, session_id
                            )
                            messages.append(
                                {
                                    "tool_call_id": tc["id"],
                                    "role": "tool",
                                    "name": function_name,
                                    "content": str(function_result),
                                }
                            )

                            credit_service.deduct_credits(
                                user_id, "tool_execution", {"tool": function_name}
                            )

                        if not assistant_content.strip() and turns < MAX_TURNS:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": "Please provide a final, natural language response based on the tool results above.",
                                }
                            )

                        continue

                break

            except Exception as e:
                logger.error(f"Error in execute_streaming turn {turns}: {e}")
                yield f"\n\n[Error: {str(e)}]"
                break

        if not assistant_content.strip() and tool_calls_list:
            assistant_content = (
                "✅ I've processed your request using my available tools."
            )
            for char in assistant_content:
                yield char

    def _reconstruct_response(self, data: dict):
        """Reconstruct a pseudo-response object from cached data."""

        class CachedResponse:
            def __init__(self, data):
                self.choices = [
                    type(
                        "Choice",
                        (),
                        {
                            "message": type(
                                "Msg",
                                (),
                                {
                                    "content": data["content"],
                                    "tool_calls": [
                                        type(
                                            "TC",
                                            (),
                                            {
                                                "id": tc["id"],
                                                "type": tc["type"],
                                                "function": type(
                                                    "Fn", (), tc["function"]
                                                )(),
                                            },
                                        )()
                                        for tc in data["tool_calls"]
                                    ]
                                    if data["tool_calls"]
                                    else None,
                                },
                            )()
                        },
                    )()
                ]

        return CachedResponse(data)

    def _serialize_response(self, resp_message) -> dict:
        """Serialize response message for caching."""
        return {
            "content": resp_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in resp_message.tool_calls
            ]
            if resp_message.tool_calls
            else None,
        }

    def _serialize_tool_calls(self, tool_calls) -> List[dict]:
        """Serialize tool calls."""
        return [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tool_calls
        ]

    def _log_response(self, response_message):
        """Log response for debugging."""
        debug_file = os.path.expanduser("~/.angelclaw/logs/tool_debug.txt")
        os.makedirs(os.path.dirname(debug_file), exist_ok=True)
        with open(debug_file, "a") as f:
            from datetime import datetime

            f.write(
                f"{datetime.now().isoformat()} - response_message type: {type(response_message)}\n"
            )
            f.write(
                f"{datetime.now().isoformat()} - response_message.content: {response_message.content}\n"
            )
            f.write(
                f"{datetime.now().isoformat()} - response_message.tool_calls: {response_message.tool_calls}\n"
            )
            if response_message.tool_calls:
                for tc in response_message.tool_calls:
                    f.write(f"{datetime.now().isoformat()} - tc type: {type(tc)}\n")
                    f.write(f"{datetime.now().isoformat()} - tc.id: {tc.id}\n")
                    f.write(
                        f"{datetime.now().isoformat()} - tc.function: {tc.function}\n"
                    )
                    f.write(
                        f"{datetime.now().isoformat()} - tc.function.name: {tc.function.name}\n"
                    )
                    f.write(
                        f"{datetime.now().isoformat()} - tc.function.arguments: {repr(tc.function.arguments)}\n"
                    )


def create_llm_executor(settings, cache=None) -> LlmExecutor:
    return LlmExecutor(settings, cache)
