# Zaagplan als API

De backend (`backend/`, FastAPI) is ook een losse API-dienst, bijvoorbeeld naast een omgeving van de OpenAEC
SuperCloud (`deploy/staging-bench/diensten-zaagplan.yaml` in openaec-supercloud).

| Route | Doel | Sleutel nodig |
|-------|------|---------------|
| `GET /v1/health` | Draait de dienst, welke versie | nee |
| `GET /v1/openapi.json` | OpenAPI-beschrijving | nee |
| `GET /v1/tools` | Tools voor een assistent (naam, beschrijving, invoerschema, route) | ja |
| `GET /v1/algorithms` | Beschikbare algoritmen | ja |
| `POST /v1/optimize/1d` | 1D-zaagplan berekenen | ja |
| `POST /v1/optimize/2d` | Nog niet beschikbaar (501) | ja |

`/v1` blijft gelijk; een wijziging die bestaande clients breekt, krijgt `/v2`. De routes zonder voorvoegsel blijven
voor de zaagplan-site.

## Sleutels

Zonder `OPENAEC_API_SLEUTELS` is de API open (zoals de site hem gebruikt, achter nginx). Met sleutels:

```bash
printf %s "<sleutel>" | sha256sum
OPENAEC_API_SLEUTELS=<hash1>,<hash2>
```

De client stuurt `Authorization: Bearer <sleutel>`. De container kent alleen de hashes.

## Mens in de lus

De tools rekenen alleen en wijzigen niets, dus de assistent mag ze zonder vragen aanroepen. Een zaagplan bewaren in
Docs doet de SuperCloud, pas na bevestiging door de gebruiker.

## Voorbeeld

```bash
curl -s http://localhost:8000/v1/optimize/1d -H "Authorization: Bearer $SLEUTEL" -H "content-type: application/json" \
  -d '{"parts":[{"id":"a","length":1200,"quantity":3}],"stocks":[{"id":"s","length":3000}]}'
```
