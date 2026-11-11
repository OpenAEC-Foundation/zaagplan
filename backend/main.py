"""
Zaagplan Optimizer - FastAPI Backend
REST API voor 1D en 2D optimalisatie

Auteur: OpenAEC (Jochem Bosman & Claude)
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import List, Optional
import uvicorn
import logging
import json

# Logging configuratie
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

from optimizer_1d import (
    Optimizer1D, 
    Part, 
    Stock, 
    Algorithm, 
    result_to_dict,
    ORTOOLS_AVAILABLE
)

app = FastAPI(
    title="Zaagplan Optimizer API",
    description="REST API voor 1D en 2D zaagplan optimalisatie",
    version="2.0.0"
)

# CORS voor frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In productie: specifieke origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sleutelcontrole (OPENAEC_API_SLEUTELS); zonder sleutels blijft de API open.
from toegang import SLEUTELS, maak_controle
app.middleware("http")(maak_controle(SLEUTELS))


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log alle requests voor debugging"""
    logger.info(f"→ {request.method} {request.url.path}")
    
    # Log request body voor POST
    if request.method == "POST":
        body = await request.body()
        if body:
            try:
                body_json = json.loads(body)
                logger.debug(f"  Request body: {json.dumps(body_json, indent=2)[:1000]}...")
            except:
                logger.debug(f"  Request body (raw): {body[:500]}")
        
        # Reset body zodat endpoint het kan lezen
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive
    
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} → {response.status_code}")
    return response


# ============ REQUEST MODELS ============

class PartInput(BaseModel):
    id: str
    length: float
    quantity: int = 1
    label: Optional[str] = None


class StockInput(BaseModel):
    id: str
    length: float
    quantity: int = -1
    cost: float = 1.0
    label: Optional[str] = None


class Optimize1DRequest(BaseModel):
    parts: List[PartInput]
    stocks: List[StockInput]
    kerf: float = 3.0
    algorithm: str = "hybrid"
    max_split_parts: int = 2  # Max aantal delen per onderdeel
    joint_allowance: float = 0.0  # Extra lengte per verbinding


# ============ ENDPOINTS ============

@app.get("/")
def root():
    """Health check en info"""
    return {
        "service": "Zaagplan Optimizer API",
        "version": "2.0.0",
        "status": "running",
        "ortools_available": ORTOOLS_AVAILABLE,
        "algorithms_1d": [a.value for a in Algorithm],
    }


@app.get("/health")
def health():
    """Simple health check voor Docker"""
    return {"status": "ok", "version": app.version}


@app.post("/debug/request")
async def debug_request(request: Request):
    """Debug endpoint: toon wat de frontend stuurt"""
    body = await request.body()
    try:
        body_json = json.loads(body)
        
        # Probeer te valideren
        errors = []
        try:
            validated = Optimize1DRequest(**body_json)
            logger.info("✓ Request valideert correct!")
        except ValidationError as e:
            errors = e.errors()
            logger.error(f"✗ Validatie errors: {errors}")
        
        return {
            "raw_body": body_json,
            "validation_errors": errors,
            "parts_count": len(body_json.get("parts", [])),
            "stocks_count": len(body_json.get("stocks", [])),
            "parts_sample": body_json.get("parts", [])[:2],
            "stocks_sample": body_json.get("stocks", [])[:2]
        }
    except json.JSONDecodeError as e:
        return {"error": "Invalid JSON", "detail": str(e), "raw": body.decode()[:500]}


@app.get("/algorithms")
def get_algorithms():
    """Lijst van beschikbare algoritmes"""
    return {
        "1d": [
            {
                "id": "ortools_optimal",
                "name": "OR-Tools Optimaal",
                "description": "Exacte oplossing via Column Generation. Beste resultaat, kan langzamer zijn bij veel onderdelen.",
                "available": ORTOOLS_AVAILABLE
            },
            {
                "id": "ortools_fast",
                "name": "OR-Tools Snel",
                "description": "Snelle heuristiek via OR-Tools MIP solver.",
                "available": ORTOOLS_AVAILABLE
            },
            {
                "id": "ffd",
                "name": "First Fit Decreasing",
                "description": "Simpele greedy heuristiek. Zeer snel, ~15-20% suboptimaal.",
                "available": True
            },
            {
                "id": "hybrid",
                "name": "Hybrid (Aanbevolen)",
                "description": "Combinatie: grote stukken eerst, kleine stukken in reststukken. Goede balans snelheid/kwaliteit.",
                "available": True
            }
        ],
        "2d": [
            {
                "id": "maxrects",
                "name": "MaxRects (Huidig)",
                "description": "Greedy rechthoek-packing. Snel maar niet optimaal.",
                "available": True
            },
            {
                "id": "nfp",
                "name": "NFP Nesting (Planned)",
                "description": "No-Fit Polygon voor irreguliere vormen. In ontwikkeling.",
                "available": False
            }
        ]
    }


@app.post("/optimize/1d")
def optimize_1d(request: Optimize1DRequest):
    """
    Optimaliseer 1D zaagplan
    
    Body:
    - parts: Lijst van onderdelen met id, length, quantity
    - stocks: Lijst van voorraad met id, length
    - kerf: Zaagsnede breedte (default: 3mm)
    - algorithm: ortools_optimal | ortools_fast | ffd | hybrid
    """
    logger.info(f"=== START OPTIMIZE 1D ===")
    logger.info(f"Algoritme: {request.algorithm}")
    logger.info(f"Parts: {len(request.parts)} stuks")
    logger.info(f"Stocks: {len(request.stocks)} types")
    logger.info(f"Kerf: {request.kerf}mm")
    logger.info(f"Max split: {request.max_split_parts}, Joint: {request.joint_allowance}mm")
    
    # Valideer algorithm
    try:
        algo = Algorithm(request.algorithm)
    except ValueError:
        logger.error(f"Onbekend algoritme: {request.algorithm}")
        raise HTTPException(
            status_code=400,
            detail=f"Onbekend algoritme: {request.algorithm}. "
                   f"Kies uit: {[a.value for a in Algorithm]}"
        )
    
    # Check OR-Tools beschikbaarheid
    if algo in [Algorithm.ORTOOLS_OPTIMAL, Algorithm.ORTOOLS_FAST] and not ORTOOLS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="OR-Tools is niet geïnstalleerd op de server. "
                   "Gebruik 'hybrid' of 'ffd' algoritme."
        )
    
    # Converteer input
    parts = [
        Part(
            id=p.id,
            length=p.length,
            quantity=p.quantity,
            label=p.label or p.id
        )
        for p in request.parts
    ]
    
    stocks = [
        Stock(
            id=s.id,
            length=s.length,
            quantity=s.quantity,
            cost=s.cost,
            label=s.label or f"{s.length}mm"
        )
        for s in request.stocks
    ]
    
    # Validatie
    if not parts:
        raise HTTPException(status_code=400, detail="Geen onderdelen opgegeven")
    if not stocks:
        raise HTTPException(status_code=400, detail="Geen voorraad opgegeven")
    
    logger.debug(f"Parts na conversie: {[(p.id, p.length, p.quantity) for p in parts[:5]]}...")
    logger.debug(f"Stocks na conversie: {[(s.id, s.length, s.quantity) for s in stocks]}")
    
    # Optimaliseer
    logger.info("Starting optimalisatie...")
    optimizer = Optimizer1D(kerf=request.kerf)
    result = optimizer.optimize(
        parts, 
        stocks, 
        algo,
        max_split_parts=request.max_split_parts,
        joint_allowance=request.joint_allowance
    )
    
    logger.info(f"=== RESULTAAT ===")
    logger.info(f"Stocks gebruikt: {result.total_stocks_used}")
    logger.info(f"Afval: {result.waste_percentage:.1f}%")
    logger.info(f"Tijd: {result.computation_time_ms:.1f}ms")
    logger.info(f"Niet geplaatst: {len(result.parts_not_placed)} stuks")
    
    return result_to_dict(result)


# ============ 2D PLACEHOLDER ============

@app.post("/optimize/2d")
def optimize_2d():
    """2D optimalisatie - nog niet geïmplementeerd via backend"""
    raise HTTPException(
        status_code=501,
        detail="2D optimalisatie via backend is nog in ontwikkeling. "
               "Gebruik de frontend maxrects-packer voor nu."
    )


# ============ /v1 (SuperCloud) ============

import api_v1
api_v1.registreer(health, get_algorithms, optimize_1d, optimize_2d, app)


# ============ RUN SERVER ============

if __name__ == "__main__":
    print("=" * 60)
    print("ZAAGPLAN OPTIMIZER API")
    print("=" * 60)
    print(f"OR-Tools beschikbaar: {ORTOOLS_AVAILABLE}")
    print("Starting server op http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
