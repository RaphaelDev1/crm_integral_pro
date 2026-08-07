"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

// Bascule simple clair/sombre (pas de mode "système" exposé à l'utilisateur
// — juste les deux états demandés). `mounted` évite un mismatch d'hydratation
// : le thème résolu n'est connu qu'après montage côté client.
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return <Button variant="ghost" size="icon" disabled aria-hidden className="opacity-0" />;
  }

  const sombre = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(sombre ? "light" : "dark")}
      title={sombre ? "Passer en mode clair" : "Passer en mode sombre"}
      aria-label={sombre ? "Passer en mode clair" : "Passer en mode sombre"}
    >
      {sombre ? <Sun size={18} /> : <Moon size={18} />}
    </Button>
  );
}
