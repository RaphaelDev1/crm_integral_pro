# ==============================================================================
#  Image portail client Next.js. Contexte de build = frontend-portail/ (projet
#  Node autonome, séparé du reste du dépôt).
#  Build : docker build -t ia-conseil-portail frontend-portail
# ==============================================================================
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* est figé au build par Next.js — passer la vraie valeur via
# --build-arg en prod si elle diffère de la valeur par défaut de next.config.js.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

# `output: "standalone"` (next.config.js) : runtime minimal, sans node_modules complet.
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
