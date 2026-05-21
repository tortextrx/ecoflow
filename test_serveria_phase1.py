import os
import json
import httpx
import asyncio
from pydantic import BaseModel
from typing import Optional, List
from rapidfuzz import fuzz

# Cargar API Key (ya extraída del .env)
api_key = "sk-or-v1-43407e30c177f74fe8644ef7c03ba0c91b8e0bd1bdfd95a"

class ExtractionEntities(BaseModel):
    nombre_cliente: Optional[str] = None
    cif: Optional[str] = None
    tipo_entidad: Optional[str] = None
    pkey_factura: Optional[int] = None

class ExtractionResponse(BaseModel):
    intent: str
    entities: ExtractionEntities

async def test_extraction():
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    examples = [
        "Quiero dar de alta un cliente nuevo que se llama Talleres Pepe SL con CIF B12345678",
        "Busca el teléfono de la empresa Flying Tiger",
        "Borra la factura 54321 de mi sistema"
    ]

    print("--- 1. TEST STRUCTURED OUTPUTS (OpenRouter + gpt-4o-mini) ---")
    for text in examples:
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Eres un asistente ERP. Extrae la intención y las entidades exactas."},
                {"role": "user", "content": text}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction",
                    "strict": True,
                    "schema": ExtractionResponse.model_json_schema()
                }
            }
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=12.0)
                resp.raise_for_status()
                data = resp.json()["choices"][0]["message"]["content"]
                print(f"INPUT: {text}")
                print(f"OUTPUT: {data}")
        except Exception as e:
            print(f"ERROR EXTRACTION: {text} -> {e}")

def test_fuzzy():
    print("\n--- 2. TEST RAPIDFUZZ (ServerIA Environment) ---")
    pairs = [
        ("Talleres Manolo", "Taller Manolo", 90),
        ("Flying Tiger Copenhagen", "Flying Tiger", 85),
        ("Construcciones Perez SL", "C. Perez SL", 80)
    ]
    for a, b, min_score in pairs:
        score = fuzz.token_set_ratio(a, b)
        print(f"COMPARE: '{a}' vs '{b}'")
        print(f"SCORE: {score:.2f} (Min esperado: {min_score}) -> {'OK' if score >= min_score else 'FAIL'}")

if __name__ == "__main__":
    test_fuzzy()
    asyncio.run(test_extraction())
