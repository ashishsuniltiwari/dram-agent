# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0

"""
DRAM Tool Wiring — Phase 3.

Provides McpToolset factory for connecting ADK agents to the DRAM MCP
server via the Stdio transport. Agents import `get_dram_toolset()` and
pass the result to their `tools` list.

Usage inside an agent module:
    from tools.dram_toolset import get_dram_toolset
    ...
    agent = Agent(
        ...,
        tools=[get_dram_toolset()],
    )

The MCP server process is spawned lazily when the first agent tool call
is made and cleaned up automatically by the ADK session lifecycle.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

# Path to the DRAM MCP server entry-point script
_SERVER_SCRIPT = str(Path(__file__).parent.parent / "mcp_server" / "dram_server.py")

# Python executable inside the project's virtual environment
_PYTHON_EXE = sys.executable


def get_dram_toolset(tool_filter: list[str] | None = None) -> McpToolset:
    """Return a McpToolset connected to the DRAM MCP server via Stdio.

    Args:
        tool_filter: Optional list of tool names to expose. If None, all
            five DRAM tools are exposed.

    Returns:
        An McpToolset instance ready to be added to an agent's tools list.
    """
    return McpToolset(
        connection_params=StdioServerParameters(
            command=_PYTHON_EXE,
            args=[_SERVER_SCRIPT, "--transport", "stdio"],
        ),
        tool_filter=tool_filter,
    )
