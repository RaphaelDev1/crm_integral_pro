import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IA Conseil — Votre espace client",
  description: "Suivez votre changement d'offre en quelques clics",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="font-sans text-slate-900 antialiased">
        <div className="max-w-2xl mx-auto px-4 py-6">
          <header className="mb-8">
            <h1 className="text-2xl font-bold text-primary">IA Conseil</h1>
            <p className="text-sm text-slate-500">Votre espace personnel</p>
          </header>
          {children}
          <footer className="mt-16 pt-8 border-t border-slate-200 text-xs text-slate-400 text-center">
            Sécurisé — Vos documents sont chiffrés et transmis uniquement aux fournisseurs concernés.
          </footer>
        </div>
      </body>
    </html>
  );
}
