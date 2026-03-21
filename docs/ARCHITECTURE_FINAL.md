# Arquitectura Final y Unificada de ecoFlow

## 1. Topología del Sistema
La arquitectura de **ecoFlow** ha sido rediseñada para converger en un **modelo único síncrono**, apoyado por una persistencia nativa relacional.

El componente central es `chat_service.py`, el cual aloja la lógica de validación e instancia al `Orchestrator` como una subcapa. 
Todas las llamadas viajan de la siguiente manera:
`HTTP POST /api/ecoflow/chat` -> `ChatService.handle()` -> Base de Datos (SQLAlchemy) -> `Orchestrator.dispatch()` -> `ERP Connectors` -> Respuesta final síncrona.

## 2. Persistencia de Estados Sólida (PostgreSQL)
Anteriormente, ecoFlow soportaba su manejo conversacional en un archivo volátil `/tmp/ecoflow_sessions.json`. Esto acarreaba fallos concurrentes e impedía multi-workers o reinicios eficientes del servicio.
**Arquitectura actual**:
- El `ChatService` inyecta en cada petición la identidad a través de `IdentityResolver` basándose en el Header `session_id`.
- SQLAlchemy recupera la iteración del usuario desde la tabla PostgreSQL `Conversations`.
- La columna `session_data` (Tipo `JSONB` robusto y bloqueante) guarda el estado contextual del chat, la intención estática, desambiguaciones activas y valores intermedios (ej: `flow_mode="service"`, `flow_data={...}`).
- Finalizada una transacción LLM o disparo al ERP, se emite un `await conversation_repo.update_session_data(db, ...)` blindando la respuesta ante cortes o concurrencia.

## 3. Trazabilidad
Se impone full observabilidad a todos los niveles de negocio mediante los siguientes vectores inyectados y atados:
- **`trace_id`**: Un valor persistente que viaja desde la petición API (`x-trace-id` o UUID autogenerado) a través del sub-módulo con ContextVar, permitiendo cazar transacciones ERP en logs atadas al request causante inicial.
- **`session_id` (`user_id`)**: Modela el actor responsable garantizando coherencia en `Conversation` y loggeando cada step (ej: "Nueva Peticion session='test'").
- **Trazabilidad DB Cruda**: Todo mensaje de entada emite de forma estática sobre la tabla `RawMessage` logrando historial total por DB de lo que se envia por webhook o frontend, si aplica. (Esta es la capa offline analítica en su caso libre).
- **Control de Logs**: El Orchestrator inyecta la intención real (`intent`), confirmación de ruteos de flujo y ejecuciones hacia las APIs de cliente, sirviendo al sysadmin para validar "qué accionó realmente al bot" detrás de cortinas.

## 4. Elementos Purgados y Código Muerto Removido
- **`app/api/routes_internal.py` y `app/process_new.py`**: El job_queue y procesamiento asíncrono para colas simuladas que usaba arquitecturas paralelizables ya deprecadas (`IntentService`) fue explícitamente barrido de main.py para forzar estabilidad al camino principal que usamos hoy. Si entra tráfico de WA masivo algún día, la respuesta es escalar los workers FastAPI en vez de reinventar una worker queue nativa de Python.
- **Mappers Zombies**: Se borraron `articulos_mapper.py` y `servicios_mapper.py` dejando su validación transaccional cruda que actualmente usan las `tools`.

## 5. Garantía de Calidad
Un script probador interno (`test_persistence.py`) está codificado y desplegable utilizando httpx nativo frente a peticiones super concurrentes forzando ambigüedad entre múltiples sesiones de un mismo actor virtual cruzado con otros para demostrar un 100% de aislamiento en PostgreSQL mitigando el file-lock que ocurría con tmpfs y JSON.
