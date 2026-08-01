/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Runtime minimal autosuffisant pour l'image Docker (voir frontend-conseiller/Dockerfile).
  output: "standalone",
  async headers() {
    // Tous les appels vers l'API passent par le proxy BFF same-origin
    // (app/api/backend/[...path]/route.ts) : pas besoin d'ouvrir connect-src
    // vers le backend FastAPI, contrairement à frontend-portail qui appelle
    // l'API directement depuis le navigateur.
    const sentryConnect = "https://*.ingest.sentry.io https://*.ingest.de.sentry.io";
    // 'unsafe-eval' est requis par le Fast Refresh de `next dev` (webpack HMR
    // utilise eval() pour les source maps) — sans lui, le JS de l'app ne
    // s'exécute plus du tout en dev (voir issue login qui n'envoyait aucune
    // requête). Jamais ajouté en production.
    const isDev = process.env.NODE_ENV !== "production";
    const csp = [
      "default-src 'self'",
      `connect-src 'self' ${sentryConnect}`,
      "img-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
      "font-src 'self'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

const { withSentryConfig } = require("@sentry/nextjs");

// `silent: true` + pas d'org/project/authToken : le build fonctionne à
// l'identique sans compte Sentry configuré (juste pas d'upload de source
// maps).
module.exports = withSentryConfig(nextConfig, {
  silent: true,
});
