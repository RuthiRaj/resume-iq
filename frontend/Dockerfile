# =====================================================================
# ResumeIQ Frontend Production Dockerfile
# Multi-stage, unprivileged OCI container image for Next.js Standalone
# =====================================================================

# ---------------------------------------------------------------------
# Stage 1: Dependency Installation
# ---------------------------------------------------------------------
FROM node:20-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# ---------------------------------------------------------------------
# Stage 2: Production Build
# ---------------------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# ---------------------------------------------------------------------
# Stage 3: Hardened Production Runner
# ---------------------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Security: Run as unprivileged non-root user (UID 10001)
RUN addgroup --system --gid 10001 nodejs && \
    adduser --system --uid 10001 nextjs

# Set up runtime directories
RUN mkdir -p public .next && \
    chown -R nextjs:nodejs /app

# Copy Next.js standalone output and static assets
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ || exit 1

CMD ["node", "server.js"]
