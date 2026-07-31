# ==============================================================================
#  Image outil conseiller Next.js. Contexte de build = frontend-conseiller/
#  (projet Node autonome, séparé du reste du dépôt).
#  Build : docker build -t ia-conseil-frontend-conseiller frontend-conseiller
# ==============================================================================
FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# `output: "standalone"` (next.config.js) : runtime minimal, sans node_modules complet.
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

# BACKEND_URL n'est PAS figé au build (lu uniquement côté serveur au runtime,
# contrairement à NEXT_PUBLIC_API_URL dans frontend-portail) : passer la
# vraie valeur via `docker run -e BACKEND_URL=...` en prod.
EXPOSE 3001
ENV PORT=3001
CMD ["node", "server.js"]
