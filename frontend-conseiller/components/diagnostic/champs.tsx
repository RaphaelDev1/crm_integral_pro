"use client";

import type { InputHTMLAttributes } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

// Petits champs libellés partagés entre les étapes du diagnostic — évite de
// réécrire le même wrapper Label + Input/Select à chaque formulaire (ces
// écrans ne passent pas par react-hook-form/AppForm, voir useDiagnosticWizard).

export function Champ({
  label,
  className,
  ...inputProps
}: { label: string; className?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label>{label}</Label>
      <Input {...inputProps} />
    </div>
  );
}

export function ChampSelect({
  label,
  value,
  onChange,
  options,
  className,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly string[];
  className?: string;
  placeholder?: string;
}) {
  return (
    <div className={cn("space-y-2", className)}>
      <Label>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder={placeholder ?? "Sélectionner…"} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
