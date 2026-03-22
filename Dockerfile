FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (required by HF Spaces)
RUN useradd -m -u 1000 user
ENV HOME=/home/user PATH="/home/user/.local/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY --chown=user . .

# Create .streamlit config for HF
RUN mkdir -p .streamlit && \
    echo '[server]\nheadless = true\nport = 7860\naddress = "0.0.0.0"\nenableCORS = false\nenableXsrfProtection = false\n\n[theme]\nbase = "dark"\nprimaryColor = "#3b82f6"\nbackgroundColor = "#000000"\nsecondaryBackgroundColor = "#0a0a0a"\ntextColor = "#e2e8f0"\n\n[browser]\ngatherUsageStats = false' > .streamlit/config.toml

USER user

EXPOSE 7860

HEALTHCHECK CMD curl --fail http://localhost:7860/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=7860", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
