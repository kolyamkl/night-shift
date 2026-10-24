# MuGuard web front end for Railway: static build served by Caddy, /api proxied to the backend.
# Build context is the repo root: docker build -f frontend/Dockerfile .
FROM node:22-alpine AS build
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2.10-alpine
COPY frontend/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
