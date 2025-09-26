# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install application dependencies
RUN pip install --no-cache-dir \
    "fastapi>=0.117.1" \
    "httpx[socks]>=0.28.1" \
    "langchain-openai>=0.3.33" \
    "langgraph>=0.6.7" \
    "openai>=1.109.0" \
    "uvicorn[standard]>=0.37.0"

# Copy application source code
COPY app ./app
COPY main.py ./main.py

# Expose the FastAPI/uvicorn port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
