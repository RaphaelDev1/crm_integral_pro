import { expect, test } from "@playwright/test";

// Nécessite un compte conseiller existant en base (E2E_USERNAME / E2E_PASSWORD)
// et le backend FastAPI démarré — ignoré si non fourni, même approche que
// e2e/login.spec.ts.
const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;

test.describe("Clients", () => {
  test.skip(!username || !password, "E2E_USERNAME / E2E_PASSWORD non configurés.");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Identifiant").fill(username!);
    await page.getByLabel("Mot de passe").fill(password!);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("parcours création → édition → suppression d'un client", async ({ page }) => {
    const nom = `E2E-${Date.now()}`;

    await page.goto("/clients");
    await page.getByRole("button", { name: "Nouveau client" }).click();
    await page.getByLabel("Prénom").fill("Test");
    await page.getByLabel("Nom").fill(nom);
    await page.getByRole("button", { name: "Créer" }).click();

    await expect(page).toHaveURL(/\/clients\/\d+$/);
    await expect(page.getByRole("heading", { name: `Test ${nom}` })).toBeVisible();

    await page.getByLabel("Ville").fill("Lyon");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Client mis à jour.")).toBeVisible();

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Supprimer" }).click();
    await expect(page).toHaveURL(/\/clients$/);
    await expect(page.getByText(nom)).not.toBeVisible();
  });
});
