import { describe, expect, it } from "vitest";

import { matchGoOption, matchOperateur } from "@/lib/diagnosticConstants";

describe("matchOperateur", () => {
  it("reconnaît un fournisseur saisi en minuscule", () => {
    expect(matchOperateur("orange")).toBe("Orange");
  });

  it("reconnaît un alias (ex. Bouygues Telecom)", () => {
    expect(matchOperateur("Bouygues Telecom")).toBe("Bouygues");
  });

  it("retombe sur 'Autre / Aucun' pour un fournisseur non reconnu", () => {
    expect(matchOperateur("Coriolis")).toBe("Autre / Aucun");
  });

  it("renvoie une chaîne vide si le fournisseur n'est pas renseigné", () => {
    expect(matchOperateur(null)).toBe("");
    expect(matchOperateur("")).toBe("");
  });
});

describe("matchGoOption", () => {
  it("fait correspondre une consommation libre au palier le plus proche au-dessus", () => {
    expect(matchGoOption("120 Go")).toBe("Illimité");
    expect(matchGoOption("45Go")).toBe("50 Go");
    expect(matchGoOption("Forfait 20 Go")).toBe("20 Go");
  });

  it("reconnaît 'illimité' en texte libre", () => {
    expect(matchGoOption("Data illimitée")).toBe("Illimité");
  });

  it("renvoie une chaîne vide si aucune consommation data n'est détectée", () => {
    expect(matchGoOption("3500 kWh")).toBe("");
    expect(matchGoOption(null)).toBe("");
  });
});
