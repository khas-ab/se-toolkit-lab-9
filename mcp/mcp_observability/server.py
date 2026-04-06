"""Stdio MCP server exposing VictoriaLogs and VictoriaTraces as typed tools."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

# VictoriaLogs and VictoriaTraces base URLs
_logs_base_url: str = ""
_traces_base_url: str = ""

server = Server("observability")


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


class _NoArgs(BaseModel):
    """Empty input model for tools that only need server-side configuration."""


class _LogsSearchQuery(BaseModel):
    query: str = Field(
        default="error",
        description="LogsQL query string (e.g., 'error', 'level:error', '_stream:{service=\"backend\"}').",
    )
    limit: int = Field(default=10, ge=1, le=1000, description="Max logs to return (default 10).")


class _LogsErrorCountQuery(BaseModel):
    service: str = Field(
        default="",
        description="Filter by service name (optional, leave empty for all services).",
    )
    minutes: int = Field(
        default=60, ge=1, le=1440, description="Time window in minutes (default 60)."
    )


class _TracesListQuery(BaseModel):
    service: str = Field(
        default="Learning Management Service",
        description="Service name to filter traces (default: 'Learning Management Service').",
    )
    limit: int = Field(default=5, ge=1, le=50, description="Max traces to return (default 5).")


class _TracesGetQuery(BaseModel):
    trace_id: str = Field(description="Trace ID to fetch (hex string, e.g., 'cc075d97d3f08f0cb612081aa5c6a61b').")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _text(data: Any) -> list[TextContent]:
    """Serialize data to a JSON text block."""
    if isinstance(data, BaseModel):
        payload = data.model_dump()
    elif isinstance(data, list):
        payload = [item.model_dump() if isinstance(item, BaseModel) else item for item in data]
    else:
        payload = data
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


async def _http_get(url: str, params: dict[str, Any] | None = None) -> Any:
    """Make an async HTTP GET request."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Tool handlers - VictoriaLogs
# ---------------------------------------------------------------------------


async def _logs_search(args: _LogsSearchQuery) -> list[TextContent]:
    """Search logs using VictoriaLogs LogsQL query."""
    if not _logs_base_url:
        return _text({"error": "VictoriaLogs URL not configured"})
    
    url = f"{_logs_base_url}/select/logsql/query"
    params = {"query": args.query, "limit": args.limit}
    
    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": str(e), "query": args.query})


async def _logs_error_count(args: _LogsErrorCountQuery) -> list[TextContent]:
    """Count errors per service over a time window."""
    if not _logs_base_url:
        return _text({"error": "VictoriaLogs URL not configured"})
    
    # Build LogsQL query for errors
    if args.service:
        query = f'_stream:{{service="{args.service}"}} AND (level:error OR SeverityText:ERROR)'
    else:
        query = "level:error OR SeverityText:ERROR"
    
    url = f"{_logs_base_url}/select/logsql/stats_query"
    params = {
        "query": f"{query} | stats count() by (service)",
    }
    
    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": str(e)})


# ---------------------------------------------------------------------------
# Tool handlers - VictoriaTraces
# ---------------------------------------------------------------------------


async def _traces_list(args: _TracesListQuery) -> list[TextContent]:
    """List recent traces for a service."""
    if not _traces_base_url:
        return _text({"error": "VictoriaTraces URL not configured"})

    # VictoriaTraces Jaeger-compatible API (under /select/jaeger path)
    url = f"{_traces_base_url}/select/jaeger/api/traces"
    params = {"service": args.service, "limit": args.limit}

    try:
        result = await _http_get(url, params)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": str(e), "service": args.service})


async def _traces_get(args: _TracesGetQuery) -> list[TextContent]:
    """Fetch a specific trace by ID."""
    if not _traces_base_url:
        return _text({"error": "VictoriaTraces URL not configured"})

    url = f"{_traces_base_url}/select/jaeger/api/traces/{args.trace_id}"

    try:
        result = await _http_get(url)
        return _text(result)
    except httpx.HTTPError as e:
        return _text({"error": str(e), "trace_id": args.trace_id})


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def _register(
    name: str,
    description: str,
    input_model: type[BaseModel],
    handler: Callable,
) -> None:
    """Register a tool with the MCP server."""
    schema = input_model.model_json_schema()
    _TOOLS[name] = (input_model, handler, Tool(name=name, description=description, inputSchema=schema))


_TOOLS: dict[str, tuple[type[BaseModel], Callable, Tool]] = {}

_register(
    "logs_search",
    "Search logs using VictoriaLogs LogsQL query. Use 'error' for all errors, or filter by service: '_stream:{service=\"backend\"} AND level:error'.",
    _LogsSearchQuery,
    _logs_search,
)
_register(
    "logs_error_count",
    "Count errors per service over a time window. Returns aggregated error counts grouped by service.",
    _LogsErrorCountQuery,
    _logs_error_count,
)
_register(
    "traces_list",
    "List recent traces for a service. Returns trace metadata including trace ID, duration, and span count.",
    _TracesListQuery,
    _traces_list,
)
_register(
    "traces_get",
    "Fetch a specific trace by ID. Returns full trace with all spans and their hierarchy.",
    _TracesGetQuery,
    _traces_get,
)


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [entry[2] for entry in _TOOLS.values()]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    entry = _TOOLS.get(name)
    if entry is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    model_cls, handler, _ = entry
    try:
        args = model_cls.model_validate(arguments or {})
        return await handler(args)
    except Exception as exc:
        return [TextContent(type="text", text=f"Error: {type(exc).__name__}: {exc}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Run the MCP server."""
    global _logs_base_url, _traces_base_url
    
    _logs_base_url = os.environ.get("VICTORIALOGS_BASE_URL", "http://victorialogs:9428").rstrip("/")
    _traces_base_url = os.environ.get("VICTORIATRACES_BASE_URL", "http://victoriatraces:10428").rstrip("/")
    
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
