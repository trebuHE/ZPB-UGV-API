FROM ros:jazzy-ros-base

WORKDIR /app

# System dependencies and CycloneDDS RMW packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-venv git \
    ros-jazzy-rmw-cyclonedds-cpp ros-jazzy-cyclonedds \
    && rm -rf /var/lib/apt/lists/*

# Default ROS 2 RMW implementation
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Create a virtual environment with system site packages enabled:
# Isolates pip dependencies (PEP 668 compliance) while granting the venv interpreter access to system ROS 2 packages (rclpy)
RUN python3 -m venv --system-site-packages /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Automatically source ROS 2 environment and activate the venv for interactive bash sessions
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc \
    && echo "source /opt/venv/bin/activate" >> /root/.bashrc

# Copy project source files
COPY bridge/ ./bridge/
COPY api/ ./api/

# Official ROS 2 entrypoint ensuring ROS environment setup before executing container commands
ENTRYPOINT ["/ros_entrypoint.sh"]

# Run the FastAPI application with uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]