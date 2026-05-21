import os
import json
import httpx
import asyncio
from pydantic import BaseModel
from typing import Optional, List

# Configurar API Key local
api_key = os.getenv("OPENAI_API_KEY")

class ExtractionEntities(BaseModel):
    nombre_cliente: Optional[str] = None
    cif: Optional[str] = None
    tipo_entidad: Optional[str] = None

class ExtractionResponse(BaseModel):
    intent: str
    entities: ExtractionEntities

async def test_extraction():
    if not api_key:
        print("ERROR: No OPENAI_API_KEY found in environment.")
        return

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    examples = [
        "Quiero dar de alta un cliente nuevo que se llama Talleres Pepe SL con CIF B12345678",
        "Busca el teléfono de la empresa Flying Tiger",
        "Borra la factura 54321 de mi sistema"
    ]

    print("--- PRUEBA DE EXTRACCIÓN ESTRUCTURADA ---")
    
    for text in examples:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Eres un asistente ERP. Extrae la intención y las entidades."},
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
                print(f"\nINPUT: {text}")
                print(f"OUTPUT: {data}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_extraction())
