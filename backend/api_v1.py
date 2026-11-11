"""
Vaste versie van de API (/v1) voor de OpenAEC SuperCloud en andere clients.

Dezelfde rekenregels als de routes zonder voorvoegsel; /v1 verandert niet meer zonder nieuwe versie.
`/v1/tools` beschrijft de tools voor de assistent: alleen rekenen, dus zonder `bevestigen`. Een resultaat
bewaren in Docs doet de SuperCloud zelf, na bevestiging door de gebruiker.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v1")

TOOLS = [
    {
        "name": "zaagplan_algoritmen",
        "description": "Lijst van de beschikbare algoritmen voor 1D- en 2D-zaagplannen.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "methode": "GET",
        "pad": "/v1/algorithms",
    },
    {
        "name": "zaagplan_optimaliseer_1d",
        "description": (
            "Bereken een 1D-zaagplan: welke onderdelen uit welke handelslengten, met zaagsnede en restafval. "
            "Wijzigt niets; het resultaat bewaren gebeurt apart, na bevestiging."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["parts", "stocks"],
            "properties": {
                "parts": {
                    "type": "array",
                    "description": "Onderdelen: id, length (mm), quantity, label.",
                    "items": {
                        "type": "object",
                        "required": ["id", "length"],
                        "properties": {
                            "id": {"type": "string"},
                            "length": {"type": "number"},
                            "quantity": {"type": "integer", "default": 1},
                            "label": {"type": "string"},
                        },
                    },
                },
                "stocks": {
                    "type": "array",
                    "description": "Voorraad: id, length (mm), quantity (-1 = onbeperkt), cost, label.",
                    "items": {
                        "type": "object",
                        "required": ["id", "length"],
                        "properties": {
                            "id": {"type": "string"},
                            "length": {"type": "number"},
                            "quantity": {"type": "integer", "default": -1},
                            "cost": {"type": "number", "default": 1.0},
                            "label": {"type": "string"},
                        },
                    },
                },
                "kerf": {"type": "number", "default": 3.0, "description": "Zaagsnede in mm."},
                "algorithm": {
                    "type": "string",
                    "enum": ["ortools_optimal", "ortools_fast", "ffd", "hybrid"],
                    "default": "hybrid",
                },
                "max_split_parts": {"type": "integer", "default": 2},
                "joint_allowance": {"type": "number", "default": 0.0},
            },
        },
        "methode": "POST",
        "pad": "/v1/optimize/1d",
    },
]


def registreer(health, algorithms, optimize_1d, optimize_2d, app):
    router.add_api_route("/health", health, methods=["GET"])
    router.add_api_route("/algorithms", algorithms, methods=["GET"])
    router.add_api_route("/optimize/1d", optimize_1d, methods=["POST"])
    router.add_api_route("/optimize/2d", optimize_2d, methods=["POST"])
    router.add_api_route("/tools", lambda: {"tools": TOOLS}, methods=["GET"])
    router.add_api_route("/openapi.json", lambda: app.openapi(), methods=["GET"], include_in_schema=False)
    app.include_router(router)
