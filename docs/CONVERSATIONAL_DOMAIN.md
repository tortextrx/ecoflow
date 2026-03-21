# Dominio Conversacional ecoFlow (ERP Domain)

## 1. El Contrato de Intención Unificado (Conversational Contract)

Cada interacción con ecoFlow debe resultar en un objeto de intención estandarizado. Este contrato desacopla el lenguaje natural (LLM) de la ejecución técnica (Connectors).

```json
{
  "intent": "string",           // Acción normalizada (ej: 'CREATE_SERVICE', 'DELETE_ENTITY')
  "module": "string",           // Módulo ERP (ENTIDADES, ARTICULOS, SERVICIOS, FACTURACION, CONTRATOS)
  "operation": "string",        // Operación CRUD+ (CREATE, READ, UPDATE, DELETE, QUERY)
  "entities": {                 // Datos extraídos y resueltos
    "primary_id": "string",     // PKEY o ID principal si existe
    "resolved": {},             // Objetos ya validados en BD/ERP
    "raw": {}                   // Datos pendientes de validación
  },
  "status": {
    "is_complete": boolean,     // ¿Tenemos todos los campos REQUIRED para el ERP?
    "missing_fields": [],       // Lista de campos que faltan (ej: ['CIF', 'DESCRIPCION'])
    "requires_confirm": boolean,// ¿Es una operación sensible?
    "risk_level": "LOW|HIGH"    // Riesgo (HIGH para Delete/Económico)
  }
}
```

## 2. Máquina de Estados (Conversational State Machine)

El Orquestador se rige por un estado determinista en PostgreSQL:

| Estado | Significado | Comportamiento |
| :--- | :--- | :--- |
| `IDLE` | Reposo | Escucha nueva intención. |
| `COLLECTING` | Recolección de Datos | Faltan campos obligatorios. Pregunta por ellos uno a uno. |
| `RESOLVING` | Resolución de Entidades | El nombre es ambiguo. Lanza flujo de desambiguación. |
| `CONFIRMING` | Confirmación del Usuario | Muestra resumen y espera "Sí/No". Obligatorio en `HIGH_RISK`. |
| `EXECUTING` | Ejecución ERP | Llamada síncrona al conector. |

## 3. Clasificación de Riesgos y Seguridad

| Operación | Riesgo | Requisito de Confirmación |
| :--- | :--- | :--- |
| Consultar Dirección | `LOW` | No (Directo) |
| Crear Servicio | `LOW` | Sí (Resumen previo) |
| Registrar Gasto | `HIGH` | Sí (Resumen + Warning) |
| Borrar Entidad/Servicio | `CRITICAL` | Sí (Doble check) |

## 4. Respuesta Consistente (The Response Layout)

Toda respuesta final debe seguir esta estructura visual:
1. **Contexto**: "Entendido, estoy preparando el alta para EcoSoft..."
2. **Resumen/Validación**: (Si falta algo) "¿Cuál es el CIF?" o (Si está listo) "📋 **Resumen**: Cliente X, CIF Y..."
3. **Acción/Resultado**: "✅ Hecho. ID 12345" o "❌ Error: CIF duplicado".
4. **Trazabilidad**: Log interno de `trace_id` y `session_id`.
