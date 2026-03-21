# Decisiones de Diseño de ecoFlow

## Orquestador Conversacional (Orchestrator Pattern)

### Motivación
Se separó la lógica de decisión LLM de la lógica de flujo de negocio para evitar "alucinaciones" durante el proceso de grabación en el ERP. El orquestador mantiene una máquina de estados determinista (idle, confirm, awaiting_data) para garantizar que las transiciones de estado sean seguras.

## Resolver de Capa Superior

### Estrategia de Resolución
La búsqueda en el ERP (`ecoSoftWEB`) requiere PKEYs exactas. Como el usuario habla en lenguaje natural ("Tiger Stores", "el coche de Javier"), el Resolver actúa como un árbitro que traduce nombres a PKEYs usando búsquedas flexibles y preguntando en caso de ambigüedad.

## Mapeo Explícito Cabecera/Detalle

### Integridad de Datos
La API de ecoSoftWEB es estricta con el formato de las facturas (NC=5, NC=6, NC=12, etc). El uso de mappers especializados (`FacturacionMapper`) centraliza la lógica de redondeo, tipo de documento y fechas para desacoplar el chat de las peculiaridades de la API.

### Trazabilidad y Telemetría (ContextVars)
Para realizar debug e inspeccionar post-mortem el estado mutante de los payloads sin contaminar el código de negocio (Mappers/Tools), la trazabilidad en ecoFlow no se pasa por los conectores convencionales (`kwargs`). Se implementa a través de *ContextVars* (`ecoflow_trace_ctx`), lo cual graba silenciosamente en formato JSON el payload íntegro de salida al ERP vinculado al Request ID único del LLM.

### Enrutamiento O-Route (Orchestrator Routing)
El `orchestrator.py` actúa como una máquina de estados pura, derivando la decisión condicional pesada de inferencia a `orchestrator_routing.py`. Esto previene regresiones cuando se añaden nuevos flujos y reduce la carga cognitiva requerida para modificar una ruta crítica.

---

## Limitaciones Actuales y Trabajo Futuro

### Búsqueda de Artículos
Actualmente el sistema está optimizado para **Gasto Genérico** o artículos de catálogo simples. No admite aún el detalle complejo de familias/subfamilias en el chat sin una PKEY previa.

### Persistencia de Sesión Local (Fortalecida por TTL)
La sesión se guarda actualmente en archivos locales estáticos (JSON). Durante la evolución funcional de *Continuity*, se robusteció esta lógica añadiendo un Time-to-Live (TTL) de 24hs con un Garbage Collector silencioso para evitar colapsos semánticos entre días. En una fase posterior se migrará verdaderamente a PostgreSQL.

### Automatización de Contratos
El módulo de contratos está presente en conectores pero no integrado en el flujo conversacional del orquestador principal.
