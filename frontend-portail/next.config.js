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
    // Le Fast Refresh de Next.js (webpack dev server) évalue les modules via
    // eval() en dev — sans 'unsafe-eval' ici, le bundle entier plante au
    // premier HMR et la page reste bloquée en chargement infini. Pas de eval
    // en build de production, donc pas besoin de l'assouplir là.
    const scriptSrc = process.env.NODE_ENV === "production"
      ? "script-src 'self' 'unsafe-inline'"
      : "script-src 'self' 'unsafe-inline' 'unsafe-eval'";
    const csp = [
      "default-src 'self'",
      `connect-src 'self' ${apiUrl} ${sentryConnect}`,
      "img-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      scriptSrc,
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
