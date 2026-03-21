import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("ecoflow")

class IntentAction(BaseModel):
    """Contrato Conversacional Unificado para operaciones ERP."""
    intent: str                  # Ej: 'CREATE', 'QUERY', 'DELETE', 'UPDATE'
    module: str                  # Ej: 'ENTIDADES', 'SERVICIOS', 'FACTURACION', 'ARTICULOS'
    operation: str               # Sub-operación o nombre de la tool
    entities: Dict[str, Any]      # Datos extraídos/resueltos (ej: pkey_entidad)
    fields: Dict[str, Any]        # Campos de datos para el ERP (ej: descripcion)
    
    # Control de Estado
    is_complete: bool = False
    missing_fields: List[str] = []
    requires_confirm: bool = False
    risk_level: str = "LOW"      # LOW, HIGH, CRITICAL
    
    # UI Metadata
    summary: str = ""            # Resumen legible para el usuario

class StateMachine:
    """Máquina de Estados Conversacional."""
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"    # Faltan datos obligatorios
    RESOLVING = "RESOLVING"      # Ambigüedad en entidades (nombres)
    CONFIRMING = "CONFIRMING"    # Esperando confirmación explícita
    EXECUTING = "EXECUTING"      # Llamada al conector
    
    @staticmethod
    def get_risk(module: str, intent: str) -> str:
        if intent in ["DELETE", "BORRAR"]: return "CRITICAL"
        if module == "FACTURACION" and intent == "CREATE": return "HIGH"
        return "LOW"

    @staticmethod
    def needs_confirmation(risk_level: str) -> bool:
        return risk_level in ["HIGH", "CRITICAL"]
