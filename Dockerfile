FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY presentation_search ./presentation_search
RUN pip install --no-cache-dir . && useradd --uid 10001 --create-home appuser
COPY --chown=10001:10001 data/presentations ./data/presentations
COPY --chown=10001:10001 scripts ./scripts
RUN mkdir -p /app/state && chown -R 10001:10001 /app/state
USER 10001
ENV DRAFTS_PATH=/app/state/drafts SHAREPOINT_CACHE_PATH=/app/state/sharepoint-cache
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "presentation_search.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
