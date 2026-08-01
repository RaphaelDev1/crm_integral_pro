import { expect, test } from "@playwright/test";

// Nécessite un compte conseiller existant (E2E_USERNAME / E2E_PASSWORD), le
// backend FastAPI démarré ET un catalogue d'offres Télécom/Mobile non vide
// (voir Admin > Catalogue > Pré-remplir) — ignoré sinon, même approche que
// e2e/clients.spec.ts. Le parcours ne couvre qu'un seul univers (Télécom) :
// le principe (comparaison → panier → PDF) est identique pour Énergie et
// Abonnements, inutile de le retester trois fois en E2E.
const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;

test.describe("Diagnostic", () => {
  test.skip(!username || !password, "E2E_USERNAME / E2E_PASSWORD non configurés.");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Identifiant").fill(username!);
    await page.getByLabel("Mot de passe").fill(password!);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("diagnostic Télécom complet → panier → PDF téléchargé", async ({ page }) => {
    const nom = `E2E-Diag-${Date.now()}`;

    await page.goto("/diagnostic");

    // Étape 1 — Univers
    await page.getByText("Télécom", { exact: true }).click();
    await page.getByRole("button", { name: "Mobile uniquement" }).click();
    await page.getByRole("button", { name: "Suivant" }).click();

    // Étape 2 — Identité (nouvelle fiche)
    await page.getByLabel("Prénom *").fill("Test");
    await page.getByLabel("Nom *").fill(nom);
    await page.getByRole("button", { name: "Suivant" }).click();

    // Étape 3 — Situation actuelle Télécom
    await expect(page.getByText("Situation actuelle du client")).toBeVisible();
    await page.getByText("Opérateur actuel *").locator("..").getByRole("combobox").click();
    await page.getByRole("option", { name: "Orange", exact: true }).click();
    await page.getByLabel("Coût mensuel actuel (€) *").fill("35");
    await page.getByText("Satisfaction réseau", { exact: false }).locator("..").getByRole("combobox").click();
    await page.getByRole("option", { name: "Ça va", exact: false }).click();
    await page.getByRole("button", { name: "Suivant" }).click();

    // Étape 4 — Recommandations
    await expect(page.getByText(`Recommandations pour Test ${nom}`)).toBeVisible();
    const ajouterPanier = page.getByRole("button", { name: "⭐ Ajouter au panier" }).first();
    await expect(ajouterPanier).toBeVisible({ timeout: 15_000 });
    await ajouterPanier.click();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Générer restitution PDF" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain("restitution_télécom");

    await expect(page).toHaveURL(/\/clients\/\d+$/);
  });
});
