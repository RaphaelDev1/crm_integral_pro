'use client';

/**
 * AdresseAutocomplete — remplace le simple champ "code postal" de l'étape 3
 * par une recherche d'adresse (Base Adresse Nationale, via le proxy BFF
 * /api/leads/adresse-autocomplete — voir backend/routers/leads_public.py).
 * La sélection remonte l'adresse complète, le code INSEE et les coordonnées,
 * utilisés côté backend pour la bannière fibre de l'étape 4 (P2.1).
 *
 * Reste utilisable sans sélectionner de suggestion : le champ texte libre est
 * conservé pour ne jamais bloquer un visiteur si l'API BAN est indisponible.
 */
import { useEffect, useRef, useState } from 'react';

export type AdresseSuggestion = {
  label: string;
  code_postal?: string;
  ville?: string;
  code_insee?: string;
  latitude?: number;
  longitude?: number;
};

export function AdresseAutocomplete({
  value,
  onChange,
  onSelect,
}: {
  value: string;
  onChange: (v: string) => void;
  onSelect: (suggestion: AdresseSuggestion) => void;
}) {
  const [suggestions, setSuggestions] = useState<AdresseSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim().length < 3) {
      setSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await fetch(`/api/leads/adresse-autocomplete?q=${encodeURIComponent(value)}`);
        if (!res.ok) return;
        const data: AdresseSuggestion[] = await res.json();
        setSuggestions(data);
        setOpen(data.length > 0);
      } catch {
        // API indisponible — le champ reste utilisable en saisie libre.
      }
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-sm font-medium text-slate-700">
        Adresse (optionnel — vérif éligibilité fibre)
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        autoComplete="off"
        placeholder="12 rue de la Paix, 75002 Paris"
        className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
      />
      {open && suggestions.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          {suggestions.map((s) => (
            <li key={s.label}>
              <button
                type="button"
                onClick={() => {
                  onChange(s.label);
                  onSelect(s);
                  setOpen(false);
                }}
                className="block w-full px-4 py-2 text-left text-sm text-slate-700 hover:bg-sky-50"
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
