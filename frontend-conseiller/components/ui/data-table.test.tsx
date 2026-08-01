import type { ColumnDef } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { DataTable } from "@/components/ui/data-table";

interface Row {
  nom: string;
  ville: string;
}

const columns: ColumnDef<Row>[] = [
  { accessorKey: "nom", header: "Nom" },
  { accessorKey: "ville", header: "Ville" },
];

const data: Row[] = [
  { nom: "Dupont", ville: "Lyon" },
  { nom: "Martin", ville: "Paris" },
];

describe("DataTable", () => {
  it("affiche toutes les lignes par défaut", () => {
    render(<DataTable columns={columns} data={data} />);
    expect(screen.getByText("Dupont")).toBeInTheDocument();
    expect(screen.getByText("Martin")).toBeInTheDocument();
  });

  it("filtre les lignes via le champ de recherche", async () => {
    render(<DataTable columns={columns} data={data} filterColumn="nom" filterPlaceholder="Rechercher un nom" />);
    await userEvent.type(screen.getByPlaceholderText("Rechercher un nom"), "Dupont");
    expect(screen.getByText("Dupont")).toBeInTheDocument();
    expect(screen.queryByText("Martin")).not.toBeInTheDocument();
  });

  it("affiche le message vide quand il n'y a aucune donnée", () => {
    render(<DataTable columns={columns} data={[]} emptyMessage="Rien à afficher" />);
    expect(screen.getByText("Rien à afficher")).toBeInTheDocument();
  });
});
