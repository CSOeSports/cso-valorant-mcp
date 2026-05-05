FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8001
ENV MCP_TRANSPORT=streamable-http

WORKDIR /app
COPY . /app/

RUN uv sync --frozen

EXPOSE 8001

CMD ["uv", "run", "valorant-mcp-http"]
