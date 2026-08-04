FROM python:3.12-slim

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dbt-postgres
RUN pip install --no-cache-dir "dbt-postgres>=1.9,<2.0"

# Copy project files
COPY transform/ ./transform/
COPY scripts/ ./scripts/
COPY writeback/ ./writeback/
COPY db/ ./db/

# Run the monitor daily at 09:00 UTC by default
# Override with: docker compose run --rm monitor python scripts/dq_monitor.py --seed-failure
CMD ["sh", "scripts/daily_monitor.sh"]
