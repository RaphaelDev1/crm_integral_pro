// Capture d'exceptions côté navigateur. No-op tant que NEXT_PUBLIC_SENTRY_DSN
// n'est pas renseigné (dev) — voir frontend-portail/.env.example. Convention
// Next.js (remplace sentry.client.config.ts, requis pour compat Turbopack).
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
