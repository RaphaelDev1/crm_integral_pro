import { expect, test } from "@playwright/test";

// Nécessite un compte conseiller existant en base (E2E_USERNAME / E2E_PASSWORD)
// et le backend FastAPI démarré — ignoré si non fourni, pour ne pas casser un
// lancement local sans backend ni base seedée.
const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;

test.describe("Connexion", () => {
  test.skip(!username || !password, "E2E_USERNAME / E2E_PASSWORD non configurés.");

  test("un login réussi redirige vers le tableau de bord", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Identifiant").fill(username!);
    await page.getByLabel("Mot de passe").fill(password!);
    await page.getByRole("button", { name: "Se connecter" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeVisible();
  });
});
