# Dockerfile – Tasky Discord Bot
# 
# Build: docker build -t tasky .
# Run:   docker run -e TOKEN=xxx -e GEMINI_API_KEY=yyy --name tasky tasky

FROM python:3.11-slim

# ============================================================================
# METADATA
# ============================================================================

LABEL maintainer="Tasky Team"
LABEL description="Tasky: Discord Accountability Bot with Gemini AI"

# ============================================================================
# SETUP
# ============================================================================

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data and logs directories
RUN mkdir -p data logs

# ============================================================================
# ENVIRONMENT & CONFIGURATION
# ============================================================================

# These must be set at runtime
ENV TOKEN=""
ENV GEMINI_API_KEY=""
ENV GEMINI_MODEL="gemini-2.5-flash"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ============================================================================
# HEALTH CHECK
# ============================================================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os; exit(0 if os.getenv('TOKEN') else 1)" || exit 1

# ============================================================================
# ENTRYPOINT
# ============================================================================

CMD ["python", "entrypoint.py"]
