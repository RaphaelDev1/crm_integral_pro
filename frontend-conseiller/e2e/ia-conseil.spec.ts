import { expect, test, type Page } from "@playwright/test";

// Sous-système "IA Conseil" (trame adaptative, isolé du CRM existant — voir
// PLAN_IMPLEMENTATION_4_PHASES.md). Nécessite, comme les autres specs e2e/
// (voir login.spec.ts / diagnostic.spec.ts) : un compte conseiller
// (E2E_USERNAME / E2E_PASSWORD), le backend FastAPI démarré, ET le catalogue
// IA Conseil seedé (`python -m backend.scripts.seed_ia_conseil`, catégorie
// "mobile" au minimum) — ignoré sinon.
const username = process.env.E2E_USERNAME;
const password = process.env.E2E_PASSWORD;

// La trame est dynamique (principe "escargot", §Principe #1) : l'ordre et le
// nombre de questions posées varient selon les réponses. Cette boucle répond
// génériquement à la question affichée jusqu'à ce que la trame se termine,
// plutôt que de coder en dur un scénario de questions précises.
async function repondreJusquaLaFinDeLaTrame(page: Page) {
  const titreTerminee = page.getByRole("heading", { name: "Trame terminée" });

  for (let tentative = 0; tentative < 40; tentative += 1) {
    if (await titreTerminee.isVisible().catch(() => false)) return;

    const boutonOui = page.getByRole("button", { name: "Oui", exact: true });
    if (await boutonOui.isVisible().catch(() => false)) {
      await boutonOui.click();
      continue;
    }

    const combobox = page.getByRole("combobox").first();
    if (await combobox.isVisible().catch(() => false)) {
      await combobox.click();
      await page.getByRole("option").first().click();
      await page.getByRole("button", { name: "Suivant" }).click();
      continue;
    }

    const input = page.locator('main input[type="number"], main input[type="text"]').first();
    if (await input.isVisible().catch(() => false)) {
      await input.fill("10");
      await page.getByRole("button", { name: "Suivant" }).click();
      continue;
    }

    await page.waitForTimeout(300);
  }

  throw new Error("La trame ne s'est pas terminée après 40 réponses.");
}

test.describe("IA Conseil — trame live", () => {
  test.skip(!username || !password, "E2E_USERNAME / E2E_PASSWORD non configurés.");

  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Identifiant").fill(username!);
    await page.getByLabel("Mot de passe").fill(password!);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("créer un client → dérouler la trame mobile → recommandations → PDF → souscription", async ({ page }) => {
    const nom = `E2E-IaConseil-${Date.now()}`;

    await page.goto("/ia-conseil/clients");
    await page.getByRole("button", { name: "Nouveau client" }).click();
    await page.getByLabel("Prénom").fill("Test");
    await page.getByLabel("Nom").fill(nom);
    await page.getByRole("button", { name: "Créer" }).click();

    await expect(page).toHaveURL(/\/ia-conseil\/clients\/[0-9a-f-]+$/);

    await page.getByRole("combobox").first().click();
    await page.getByRole("option", { name: "Mobile", exact: true }).click();
    await page.getByRole("button", { name: "Démarrer la trame" }).click();

    await expect(page).toHaveURL(/\/ia-conseil\/clients\/[0-9a-f-]+\/trame\/[0-9a-f-]+$/);

    await repondreJusquaLaFinDeLaTrame(page);

    await expect(page.getByText(/recommandation/i).first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Voir la synthèse" }).click();
    await expect(page.getByRole("heading", { name: "Synthèse de la trame" })).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Télécharger la synthèse PDF" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toContain("synthese-ia-conseil");

    await page.getByRole("button", { name: "Enregistrer la souscription" }).click();
    await expect(page.getByText("Souscription enregistrée.")).toBeVisible({ timeout: 10_000 });
  });
});
