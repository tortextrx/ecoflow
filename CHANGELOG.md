# Changelog de ecoFlow

## [2026-03-21] - Fase de Desacoplamiento y Continuidad

### Añadido
* **Desambiguación de Entidades**: Nuevo modo `AWAITING_DISAMBIGUATION` para pedir al usuario seleccionar entre varias entidades cuando la búsqueda por nombre en ERP retorna múltiples candidatos (Ej. "Juan" -> Juan Pérez vs Juan Carlos).
* **ContextVars para Trazabilidad Extremo a Extremo**: Se añadió soporte para telemetría pasiva. El `trace_id` inyectado en `routes_chat.py` o autogenerado se propaga hasta `connectors/base.py` mediante variables de contexto asíncronas (`contextvars`), grabando localmente los inputs y outputs de ERP sin afectar firmas ni funciones del corazón (`tool_registry`).
* **Enrutador Purificado (`orchestrator_routing.py`)**: Para desacoplar el gigantesco switch de `orchestrator.dispatch`, se aisló toda la lógica condicional prioritaria (flujos activos, triggers por PKEY, flujos estáticos) en funciones simples enrutadoras puras.

### Modificado
* **Resolución Multicapa**: `resolver.py` ahora contiene normalización de strings (`lower`, quita de acentos/signos) y prioriza match exacto, luego match parcial (contains), y luego la heurística de comodines original.
* **Calidad de Descripciones de Servicios**: Si un usuario envía mensajes ambiguos ("haz algo", "prueba", "revisar") al dar de alta un servicio, la lógica lo rechaza proactivamente (`_flow_service`) y solicita precisión antes de registrarlo.
* **Confirmación Rica de Servicios**: Antes de mandar a grabar un servicio en ERP, el bot consolida explícitamente y en markdown un resumen del `Cliente` y la `Tarea` para evitar errores fatales.
* **Persistencia de Sesiones**: `chat_service.py` mejoró el manejo en fichero adhiriendo un TTL (Time-To-Live) de 24h a las sesiones. Pasado ese tiempo se resetean y recolectan internamente (GC local). Se añadió mecanismo defensivo a las sesiones para heredar el `last_resolved_entity` a nuevos flujos multi-turno.
