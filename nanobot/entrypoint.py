#!/usr/bin/env python3
"""
Entrypoint for nanobot gateway in Docker.

Resolves environment variables into config.json at runtime, then launches nanobot gateway.
"""

import json
import os
import sys
from pathlib import Path


def main():
    config_path = Path("/app/nanobot/config.json")
    workspace_path = Path("/app/nanobot/workspace")
    
    # Load base config
    with open(config_path) as f:
        config = json.load(f)
    
    # Resolve LLM provider API key and base URL from env vars
    llm_api_key = os.environ.get("LLM_API_KEY")
    llm_base_url = os.environ.get("LLM_API_BASE_URL")
    llm_model = os.environ.get("LLM_API_MODEL")
    
    if llm_api_key:
        config["providers"]["custom"]["apiKey"] = llm_api_key
    if llm_base_url:
        config["providers"]["custom"]["apiBase"] = llm_base_url
    if llm_model:
        config["agents"]["defaults"]["model"] = llm_model
    
    # Resolve gateway host/port
    gateway_host = os.environ.get("NANOBOT_GATEWAY_CONTAINER_ADDRESS")
    gateway_port = os.environ.get("NANOBOT_GATEWAY_CONTAINER_PORT")
    
    if gateway_host:
        config.setdefault("gateway", {})["host"] = gateway_host
    if gateway_port:
        config.setdefault("gateway", {})["port"] = int(gateway_port)
    
    # Resolve webchat config
    webchat_host = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_ADDRESS")
    webchat_port = os.environ.get("NANOBOT_WEBCHAT_CONTAINER_PORT")
    access_key = os.environ.get("NANOBOT_ACCESS_KEY")
    
    if webchat_host:
        config.setdefault("channels", {}).setdefault("webchat", {})["host"] = webchat_host
    if webchat_port:
        config.setdefault("channels", {}).setdefault("webchat", {})["port"] = int(webchat_port)
    if access_key:
        config.setdefault("channels", {}).setdefault("webchat", {})["access_key"] = access_key
    
    # Resolve MCP server environment variables
    lms_backend_url = os.environ.get("NANOBOT_LMS_BACKEND_URL")
    lms_api_key = os.environ.get("NANOBOT_LMS_API_KEY")
    
    if lms_backend_url and "tools" in config and "mcpServers" in config["tools"]:
        mcp_config = config["tools"]["mcpServers"].get("lms", {})
        mcp_config["command"] = "python"
        mcp_config["args"] = ["-m", "mcp_lms", lms_backend_url]
        mcp_config.setdefault("env", {})["PYTHONPATH"] = "/app/mcp"
        if lms_api_key:
            mcp_config["env"]["NANOBOT_LMS_API_KEY"] = lms_api_key
    
    # Write resolved config
    resolved_path = Path("/app/nanobot/config.resolved.json")
    with open(resolved_path, "w") as f:
        json.dump(config, f, indent=2)
    
    # Launch nanobot gateway
    os.execvp("nanobot", ["nanobot", "gateway", "--config", str(resolved_path), "--workspace", str(workspace_path)])


if __name__ == "__main__":
    main()
