# Mercury web UI on Google Cloud Run.
#
# Stage 1 builds the Vite bundle.  Stage 2 serves it via a tiny static-file
# server (we use `serve` because nginx pulls in glibc + 30 MB; serve is 5 MB).
# Stage 2 runs as non-root on a distroless-style nodejs base.
#
# The image is signed-out: no Ollama, no GPU, no Cortex backend bundled.
# When the user hits /cortex from this Cloud Run instance, the page falls
# back to Vertex AI Gemini for narration (see docs/CLOUD_FAILOVER.md) and
# proxies real-data requests to the GPU host's Mercury API via Cloudflare
# Tunnel — Cloud Run holds the session, the 5090 holds the model weights.

# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

# Install with --include=dev so we can run vite build
COPY package.json package-lock.json ./
RUN npm ci --include=dev

COPY . .
ENV NODE_ENV=production
ENV VITE_DEPLOY_TARGET=cloudrun
RUN npm run build

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime
WORKDIR /app

RUN addgroup -S mercury && adduser -S -G mercury mercury

# `serve` is a 30-line static server, sufficient for SPA routing
RUN npm install -g serve@14.2.4

COPY --from=build --chown=mercury:mercury /app/dist ./dist

USER mercury

# Cloud Run sets PORT.  serve respects it via -l.
ENV PORT=8080
EXPOSE 8080

# `--single` tells serve to fall through unknown paths to /index.html so the
# SPA router can take over (otherwise /cortex would 404 on a hard refresh).
CMD ["sh", "-c", "serve -s dist -l ${PORT}"]
