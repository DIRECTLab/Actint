ARG NODE_VERSION=22-alpine

# =========================================
# Stage 1: Dependencies
# =========================================
FROM node:${NODE_VERSION} AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

# =========================================
# Stage 2: Builder
# =========================================
FROM node:${NODE_VERSION} AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Environment variables must be present at build time for Next.js
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# =========================================
# Stage 3: Runner
# =========================================
FROM node:${NODE_VERSION} AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-privileged user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy essential files from the builder
COPY --from=builder /app/public ./public

# Set the correct permissions for the cache folder
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Leverages the standalone output built in Stage 2
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# The standalone build creates a server.js file
CMD ["node", "server.js"]