import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ClientForm } from "@/components/clients/ClientForm";

describe("ClientForm", () => {
  it("rejette la création sans prénom ni nom", async () => {
    const onSubmit = vi.fn();
    render(
      <ClientForm
        mode="create"
        defaultValues={{ prenom: "", nom: "" }}
        onSubmit={onSubmit}
        submitLabel="Créer"
      />
    );

    await userEvent.click(screen.getByRole("button", { name: "Créer" }));

    expect(await screen.findByText("Le prénom est requis.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("soumet les valeurs saisies en mode création", async () => {
    const onSubmit = vi.fn();
    render(
      <ClientForm
        mode="create"
        defaultValues={{ prenom: "", nom: "" }}
        onSubmit={onSubmit}
        submitLabel="Créer"
      />
    );

    await userEvent.type(screen.getByLabelText("Prénom"), "Jean");
    await userEvent.type(screen.getByLabelText("Nom"), "Dupont");
    await userEvent.click(screen.getByRole("button", { name: "Créer" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ prenom: "Jean", nom: "Dupont" }));
  });

  it("autorise l'édition sans prénom ni nom (schéma update)", async () => {
    const onSubmit = vi.fn();
    render(
      <ClientForm
        mode="edit"
        defaultValues={{ prenom: "Jean", nom: "Dupont", ville: "" }}
        onSubmit={onSubmit}
        submitLabel="Enregistrer"
      />
    );

    await userEvent.clear(screen.getByLabelText("Prénom"));
    await userEvent.type(screen.getByLabelText("Ville"), "Lyon");
    await userEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ ville: "Lyon" }));
  });
});
