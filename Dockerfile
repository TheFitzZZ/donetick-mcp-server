# Multi-stage Dockerfile for Donetick MCP Server

FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy all files needed for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Set Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default transport (can be overridden: stdio or sse)
ENV MCP_TRANSPORT=stdio \
    SSE_HOST=0.0.0.0 \
    SSE_PORT=3000

# Expose port for SSE transport
EXPOSE 3000

# Health check for SSE mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD if [ "$MCP_TRANSPORT" = "sse" ]; then python -c "import httpx; httpx.get('http://localhost:3000/health').raise_for_status()"; else exit 0; fi

# Run the MCP server
CMD ["python", "-m", "donetick_mcp.server"]
