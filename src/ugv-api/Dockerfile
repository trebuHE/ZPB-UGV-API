FROM ros:jazzy-ros-base

WORKDIR /app

# System deps (pip is not included in ros-base)
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip python3-venv ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

    
# Virtual environment — avoids PEP 668 (externally-managed-environment)
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Python deps (cached layer — only rebuilt when requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project code (copied last so code edits don't invalidate the deps layer)
COPY bridge/ ./bridge/
COPY api/ ./api/