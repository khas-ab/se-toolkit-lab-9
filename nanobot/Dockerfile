# Multi-stage build for nanobot gateway with uv

# ---
# Stage 1: Build the application
# ---

ARG REGISTRY_PREFIX_DOCKER_HUB
FROM ${REGISTRY_PREFIX_DOCKER_HUB}astral/uv:python3.14-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Disable Python downloads - use system interpreter
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Copy project files from workspace context
COPY --from=workspace pyproject.toml uv.lock /app/

# Copy nanobot, mcp, and nanobot-websocket-channel projects from workspace context
COPY --from=workspace nanobot/pyproject.toml /app/nanobot/pyproject.toml
COPY --from=workspace mcp/pyproject.toml /app/mcp/pyproject.toml
COPY --from=workspace nanobot-websocket-channel/pyproject.toml /app/nanobot-websocket-channel/pyproject.toml

# Sync nanobot dependencies (including lms-mcp and nanobot-webchat from workspace)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package nanobot --package lms-mcp --package nanobot-webchat

# Copy the nanobot, mcp, and nanobot-websocket-channel source from workspace context
COPY --from=workspace nanobot /app/nanobot
COPY --from=workspace mcp /app/mcp
COPY --from=workspace nanobot-websocket-channel /app/nanobot-websocket-channel

# ---
# Stage 2: Final runtime image
# ---

ARG REGISTRY_PREFIX_DOCKER_HUB
FROM ${REGISTRY_PREFIX_DOCKER_HUB}python:3.14.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8

# Create non-root user
RUN groupadd --system --gid 999 nonroot \
    && useradd --system --gid 999 --uid 999 --create-home nonroot

# Copy application from builder
COPY --from=builder --chown=nonroot:nonroot /app /app

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/nanobot:/app/mcp:/app/nanobot-websocket-channel"

USER nonroot
WORKDIR /app

# Run the entrypoint
CMD ["python", "/app/nanobot/entrypoint.py"]
