# Auditoría forense de regresión funcional — ecoFlow

Fecha: 2026-03-27
Ámbito: reproducción real en serverIA, sin usar local como fuente de verdad

---

## 1. Resumen ejecutivo

El sistema **sí ha ido a peor** en un sentido muy concreto: hoy responde con más frecuencia de forma **plausible pero incorrecta**, mezcla rutas, rellena huecos con narrativa, y en varios dominios deja que el LLM o la humanización “maquillen” fallos estructurales del core.

La degradación no viene de una sola causa. Viene de una combinación de 4 factores:

1. **Arquitectura demasiado llm-first** en consultas que deberían ser deterministas.
2. **Fallbacks demasiado permisivos** que convierten errores de routing/resolver/API en respuestas “bonitas”.
3. **Expansión funcional mal gobernada** tras añadir artículos, contratos y facturación al mismo orquestador.
4. **Acoplamiento débil entre capacidad declarada y capacidad real del ERP**, especialmente en artículos.

Conclusión dura pero honesta: hoy ecoFlow está más cerca de un **bot conversacional que improvisa** que de un **ChatGPT conectado al ERP con gobernanza alta**.

Para preproducción solvente, mi recomendación es **endurecer ya** los tramos problemáticos y aceptar menos “magia” a cambio de mucha más fiabilidad.

---

## 2. Evidencia reproducida en serverIA

Los casos se reprodujeron en serverIA enviando exactamente los textos facilitados por producto, usando sesiones separadas y `trace_id` explícito por turno.

Casos ejecutados:

- A1 — Entidades / teléfono de Cristian
- B1 — Artículos / tornillo
- C1 — Servicios / operario Javier Play

Fuente principal de traza:

- respuestas reales del endpoint interno `http://127.0.0.1:18080/api/ecoflow/chat`
- `journalctl -u ecoflow` en serverIA

---

## 3. Cadena forense por caso

## Caso A1 — Entidades / teléfono de Cristian

### Síntoma observado

- Arranca bien.
- Entra en una ruta de alta/confirmación de entidad cuando el usuario en realidad quería consulta/listado.
- Recupera el dato en un turno posterior.
- Después descarrila y acaba devolviendo una entidad irrelevante (`COMUNIDAD CERVANTES 70`).

### Cadena real

#### Turno 1
Input: “Necesito el teléfono de un cliente”

- Respuesta: pide cliente.
- Estado final: `ENTITY_CONTEXT`.

Diagnóstico:
- Comportamiento razonable.

#### Turno 2
Input: “El cliente se llama Cristian”

Traza real:
- LLM: `intent=create_entity`, entities=`nombre_cliente`, `tipo_entidad`
- Estado previo: `ENTITY_CONTEXT`
- Routing: entra por flujo de entidad
- Resolver: llama a `ObtenerEntidades` con `%Cristian%`
- API devuelve varias coincidencias relevantes (al menos `CRISTIAN`, `Cristian Sánchez`, `Cristian ecoSoft`)
- Respuesta al usuario: coincidencia única o semidesambiguación mal orientada
- Estado final: `AWAITING_ENTITY_CONFIRM`

Punto de ruptura:
- **llm_intent_drift**: el LLM clasifica una consulta contextual como `create_entity`.
- **wrong_flow_routing**: el sistema cae en [_flow_entity()](app/services/orchestrator.py:270) en vez de tratarlo como búsqueda/listado o consulta de campo.

#### Turno 3
Input: “Quiero el teléfono de Cristian”

Traza real:
- LLM: `intent=consultar_campo`, entities=`campo`
- Estado previo: `AWAITING_ENTITY_CONFIRM`
- Se mantiene dentro del flujo de alta/confirmación, no en una rama de consulta pura.
- Respuesta sigue en tono de selección/alta.

Punto de ruptura:
- **pending_field_consumption_fail** / **legacy_path_regression**:
  el estado `AWAITING_ENTITY_CONFIRM` secuestra un turno que ya es una consulta legítima.

#### Turno 4
Input: texto largo pidiendo listado de todos los Cristian

Traza real:
- LLM: `intent=query_entity`, `nombre_cliente`
- Resolver vuelve a consultar `%cristian%`
- ERP devuelve candidatos correctos
- Respuesta final: “ya he encontrado a CRISTIAN... ID 66 ... ¿continuamos con este?”
- Estado final: `idle`

Punto de ruptura:
- **resolver_miss parcial + api_result_ignored parcial + fallback_hallucinated parcial**
- El sistema tenía suficientes candidatos para listar opciones, pero colapsa la respuesta a una sola coincidencia y abandona el estado de desambiguación.

#### Turno 5
Input: “Como va la cosa?”

- LLM: `unknown`
- Routing: [Fallback general](app/services/orchestrator.py:264)
- Respuesta genérica

Punto de ruptura:
- Aquí no hay fallo grave: es un turno meta.

#### Turno 6
Input: “El teléfono de Cristian ecoSoft”

Traza real:
- LLM: `consultar_campo`, entities=`campo`
- Routing: consulta de campo de entidad
- Resolver: `%cristian ecosoft%`
- API: devuelve coincidencia correcta
- `ObtenerEntidad` se ejecuta correctamente
- Respuesta final: teléfono correcto `985980890`

Diagnóstico:
- La cadena completa funciona cuando el shape de consulta llega limpio.

#### Turno 7
Input: reproche del usuario diciendo que había varios Cristian

Traza real:
- LLM: `unknown`
- Estado previo: `ENTITY_CONTEXT`
- Continuidad de contexto en entidad intenta extraer un hint de nombre desde el texto completo
- [_extract_entity_name_hint_from_field_query()](app/services/orchestrator.py:2365) deja sobrevivir tokens irrelevantes
- Resolver intenta buscar por una frase absurda completa; al fallar, hace fallback por primera palabra (`antes`)
- Resolver encuentra `COMUNIDAD CERVANTES 70`
- Respuesta final se construye sobre esa coincidencia basura

Punto de ruptura exacto:
- **resolver_overpermissive** + **fallback_hallucinated** + **context_contamination**

La función [resolve_entity()](app/services/resolver.py:128) hace un fallback peligrosísimo por la primera palabra cuando la búsqueda original no encuentra nada. Eso, combinado con la extracción de nombre demasiado laxa en [orchestrator.py](app/services/orchestrator.py:2365), contamina el contexto y lleva a una entidad que nada tiene que ver.

#### Turno 8
Input: “Ese no es cristian”

- LLM: `unknown`
- Estado: `idle`
- Routing: [Fallback general](app/services/orchestrator.py:264)
- Respuesta: genérica

Punto de ruptura:
- **state_not_persisted semánticamente** / **wrong_flow_routing**
- No se conserva una desambiguación activa. El sistema debería seguir en selección, no caer a `idle`.

### Clasificación principal del caso A1

- `llm_intent_drift`
- `wrong_flow_routing`
- `resolver_overpermissive`
- `fallback_hallucinated`
- `context_contamination`

### Causa raíz dominante

El sistema usa demasiado pronto el flujo de alta de entidad y demasiado tarde una estrategia determinista de listado/selección. Cuando la conversación se vuelve discursiva, el resolver acaba buscando basura textual y el fallback le da apariencia de respuesta válida.

---

## Caso B1 — Artículos / tornillo

### Síntoma observado

- No encuentra artículos que “aparentemente existen”.
- No lista opciones.
- Acaba empujando al usuario a alta guiada.
- El proveedor tampoco se resuelve bien.

### Hallazgo clave

Aquí hay un problema objetivo y muy grave de capacidad real del backend:

En la traza del ERP, `/API_Articulos/ObtenerArticulos` devuelve:

> `No se encontró el procedimiento almacenado 'dbo.ARTICULOS_F_API'`

Es decir: la capacidad declarada como soportada en [docs/FUNCTIONAL_CAPABILITIES.md](docs/FUNCTIONAL_CAPABILITIES.md:33) no está realmente operativa en serverIA para consulta/listado de artículos.

### Cadena real

#### Turnos 1-4
Inputs de consulta: PKEY, listado por prefijo, código, ID concreto.

Traza real repetida:
- LLM: `query_article`
- Routing: [_handle_query_article()](app/services/orchestrator.py:1773)
- Tool ejecutada: [ListarArticulosTool.execute()](app/services/tools/articulos_tools.py:18)
- Connector: [obtener_articulos()](app/connectors/articulos.py:22)
- ERP responde `ERROR` por procedimiento inexistente
- Tool traduce esto a `found=False` y la capa superior lo convierte en “no encuentro artículos...”

Punto de ruptura exacto:
- **unsupported_query_shape** y más aún **backend capability missing**
- También **api_result_ignored** en el sentido de que el error del ERP se degrada a “no hay resultados”, ocultando que no fue una consulta válida sino un fallo estructural de backend.

#### Turno 5
Input: “Hay algun artículo dado de alta en la base de datos?”

- LLM: `unknown`
- En vez de listar artículos, el sistema entra en flujo guiado de alta y pregunta descripción.

Punto de ruptura:
- **wrong_flow_routing** + **unsupported_query_shape**
- No existe una ruta robusta para listado global de artículos.

#### Turnos 6-9
Inputs: “tornillo del 10”, familia, proveedor, proveedor existe...

Traza real:
- Estado previo: `AWAITING_ARTICULO_COLLECT`
- El sistema interpreta todo como continuación de alta
- [detect_active_flow()](app/services/orchestrator_routing.py:4) prioriza `pending_field + flow_mode`
- El flujo [_flow_article()](app/services/orchestrator.py:1077) recomienda completar familia/proveedor antes de crear
- El proveedor se intenta resolver por entidad, pero sin éxito
- Mensajes como “el proveedor existe...” se vuelven pseudo-confirmaciones dentro del alta

Punto de ruptura:
- **wrong_flow_routing**: una vez abierto el flujo de alta, casi todo queda absorbido por él.
- **pending_field_consumption_fail**: el flujo no distingue entre datos de alta y una rectificación/consulta del usuario.
- **api_result_ignored**: el error real del ERP en la búsqueda inicial no se expone, por lo que el sistema cambia de misión sin decírselo al usuario.

### Clasificación principal del caso B1

- `unsupported_query_shape`
- `api_result_ignored`
- `wrong_flow_routing`
- `pending_field_consumption_fail`

### Causa raíz dominante

El dominio artículos está roto en consulta real porque la API/listado no funciona en backend, y el sistema, en vez de declararlo, se desliza hacia alta guiada. Eso genera la sensación de “el bot improvisa”, y con razón.

---

## Caso C1 — Servicios / listado por operario

### Síntoma observado

- El usuario pregunta por servicios asignados a un operario.
- El sistema insiste en pedir cliente.
- Mezcla operario y cliente.
- Acaba cancelando sin sentido.

### Cadena real

#### Turno 1
Input: “Dime los servicios o tareas asignadas al operario Javier Play”

Traza real:
- LLM: `unknown`
- Entra al dominio servicio
- [SERVICE_TRACE] registra `missing client -> ask_client`
- `flow_data={'operario_name': 'Javier Play'}`
- Respuesta: “¿Para qué cliente es el servicio?”

Punto de ruptura exacto:
- **wrong_flow_routing**
- El flujo de servicio en [orchestrator.py](app/services/orchestrator.py:522) está diseñado como “crear servicio para un cliente” y exige cliente antes de cualquier otra cosa.

#### Turno 2
Input: misma idea reformulada

- LLM: `query_history`, entities=`operario`
- Aun así el flujo vuelve a `missing client -> ask_client`

Punto de ruptura:
- **wrong_domain_selected** / **unsupported_query_shape**
- No existe soporte real para “listado de servicios por operario”, y el orquestador no sabe decirlo; reusa el flujo de creación.

#### Turno 3
Input: “Cristian ecoSoft”

- LLM: `confirm`
- El sistema lo humaniza como “Hola Cristian...”
- Pero internamente sigue faltando cliente y mantiene el mismo bucle

Punto de ruptura:
- **llm_intent_drift** + **pending_field_consumption_fail**
- La entrada del usuario se interpreta como confirmación, no como cliente candidato resoluble.

#### Turno 4
Input: “Para Javier Play”

- LLM: `confirm`, entities=`operario`
- Respuesta final: cancelación — “no hacer ningún cambio”

Punto de ruptura exacto:
- **wrong_flow_routing** + **fallback_hallucinated**
- El sistema cae en una semántica de cancelación/no-op totalmente ajena al objetivo del usuario.

### Clasificación principal del caso C1

- `unsupported_query_shape`
- `wrong_flow_routing`
- `llm_intent_drift`
- `pending_field_consumption_fail`

### Causa raíz dominante

El dominio servicios no implementa de verdad la consulta pedida. El sistema fuerza el molde “servicio = creación ligada a cliente”, y el LLM/humanización rellenan el resto con lenguaje plausible.

---

## 4. Tabla de causas raíz agrupadas

| Causa raíz | Casos que explica | Dominios | Severidad | Prioridad |
|---|---:|---|---|---|
| Routing forzado a flujos de creación/colección cuando el usuario quiere consultar/listar | 3/3 | entidades, artículos, servicios | crítica | P0 |
| Fallback/humanización convierten errores reales en respuestas plausibles | 3/3 | entidades, artículos, servicios | crítica | P0 |
| Soporte backend real no alineado con capacidades declaradas | 1/3 de forma total, 2/3 parcial | artículos principalmente | crítica | P0 |
| Uso excesivo del LLM para clasificar consultas triviales/contextuales | 2/3 fuerte, 3/3 parcial | entidades, servicios, artículos | alta | P1 |
| Resolver con fallback demasiado permisivo por primera palabra | 1/3 muy fuerte, 2/3 parcial | entidades | alta | P1 |
| Estado conversacional secuestra turnos posteriores y no sabe rectificar | 3/3 | entidades, artículos, servicios | alta | P1 |
| Orquestador unificado demasiado complejo para gobernar dominios heterogéneos | 3/3 | global | alta | P1 |

---

## 5. ¿Por qué ahora va peor que antes?

La revisión de cambios muestra este patrón:

- base inicial simple: `2b792bf`
- persistencia y routing más complejos: `e433dca`
- endurecimiento puntual + telemetría + resolver: `e65d30f`, `e077f37`, `8ab1ef4`
- gran salto de arquitectura unificada: `49f1d2e`
- expansión funcional ERP v4.0 (contratos, artículos, facturación): `6e1ed7a`

Mi lectura:

### Punto aproximado de inflexión
El deterioro fuerte probablemente empieza entre:

- [49f1d2e](app/services/orchestrator.py:1) — unificación del state machine
- [6e1ed7a](app/services/orchestrator.py:1) — expansión funcional v4.0

### Por qué
Antes el sistema tenía menos dominios, menos cruces y menos ambición. Ahora:

1. Un solo [UnifiedOrchestrator](app/services/orchestrator.py:72) decide demasiadas cosas.
2. [detect_new_flow()](app/services/orchestrator_routing.py:55) y [detect_active_flow()](app/services/orchestrator_routing.py:4) absorben mensajes con heurísticas globales.
3. El LLM clasifica sobre un catálogo muy amplio en [cognitive_service.py](app/services/cognitive_service.py:52).
4. La humanización en [ChatService.handle()](app/services/chat_service.py:57) embellece respuestas aunque el core haya tomado una ruta incorrecta.

Resultado: el sistema parece más listo, pero en realidad está **menos gobernado**.

---

## 6. Juicio honesto sobre el stack actual

## ¿Estamos pasando demasiado pronto por el LLM?
Sí.

Se está usando el LLM para decidir cosas que deberían ser deterministas o híbridas con guardarraíl duro:

- consulta de campo con nombre parcial
- listado vs alta
- consulta por operario
- respuesta correctiva del usuario (“ese no es”, “hay varios”, “existe”) 

## ¿Estamos usando el LLM para cosas que deberían ser deterministas?
Sí, claramente.

Especialmente:

- detección de listados
- follow-ups de corrección
- rectificaciones de desambiguación
- selección del shape de consulta de servicio/artículo

## ¿El resolver ha quedado peor integrado que antes?
Sí.

No porque el fuzzy sea malo en sí, sino porque su fallback textual es demasiado agresivo y se invoca desde entradas discursivas que no deberían llegar a él limpias.

## ¿La arquitectura actual favorece respuestas plausibles pero malas?
Sí.

La combinación de:

- clasificación LLM amplia,
- orquestador enorme,
- fallback general,
- humanización final,

favorece exactamente ese patrón: **respuesta convincente, pero mal anclada al ERP**.

---

## 7. Plan de corrección

## Nivel A — correcciones mínimas de alto impacto

### A1. Cortar fallbacks peligrosos del resolver

En [resolve_entity()](app/services/resolver.py:128), eliminar o endurecer muchísimo el fallback por primera palabra cuando la búsqueda completa falla.

Qué gana:
- evita casos basura como `antes -> COMUNIDAD CERVANTES 70`
- reduce respuestas alucinadas con apariencia de ERP real

### A2. Separar de forma estricta “consulta/listado” de “alta”

Antes de abrir flujo de alta, meter una capa determinista de intención operativa:

- si pide teléfono/email/dirección → consulta de campo
- si pide “dime los”, “lista”, “busca todos” → listado
- si pide por operario → consulta/listado, nunca creación

Qué gana:
- ataca A1, B1 y C1 a la vez

### A3. No maquillar errores de backend como “no hay resultados”

En artículos, cuando la API devuelva error de procedimiento inexistente, responder error gobernado del sistema, no “no encuentro artículos”.

Qué gana:
- separa fallo de backend de fallo de datos
- deja de confundir al usuario y al equipo

### A4. Desactivar humanización en respuestas de error/routing incierto

Si el core cae en fallback general o detecta error de conector, no pasar por un rewriter que suavice o reinterprete.

Qué gana:
- más observabilidad real
- menos sensación de “loro bonito”

### A5. Introducir guardarraíl de shape soportado por dominio

Si un shape no está soportado (“listar servicios por operario”, “listar artículos si backend no soporta query”), decirlo explícitamente y no redirigir a alta.

Qué gana:
- honestidad operativa
- evita bucles absurdos

---

## Nivel B — simplificación / endurecimiento para preproducción

### B1. Endurecer entidades
- consultas de campo y listados por nombre parcial deben ser deterministic-first
- desambiguación obligatoria cuando haya >1 candidato relevante
- nunca resolver texto discursivo libre como nombre sin filtro fuerte

### B2. Endurecer artículos
- si consulta backend real no funciona, sacar el dominio de “fiable” en preproducción
- o limitarlo a PKEY / referencia exacta / lectura directa verificada
- no permitir transición silenciosa de consulta a alta

### B3. Endurecer servicios
- separar creación de servicio y consulta/listado
- no reutilizar el flujo de creación para preguntas por operario
- si el ERP no soporta bien “por operario”, declararlo como shape no soportado o implementarlo de forma específica

### B4. Reducir superficie llm-first
- usar LLM para entender lenguaje natural abierto
- pero no para decidir rutas críticas cuando hay heurísticas deterministas claras

### B5. Hacer visible el motivo real del fallo
- `backend_error`
- `unsupported_query_shape`
- `ambiguous_selection_required`
- `resolver_low_confidence`

Eso acerca el sistema a un asistente serio y lo aleja del bot improvisador.

---

## 8. Recomendación de producto final

### Pregunta
> Para llevar ecoFlow a preproducción cuanto antes, ¿debemos seguir empujando hacia un comportamiento tipo ChatGPT o conviene endurecer ya parte del sistema y aceptar un comportamiento más bot pero mucho más fiable?

### Mi respuesta
**Conviene endurecer ya.**

No recomiendo seguir empujando en modo “más ChatGPT” sobre la base actual.

La razón es simple:

- cuando acierta, parece brillante
- cuando falla, falla de una forma muy peligrosa: convincente, pero incorrecta

Para preproducción, eso es peor que un bot más seco pero fiable.

### Recomendación concreta

Ir a un modelo híbrido mucho más disciplinado:

- **LLM para entender reformulaciones y lenguaje natural abierto**
- **routing determinista para consultas/listados de alto riesgo semántico**
- **resolver con umbrales duros y sin fallback textual loco**
- **errores explícitos cuando backend/capacidad no soporta la consulta**

### Traducción operativa

No intentar vender ahora una UX de “ChatGPT conectado al ERP” en todos los dominios.

Para llegar a preproducción solvente antes:

1. endurecer entidades,
2. acotar servicios a shapes realmente soportados,
3. rebajar artículos a soporte honesto o corregir su backend primero,
4. eliminar respuestas plausibles no verificadas.

Ese camino sacrifica algo de magia conversacional, pero recupera lo más importante:

**fiabilidad, trazabilidad y confianza real del usuario.**

---

## 9. Veredicto final

Qué está pasando, en bruto:

> ecoFlow ha crecido más rápido en complejidad conversacional que en gobernanza determinista.
> El LLM, el orquestador unificado y la humanización están tapando demasiado bien fallos de routing, resolver y capacidad real del ERP.
> El resultado no es un asistente conectado con fiabilidad alta, sino un sistema que a menudo parece saber más de lo que realmente sabe.

Mi criterio técnico:

> **Sí: hay que reconducirlo hacia algo más determinista en los tramos problemáticos ya, antes de seguir ampliando comportamiento “tipo ChatGPT”.**

