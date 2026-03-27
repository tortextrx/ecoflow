# Auditoría técnica ecoFlow + plan de prompts para Antigravity

## 1) Diagnóstico del repositorio

### Arquitectura real actual (no idealizada)

ecoFlow tiene **dos arquitecturas superpuestas** dentro del mismo repo:

1. **Ruta síncrona de chat HTTP/form-data (la que hoy parece operativa para el usuario):**
   `routes_chat -> ChatService -> Orchestrator.dispatch -> CognitiveService -> Resolver -> ToolRegistry -> Connectors ecoSoft`.
   Esta ruta persiste estado en `/tmp/ecoflow_sessions.json` y maneja flujos `entity/service/expense` con `flow_mode` + `state`. (app/api/routes_chat.py, app/services/chat_service.py, app/services/orchestrator.py)

2. **Ruta asíncrona event-driven con DB/jobs (más “nueva”, pero incompleta/incongruente):**
   `routes_internal/simulate -> raw_message + job -> queue -> process_message -> IdentityResolver/IntentService/OpenAIResponsesProvider -> Orchestrator.run`.
   El problema es que el `Orchestrator` actual **no implementa `run` ni recibe `intent_service` en constructor**, pero `main.py` y `process_new.py` lo invocan como si sí. Esto evidencia deriva entre diseño y código activo. (app/main.py, app/process_new.py, app/services/orchestrator.py)

### Flujo principal de conversación y viaje de datos al ERP

- Entrada usuario (texto/archivo): `POST /api/ecoflow/chat` en multipart/form-data. (app/api/routes_chat.py)
- Sesión: se carga/guarda JSON local en `/tmp`, sin control de concurrencia por sesión. (app/services/chat_service.py)
- Detección de intención: LLM vía OpenRouter (`gpt-4o-mini`) con JSON schema blando (prompt textual + `response_format=json_object`). (app/services/cognitive_service.py)
- Orquestación: decisiones por combinación de `intent`, keywords y estado pegajoso de flujo. (app/services/orchestrator.py)
- Resolución entidad: exacto por CIF, exacto por nombre, fallback `%nombre%`; si múltiples, devuelve AMBIGUOUS pero el orquestador no implementa el paso de desambiguación interactiva. (app/services/resolver.py, app/services/orchestrator.py)
- Ejecución ERP: tools -> connectors -> `BaseEcoSoftConnector._post` contra `https://www.ecosoftapi.net`. (app/services/tools/*.py, app/connectors/*.py)
- Trazabilidad actual: payload/respuesta cruda a ficheros globales en `/tmp/ecoflow_trace.json` y `/tmp/ecoflow_response.log` (sobrescribe entre peticiones). (app/connectors/base.py)

### Fortalezas reales

- Flujo de gasto multimodal tiene base útil: extracción OCR/visión, confirmación y grabación de NC=6. (app/services/tools/extraer_documento.py, app/services/tools/registrar_gasto.py, app/mappers/facturacion_mapper.py)
- Resolver prioriza CIF/contexto antes de fuzzy, reduciendo duplicados en casos buenos. (app/services/resolver.py)
- Mappers separados para entidades/facturación/servicios: reduce dependencia directa del prompt conversacional en payload ERP. (app/mappers/*.py)
- Sticky flows en orquestador evitan saltar de intención a mitad de alta/servicio/gasto. (app/services/orchestrator.py)

### Fragilidades y cuellos de botella

1. **Orquestador monolítico y altamente acoplado**
   - Mezcla NLU fallback por keywords, estado, reglas de negocio, construcción de payload y llamadas ERP en un solo archivo.
   - Alto riesgo de regresión transversal al tocar cualquier rama de `dispatch`. (app/services/orchestrator.py)

2. **Incongruencia arquitectónica (ruta DB/jobs vs ruta chat directa)**
   - `main.py`/`process_new.py` usan contrato de `Orchestrator` que ya no coincide.
   - Esto complica mantener continuidad y sugiere código muerto o no verificado. (app/main.py, app/process_new.py, app/services/orchestrator.py)

3. **Persistencia de sesión frágil**
   - Archivo único `/tmp/ecoflow_sessions.json`, sin locking, sin TTL, sin versionado de esquema de sesión.
   - Riesgo de corrupción de sesión con concurrencia o múltiples workers. (app/services/chat_service.py)

4. **Resolución de entidades incompleta para lenguaje natural real**
   - Búsqueda por nombre limitada a exacto y `%...%` literal.
   - No hay normalización robusta ni ranking de candidatos por similitud.
   - Estado `AMBIGUOUS` no cierra loop conversacional hoy. (app/services/resolver.py, app/services/orchestrator.py)

5. **Heurísticas de intención rígidas y potencialmente conflictivas**
   - Reglas `if intent == ... or keyword in texto` que pueden disparar flujos incorrectos.
   - Mezcla de castellano libre + tokenización manual sin capa de confianza/score. (app/services/orchestrator.py)

6. **Observabilidad mínima y no correlacionada por request**
   - Trazas de connector en archivos globales pisables, sin request_id.
   - Dificulta auditoría de regresiones “intermitentes”. (app/connectors/base.py)

7. **Módulo de artículos sensible y no aislado**
   - Defaults de payload y convenciones todavía inestables.
   - Sin suite de pruebas ni contrato conversacional maduro para escalarlo seguro. (app/services/tools/articulos_tools.py, app/mappers/articulos_mapper.py)

### Deuda técnica peligrosa

- Contratos internos rotos (`Orchestrator` viejo/nuevo coexistiendo).
- Ausencia de tests automatizados en repo para flujos críticos.
- Persistencia local de sesión en `/tmp` para lógica de negocio transaccional.
- Multiplicidad de estilos de tools (`BaseTool + ToolResult` vs dict planos), que impide extender sin fugas de complejidad. (app/services/tools/crear_preentidad.py vs app/services/tools/*.py)

### Qué está listo para evolucionar vs qué no

**Listo para evolucionar (iteraciones pequeñas):**
- Resolver de entidades (mejor ranking + desambiguación).
- Orquestador (extracción de piezas en módulos auxiliares sin reescribir todo).
- Manejo de contexto conversacional de sesión (sin tocar aún DB/jobs).
- Validaciones y guardrails de flujos de servicio/gasto.

**No listo para evolución agresiva todavía:**
- Artículos (solo auditoría/guardrails, no ampliación funcional).
- Ruta DB/jobs principal como reemplazo total de chat actual (hay contratos inconsistentes).
- Refactor global de arquitectura.

---

## 2) Prioridades recomendadas (3–6 iteraciones)

1. **Resolver entidades v2 (normalización + ranking + desambiguación real)**
2. **Orquestador: extraer y aislar “router de flujos” sin cambiar behavior crítico**
3. **Contexto conversacional robusto (memoria corta de slots + TTL + limpieza segura)**
4. **Flujo de servicios: endurecer captura/confirmación para mejorar calidad de inserción**
5. **Observabilidad mínima anti-regresión (correlation id + logs estructurados de decisiones)**
6. **Congelar artículos y crear sólo pruebas de no-regresión (sin nuevas features)**

---

## 3) Prompts listos para Antigravity (Gemini 3 Flash)

## Prompt 1 — Resolver entidades v2 (sin tocar artículos)

```markdown
Eres un asistente de implementación estricta. Haz cambios MINIMOS y reversibles.

## Objetivo
Mejorar resolución de entidades por nombre sin romper lo que ya funciona por CIF exacto.

## Archivos que PUEDES tocar
- app/services/resolver.py
- app/services/orchestrator.py
- app/services/tools/buscar_entidad.py (solo si es imprescindible y de forma mínima)

## Archivos que NO puedes tocar
- app/services/tools/articulos_tools.py
- app/mappers/articulos_mapper.py
- app/connectors/articulos.py
- app/main.py
- app/process_new.py
- cualquier archivo fuera de la lista permitida

## Cambios deseados
1. En resolver.py:
   - Mantener prioridad absoluta: context_pk > cif exacto > nombre.
   - Añadir normalización de nombre para comparar (lower, trim, quitar acentos y signos comunes).
   - Implementar estrategia escalonada por nombre:
     a) exacto normalizado
     b) contains normalizado
     c) fallback wildcard actual
   - Devolver un ranking de candidatos cuando haya múltiples, con campos mínimos: pkey, nombre, cif.

2. En orchestrator.py:
   - Cuando resolve_entity devuelva AMBIGUOUS, no fallar silenciosamente.
   - Entrar en estado de desambiguación controlado y pedir al usuario elegir 1..N.
   - Resolver la selección numérica y continuar flujo original sin perder flow_data.
   - NO modificar la lógica de confirmación de entity/service/expense existente salvo lo imprescindible.

## Riesgo de regresión a vigilar
- Alta de entidad (create_entity)
- Creación de servicio (open_task)
- Flujo ticket/factura → gasto
- Resolución por CIF exacto sin duplicar

## Validaciones obligatorias al terminar
- Ejecutar pruebas/manual checks con 6 casos:
  1) CIF exacto existente -> RESOLVED único
  2) Nombre exacto único -> RESOLVED
  3) Nombre parcial con 2+ coincidencias -> pregunta de desambiguación
  4) Selección “2” -> recupera candidato 2
  5) Selección inválida -> vuelve a pedir opción válida
  6) Flujo de gasto con CIF existente -> sigue resolviendo por CIF
- Mostrar diff final limitado a los archivos permitidos.

## Criterio de éxito
- Mejora de resolución por nombre + desambiguación funcional
- Ninguna regresión visible en los 4 flujos estables
- Sin refactor masivo ni cambios de arquitectura
```

## Prompt 2 — Orquestador: desacople quirúrgico del enrutado

```markdown
Implementación quirúrgica. NO hagas rediseño global.

## Objetivo
Reducir acoplamiento del orchestrator separando lógica de enrutado de flujos, manteniendo comportamiento.

## Archivos que PUEDES tocar
- app/services/orchestrator.py
- app/services/orchestrator_routing.py (archivo nuevo permitido)

## Archivos que NO puedes tocar
- app/services/resolver.py
- app/services/cognitive_service.py
- app/services/tools/*
- app/main.py
- app/process_new.py
- módulo artículos completo

## Cambios deseados
1. Crear `orchestrator_routing.py` con funciones puras para:
   - detección de flujo activo
   - detección de intención de lanzamiento de flujo
   - detección de intención de historial por pkey
2. En `orchestrator.py`:
   - reemplazar condicionales grandes de dispatch por llamadas al módulo nuevo.
   - NO cambiar textos de respuesta ni payloads ERP actuales.
3. Mantener API pública del orchestrator exactamente igual (`dispatch`, métodos actuales).

## Riesgo de regresión
- Cambiar orden de prioridad de decisiones de dispatch.

## Validaciones obligatorias
- Ejecutar chequeo de equivalencia con 8 inputs representativos antes/después (mismos replies/state esperados).
- Verificar que no se modificó ninguna tool ni mapper.
- Mostrar lista de funciones movidas y confirmar que no cambió semántica.

## Criterio de éxito
- Menos complejidad en dispatch
- Misma conducta funcional observable en flujos críticos
```

## Prompt 3 — Contexto conversacional robusto (sin migrar a DB)

```markdown
Haz cambios mínimos y seguros. NO migres arquitectura.

## Objetivo
Fortalecer manejo de contexto/sesión para reducir pérdidas de contexto entre turnos sin tocar ecoBot/ecoFast.

## Archivos que PUEDES tocar
- app/services/chat_service.py
- app/services/orchestrator.py

## Archivos que NO puedes tocar
- app/main.py
- app/process_new.py
- app/core/db.py
- app/repositories/*
- app/services/tools/*
- módulo artículos completo

## Cambios deseados
1. En chat_service.py:
   - Añadir metadata por sesión: `updated_at`, `session_version`.
   - Añadir limpieza segura de sesiones antiguas (TTL configurable por constante local, p.ej. 24h).
   - Mantener compatibilidad con sesiones existentes sin esos campos.
2. En orchestrator.py:
   - Estandarizar acceso defensivo a `flow_data` y `last_resolved_entity`.
   - Evitar que `_clear_flow` borre información útil de contexto de entidad resuelta.

## Riesgo de regresión
- Perder estado a mitad de alta/servicio/gasto.

## Validaciones obligatorias
- Caso multi-turno: crear servicio en 3 mensajes separados conservando cliente.
- Caso cancelación: cancelar gasto y empezar nueva tarea sin arrastre de flow_data antiguo.
- Caso reinicio de sesión vencida: estado limpio sin excepciones.

## Criterio de éxito
- Menos pérdidas de contexto
- Sin cambios funcionales en conectores/ERP
- Sin tocar DB ni job queue
```

## Prompt 4 — Servicios: endurecer calidad de inserción sin ampliar alcance

```markdown
Haz mejora puntual de calidad. NO introducir nuevas features grandes.

## Objetivo
Mejorar consistencia de datos en creación de servicio (descripción, cliente, confirmación) sin romper flujo estable.

## Archivos que PUEDES tocar
- app/services/orchestrator.py
- app/mappers/servicios_mapper.py (solo si realmente se usa en el cambio)

## Archivos que NO puedes tocar
- app/services/resolver.py (excepto lectura)
- app/services/tools/servicios_tools.py (no tocar salvo bug crítico)
- app/services/tools/articulos_tools.py
- app/mappers/articulos_mapper.py

## Cambios deseados
1. En flujo `_flow_service`:
   - Validar longitud mínima razonable de `descripcion` antes de confirmar.
   - Si descripción parece ambigua/genérica (“haz algo”, “revisar”), pedir precisión.
   - Confirmación final debe mostrar cliente resuelto + resumen corto del trabajo.
2. NO cambiar payload base ni campos ERP obligatorios actuales.

## Riesgo de regresión
- Romper creación de servicio que hoy sí funciona.

## Validaciones obligatorias
- Servicio con descripción clara -> confirma y crea.
- Servicio con descripción vacía/genérica -> pide aclaración.
- Flujo con cliente ya resuelto previamente -> reutiliza contexto.

## Criterio de éxito
- Mejora en calidad de datos de servicio sin alterar contrato ERP
```

## Prompt 5 — Observabilidad anti-regresión (mínima)

```markdown
Implementación conservadora. Sin refactor de logging global.

## Objetivo
Añadir trazabilidad por request para diagnosticar regresiones de flujo sin tocar arquitectura de fondo.

## Archivos que PUEDES tocar
- app/api/routes_chat.py
- app/services/chat_service.py
- app/services/orchestrator.py
- app/connectors/base.py

## Archivos que NO puedes tocar
- app/main.py
- app/process_new.py
- app/core/logging_config.py
- cualquier módulo de artículos

## Cambios deseados
1. Generar `trace_id` por request chat (si no viene).
2. Propagar `trace_id` por chat_service -> orchestrator -> connectors.
3. Incluir `trace_id` en logs clave:
   - entrada de mensaje
   - intención detectada
   - decisión de flujo
   - llamada ERP endpoint
4. En base connector, evitar sobreescritura ciega de `/tmp/ecoflow_trace.json`:
   - usar archivo por trace_id o append seguro.

## Riesgo de regresión
- Introducir ruido o errores en firmas de métodos usados por flujos críticos.

## Validaciones obligatorias
- Confirmar que una conversación completa entity/service/expense imprime mismo trace_id por request.
- Verificar que endpoints ERP siguen respondiendo igual.
- No modificar payload funcional enviado al ERP.

## Criterio de éxito
- Post-mortem de fallos posible con un trace_id
- Cero cambios de negocio en payloads
```

---

## 4) Advertencias críticas para Antigravity

1. **No tocar aún módulo de artículos para ampliar funcionalidad**: sólo auditoría o pruebas de no-regresión.
2. **No intentar “activar” la arquitectura DB/jobs como reemplazo total** hasta resolver contrato inconsistente de Orchestrator.
3. **No hacer refactors globales de tools/mappers** en un solo cambio; el acoplamiento actual provoca regresiones en cascada.
4. **No alterar prioridad de resolución CIF exacto**: es la barrera principal anti-duplicados.
5. **No romper sticky flows (`flow_mode` + `state`)**: son frágiles pero hoy sostienen la continuidad conversacional.
6. **No mezclar en una iteración mejoras de resolver + servicios + gasto + artículos**: separar por prompts pequeños y validación por casos.

Patrones que históricamente disparan regresión en este repo:
- Cambiar `dispatch` completo de una vez.
- “Limpiar” estados sin preservar contexto útil (`last_resolved_entity`).
- Modificar payloads ERP por “estandarizar” sin pruebas de ida y vuelta.
- Añadir heurísticas de intent sin tests de conflicto entre keywords y estado activo.
