FROM astral/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Copy the backend source code into the container
COPY . .

# Mount the additional context smolagents_src to /mnt/smolagents
# The override file redirects the dependency to this local mount
RUN --mount=from=smolagents_src,target=/mnt/smolagents,rw \
    uv pip install --system --override overrides.txt .

CMD ["python", "-m", "backend.transport.start_web_socket"]