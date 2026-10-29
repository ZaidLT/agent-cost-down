FROM python:3.13-slim
RUN pip install --no-cache-dir uv==0.11.6
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev
COPY fixtures-v3 ./fixtures-v3
COPY schemas ./schemas
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 ACD_LIVE_ENABLED=false
RUN useradd --create-home --uid 10001 acd
RUN mkdir -p /app/artifacts /app/private && chown -R acd:acd /app/artifacts /app/private
USER acd
EXPOSE 8000
CMD ["python", "-m", "agent_cost_down.server"]
