"""
Toegangscontrole voor de API-dienst in de OpenAEC SuperCloud.

Zelfde afspraak als de rekenkern van Open FEM Studio: de container kent alleen de SHA-256 van elke sleutel
(`OPENAEC_API_SLEUTELS`, komma-gescheiden) en de client stuurt `Authorization: Bearer <sleutel>`.
Zonder `OPENAEC_API_SLEUTELS` blijft de API open, zoals de losse zaagplan-site (frontend + backend) hem gebruikt.
"""

import hashlib
import hmac
import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse

# Open zonder sleutel: health en de beschrijving van de API.
VRIJ = {"/health", "/v1/health", "/v1/openapi.json", "/openapi.json", "/docs", "/redoc"}


def lees_sleutels(waarde: str | None) -> list[str]:
    """De SHA-256-hashes uit OPENAEC_API_SLEUTELS; een fout in de lijst stopt het starten."""
    hashes = [h.strip().lower() for h in (waarde or "").split(",") if h.strip()]
    for h in hashes:
        if not re.fullmatch(r"[0-9a-f]{64}", h):
            raise RuntimeError(
                f"OPENAEC_API_SLEUTELS: waarde van {len(h)} tekens is geen SHA-256 van 64 hextekens."
            )
    return hashes


def maak_controle(hashes: list[str]):
    async def controle(request: Request, call_next):
        if not hashes or request.method == "OPTIONS" or request.url.path in VRIJ:
            return await call_next(request)
        kop = request.headers.get("authorization", "")
        sleutel = kop[7:] if kop.startswith("Bearer ") else ""
        hash_ = hashlib.sha256(sleutel.encode()).hexdigest()
        if sleutel and any(hmac.compare_digest(hash_, h) for h in hashes):
            return await call_next(request)
        return JSONResponse(
            {"detail": "Stuur de sleutel mee als `Authorization: Bearer <sleutel>`."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return controle


SLEUTELS = lees_sleutels(os.environ.get("OPENAEC_API_SLEUTELS"))
