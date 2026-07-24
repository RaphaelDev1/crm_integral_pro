/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Runtime minimal autosuffisant pour l'image Docker (voir frontend-portail/Dockerfile).
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
  async headers() {
    // API backend + Sentry sont les seules destinations réseau nécessaires à ce
    // portail (aucun tiers embarqué, aucun script/style externe) : CSP resserrée
    // en conséquence plutôt qu'une politique par défaut permissive.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const sentryConnect = "https://*.ingest.sentry.io https://*.ingest.de.sentry.io";
    const csp = [
      "default-src 'self'",
      `connect-src 'self' ${apiUrl} ${sentryConnect}`,
      "img-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline'",
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
// maps) — voir DEPLOIEMENT.md pour la configuration complète en prod.
module.exports = withSentryConfig(nextConfig, {
  silent: true,
});
