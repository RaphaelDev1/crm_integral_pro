import type { Metadata } from "next";

import { AuthProvider } from "@/contexts/AuthContext";

import { Providers } from "./providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "IA Conseil — Outil conseiller",
  description: "Diagnostic client, prospects, clients, facturation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="font-sans text-slate-900 antialiased dark:text-slate-100">
        <Providers>
          <AuthProvider>{children}</AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
