// Renommage purement cosmétique : la valeur stockée/technique reste "Admin"
// (require_role("Admin") côté backend, estAdmin() côté frontend) — seul le
// libellé affiché à l'utilisateur devient "Responsable".
export function libelleRole(role: string): string {
  return role === "Admin" ? "Responsable" : role;
}
