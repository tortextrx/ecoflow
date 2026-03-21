# Producción: Seguridad y Endurecimiento Operativo (v4.1.x)

Este documento detalla los controles implementados en la solución **ecoFlow** para garantizar la seguridad operativa y fiabilidad antes del paso final a producción.

## 1. Validación Fuerte de Entrada

**Protección Perimetral (FastAPI Router):**
- **Validación de Tipos y Longitud:** El endpoint ahora restringe el tamaño de *message* a 1000 caracteres como máximo para prevenir ataques DoS de LLM context (evitando colapsos por consumo de tokens).
- **Control de `session_id`:** El identificador de sesión se valida contra patrones alfanuméricos (`^[a-zA-Z0-9_-]+$`) limitados a 100 caracteres, bloqueando posibles inyecciones path o log-forging.
- **Adjuntos Sanitizados (MIME & Tamaño):** Se verifica estrictamente que el `content_type` subido corresponda a las extensiones listadas de forma explícita (`image/jpeg`, `image/png`, `application/pdf`). El tamaño en disco virtual está capado a **10MB** abortando preventivamente para proteger la RAM.

## 2. Seguridad Operacional (Capa Aplicación y ERP)

**Clasificación de Riesgos y "Double-Confirm" estricto:**
- Todas las operaciones destructivas (Eliminar Factura, Servicio, Contrato, Entidad) exigen la fase *Security Check*, forzando al usuario a escribir explícitamente **"CONFIRMO"**.
- El orquestador cuenta con estados trampa (`AWAITING_DELETE_CONFIRM`) que droppean cualquier otra intención que no sea confirmación literal, retornando al punto neutro, protegiendo ante ambigüedades.
- Restricciones en *Módulo de Facturación:* Bloqueo rígido inmutable sobre emisión de facturas finales (`NC=13`) y facturas simplificadas (`NC=20`).

## 3. Observabilidad y Trazabilidad (Logging Estructurado)

**Visibilidad total sin exposición de secretos:**
- **Inyección por ContextVars:** El identificador transaccional único (`trace_id`) fluye desde la API Edge hasta el Connector ERP, uniendo todos los eventos generados (Routing, Intents, Tools, API externa, Humanization) en un solo hilo correlacionable logueado en crudo.
- **Formato Estructurado:** Se eliminó la escritura estéril de logs aislados. Ahora todo el servidor tira eventos con keys nativas (`trace_id`, `layer`, `action`, `session`, `status_code`) garantizando análisis directo con herramientas modernas (e.g. ELK, Datadog).
- **Sanitización Interna:** Al generar las anotaciones que viajan hacia afuera (logs), el conector empaqueta el dict de headers y aplica una sobreescritura `Authorization = ***`, asegurando que el API Auth Token nunca se filtre pasivamente.

## 4. Resiliencia y Manejo de Errores

**Cierre de Puntos Críticos (Single Points of Failure):**
- **Timeouts controlados en ERP (`httpx.TimeoutException`):** El `BaseEcoSoftConnector` levanta advertencias propias separadas que no destrozan el Request. Fallar conectando a ecoSoft se convierte en un objeto validable en la capa Orquestador para devolver al usuario "Sistema temporalmente fuera de línea".
- **Degradación Elegante del LLM:** Si OpenRouter o la red estallan por cuota o latencia excesiva, el `CognitiveService` captura de forma muda el Error/Timeout, forzando un fallback seguro hacia `intent = unknown`. 
- **Layering de Humanización (Response Service):** En el límite, si el Cognitive model de humanización cae, el response_service atrapa el fallo de red, y devuelve silenciosamente el `technical_message` directo, de manera que el usuario *recibe el reporte transaccional de cualquier manera* (no se pierde la certidumbre de lo que ocurrió en el ERP).

## 5. Riesgos Residuales Aceptados

- **Latencia Cognitiva:** Las pausas combinadas entre OCR (si lo hubiera), Inferencia de Intención ERP (vía LLM), Query ERP e Inferencia de Humanización podrían superar 8 segundos. Requerido informar bien al backend que llama (ej: WhatsApp).
- **Errores Semánticos Específicos del LLM:** Una ambigüedad humana extrema no soportada por el sistema que logre engañar al LLM, sin embargo está contenido por las fronteras confirmatorias pre-transacción, bajando la severidad de Riesgo Crítico a Riesgo Bajo de usabilidad.
