from __future__ import annotations
import json
import logging
from typing import Any

import httpx

from ..manifest.schema import McpSpec

logger = logging.getLogger(__name__)


class MCPExecutor:
    """
    Executes MCP (Model Context Protocol) tool calls.
    Bridges between the LLM tool-use loop and external MCP servers.
    """

    def __init__(self, llm_client=None):
        self._llm = llm_client
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def execute_with_tools(
        self,
        model: str,
        messages: list[dict],
        mcps: list[McpSpec],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[dict, int]:
        """
        Agentic loop: LLM → tool call → result → LLM until done.
        Returns (final_output_dict, total_tokens).
        """
        tools = await self._build_tool_schemas(mcps)
        current_messages = list(messages)
        total_tokens = 0
        max_tool_rounds = 10

        for _ in range(max_tool_rounds):
            resp = await self._llm.chat(
                model=model,
                messages=current_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )
            total_tokens += resp.get("eval_count", 0)
            msg = resp.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                # Final answer
                content = msg.get("content", "")
                return _parse_content(content), total_tokens

            # Execute tool calls
            current_messages.append({"role": "assistant", "content": msg})
            for tc in tool_calls:
                result = await self._dispatch_tool(tc, mcps)
                current_messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tc.get("id", ""),
                })

        # Fallback if max rounds reached
        return {"_max_tool_rounds": True}, total_tokens

    async def execute(self, action: str, snapshot: dict | None) -> None:
        """Execute a compensating action (SAGA callback)."""
        logger.info("Executing compensating action: %s", action)
        # In production this would dispatch to the appropriate MCP server
        # For now we log and succeed
        pass

    async def _build_tool_schemas(self, mcps: list[McpSpec]) -> list[dict]:
        tools = []
        for mcp in mcps:
            if mcp.transport == "stdio" or not mcp.url:
                continue
            try:
                r = await self._http.get(f"{mcp.url}/tools")
                if r.status_code == 200:
                    tools.extend(r.json().get("tools", []))
            except Exception as exc:
                logger.warning("Failed to fetch tools from MCP %s: %s", mcp.name, exc)
        return tools

    async def _dispatch_tool(self, tool_call: dict, mcps: list[McpSpec]) -> Any:
        func = tool_call.get("function", {})
        tool_name = func.get("name", "")
        args = func.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}

        # Find which MCP owns this tool
        for mcp in mcps:
            if not mcp.url:
                continue
            try:
                r = await self._http.post(
                    f"{mcp.url}/tools/{tool_name}",
                    json={"arguments": args},
                )
                if r.status_code == 200:
                    return r.json()
            except Exception as exc:
                logger.error("Tool call %s failed on MCP %s: %s", tool_name, mcp.name, exc)

        return {"error": f"Tool {tool_name!r} not found"}


def _parse_content(content: str) -> dict:
    try:
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return json.loads(content[start:end].strip())
        return json.loads(content.strip())
    except (ValueError, KeyError):
        return {"raw_output": content}
