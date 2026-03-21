# Auditoría Técnica y Plan de Producción de ecoFlow

## 1. Arquitectura Actual Real
El sistema presenta una bifurcación arquitectónica (mezcla de "Arquitectura Demo" y "Arquitectura Robusta"):
- **Arquitectura Activa (Demo / Síncrona)**:
  - Frontend webchat -> `app/api/routes_chat.py` -> `chat_service.py` -> `orchestrator.py` -> `connectors`.
  - Esta ruta es rápida, síncrona, y apoya todo el peso computacional verificado hoy (entidades, servicios, gastos y desambiguación).
  - El estado transaccional (sesión) reside en archivos estáticos en `/tmp/` gestionado por `chat_service`.
- **Arquitectura Latente (Robusta / Asíncrona)**:
  - Rutas `app/api/routes_internal.py` (simulador de webhooks) que guardan en DB (`RawMessage`, `Job` con control de IDEMPOTENCIA).
  - Un worker transaccional en background (`main.py` y `process_new.py`) consume esta cola para procesar los mensajes asíncronamente como exige WhatsApp.
  - **Bloqueo de Estado**: Esta ruta estaba rota, pues referenciaba la librería `IntentService` deprecada y a métodos muertos del Orquestador (`.run()`).

## 2. Inventario de Código Muerto y Deuda Técnica
- **Mappers Obsoletos**: Los archivos `app/mappers/articulos_mapper.py` y `app/mappers/servicios_mapper.py` son código zombie. Sus tools correspondientes (`servicios_tools` y `articulos_tools`) están inyectando los payloads manualmente evadiendo la capa de mapping.
- **Desincronización Estructural**: Se configuraron sofisticadas tablas PSQL en `app/models/db/*` (para actores, ids y multi-sesión) que el flujo activo (síncrono) evade por completo, haciendo inútil el ORM en chats en vivo.

## 3. Arquitectura Objetivo Recomendada
La arquitectura definitiva no debe destruir ninguna de las dos. Debe **hibridar** los enfoques integrando la robustez de BD con la agilidad del chat sincronizado:
1.  **Motor Universal Único:** Toda inteligencia de chat y negocio ocurre en `chat_service.py -> orchestrator.dispatch()`. Punto.
2.  **Persistencia Transparente:** `chat_service.py` debe abandonar los JSON de `/tmp/` e integrarse con el modelo `Conversation` y `Operation` en PostgreSQL que ya existe en `app/core/db.py`.
3.  **Omnicanalidad:**
    - El WebChat dispara a la API síncrona de FastAPI, la cual llama a `chat_service.py`.
    - WhatsApp dispara al webhook asíncrono, que introduce en el `JobQueue`. El procesador de cola llama a este mismo `chat_service.py` utilizando como KeySession el ID validado del número de teléfono.

## 4. Checklist Priorizado de Bloqueos (Camino a Producción Real)

### Prioridad 0 (Bloqueantes Críticos de Producción)
- [ ] **Migración de Sesiones a DB Real**: Eliminar el cache/archivo temporal y forzar a `chat_service` a inyectar la tabla `Conversation`. Si ServerIA lanza 2 contenedores de la app, el sistema `/tmp` provocará alucinaciones al enviar cada mensaje a un contenedor con JSON vacíos distintos.
- [ ] **Verificación de Seguridad en Conectores**: Mover los endpoints y tokens dispersos y certificar que la comunicación siempre se rige por un cifrado duro gestionado en un vault o environment inyectable en `config.py`.

### Prioridad 1 (Estabilidad Estructural)
- [ ] **Saneamiento de Mappers vs Tools**: O bien adaptar `servicios_tools` y `articulos` a usar el Mapper, o eliminar de raíz `servicios_mapper` y `articulos_mapper` para que no contamine la vista estructural del código.
- [ ] **E2E del Worker Asíncrono**: Levantar una suite de prueba contra la API de WhatsApp mediante webhook (usando `IdempotencyRecord`) y testear que el Job Queue es capaz de lanzar a `chat_service.py` y resolver un gasto exitosamente en el ERP sin time-outs.

## 5. Quick Wins Ejecutados en esta Fase
- **Purgado de Servicios Fantasma:** Eliminar `app/services/intent_service.py` ya que todo se transacciona vía `cognitive_service.py`.
- **Integridad del Worker:** En `app/process_new.py` y `app/main.py`, se removió la llamada fatídica al `.run()` fantasma. Ahora el loop se orienta en apuntar la conexión en background mediante `res_dict = await chat_svc.handle(...)` que estabiliza el comportamiento.
