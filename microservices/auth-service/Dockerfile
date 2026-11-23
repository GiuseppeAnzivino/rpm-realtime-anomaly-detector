# Same Python version used by the CI pipeline
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# NOTE: requirements.txt still includes the test dependencies (pytest, pytest-cov).
# They will be moved to a separate file when test dependencies are split.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Only the application code: tests and pytest configuration stay out of the image
COPY src ./src

# Run as a non-root user
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]