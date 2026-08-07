from pydantic import BaseModel


class PurgeDonneesTestOut(BaseModel):
    clients_supprimes: int
    prospects_supprimes: int
    fichiers_supprimes: int
