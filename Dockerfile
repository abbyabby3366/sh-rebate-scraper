FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Install Node.js 20 LTS in Ubuntu Playwright image
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt package.json package-lock.json* ./
RUN pip install --no-cache-dir -r requirements.txt && npm install

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]
