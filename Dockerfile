# Use standard python alpine image
FROM python:3.13-alpine

WORKDIR /app

# Install uv via pip (most compatible way to avoid image pull errors)
RUN pip install --no-cache-dir uv

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# We use --system to install into the image's python environment
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the application
COPY . .

# Install the project
RUN uv sync --frozen --no-dev

# Run the application
CMD ["python", "app/main.py"]
