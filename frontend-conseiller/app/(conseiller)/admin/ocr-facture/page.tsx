"use client";

import { AnalyseFactureForm } from "@/components/factures/AnalyseFactureForm";
import { AdminGuard } from "@/components/layout/AdminGuard";

export default function OcrFacturePage() {
  return (
    <AdminGuard>
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-primary">OCR facture</h1>
        <AnalyseFactureForm />
      </div>
    </AdminGuard>
  );
}
