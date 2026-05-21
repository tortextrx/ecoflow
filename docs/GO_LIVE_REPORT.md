# GO_LIVE_REPORT

**Fecha:** 2026-03-22  
**Entorno validado:** serverIA (`ecoflow.service`)  
**Tipo de ronda:** rescate semántico de coherencia conversacional (sin despliegue/go-live).

---

## 1) Objetivo de esta ronda

Cerrar fallos semánticos bloqueantes de la suite E2E en lógica de estados y routing, priorizando:

- cancelación global robusta,
- confirmación de borrado sin pérdida de contexto,
- cierre real de `delete_entity`,
- no cruce de dominios artículo/entidad,
- consistencia multi-turno de artículos,
- coherencia tools/connectors en facturación,
- soporte de PKEY directa,
- modo determinista de test.

---

## 2) Causa raíz y correcciones aplicadas

1. **Cancelación ignorada en flujos activos**
   - **Causa raíz:** override de cancelación no era absoluto en todas las ramas activas.
   - **Corrección:** cancelación global prioritaria en orquestación, con limpieza completa de estado pendiente y retorno a `idle`.

2. **Double-confirm de borrado roto**
   - **Causa raíz:** pérdida prematura de `pending_delete` antes de ejecutar la operación final.
   - **Corrección:** conservación de contexto hasta éxito real o cancelación explícita; no se “olvida” silenciosamente el borrado.

3. **`delete_entity` no cerrado end-to-end**
   - **Causa raíz:** desalineación entre capacidad declarada y ejecución real.
   - **Corrección:** cierre del camino completo (orquestación + tooling/connector efectivo) y validación en regresión.

4. **Cruce de dominios (alta artículo caía en entidad)**
   - **Causa raíz:** reglas genéricas de routing demasiado amplias para “alta”.
   - **Corrección:** routing explícito por dominio e intención, priorizando artículo/contrato/factura y restringiendo entidad a señales claras.

5. **Flujo de artículos incompleto/inestable**
   - **Causa raíz:** activación multi-turno sin cierre robusto en todas las transiciones.
   - **Corrección:** enrutado explícito a flujo activo de artículo con ciclo completo de recoger/confirmar/ejecutar/limpiar.

6. **Facturación inconsistente entre tools y connectors**
   - **Causa raíz:** caminos duplicados desde orquestador y posibles nombres desalineados.
   - **Corrección:** unificación del camino de ejecución y validación de operaciones de query/delete contra métodos reales.

7. **Resolución PKEY insuficiente**
   - **Causa raíz:** exceso de dependencia en nombre comercial en lenguaje natural.
   - **Corrección:** resolución directa de PKEY cruda (p. ej. `12345`, `PKEY 12345`) en dominios relevantes.

8. **Tests contaminados por humanización**
   - **Causa raíz:** assertions expuestas a variabilidad lingüística.
   - **Corrección:** modo determinista (`X-EcoFlow-Test-Mode: raw`, con prioridad sobre env) para validar semántica operativa estable.

---

## 3) Evidencia ejecutada en serverIA

- `tests/run_regression_1_7.py` → **PASS (7/7)**
- `tests/run_regression_8_12.py` → **PASS (7/7)**
- `tests/run_regression_operational_guardrails.py` → **PASS (7/7)**

Ejecución realizada en servidor con intérprete de entorno (`venv/bin/python`) y `PYTHONPATH=/home/ecoflow`.

---

## 4) Archivos impactados

- `app/services/orchestrator.py`
- `app/services/orchestrator_routing.py`
- `app/services/resolver.py`
- `app/services/cognitive_service.py`
- `app/mappers/entidades_mapper.py`
- `app/services/tools/articulos_tools.py`
- `tests/run_regression_1_7.py`
- `tests/run_regression_8_12.py`
- `tests/run_regression_operational_guardrails.py`
- `docs/GO_LIVE_REPORT.md`

---

## 5) Estado y recomendación

**Estado actual:** coherencia semántica restablecida para la ronda de rescate pedida, con regresión objetivo en verde en serverIA.

**Recomendación operativa:**

- **Sí, repetir ya el prompt 6 / suite GO_LIVE_REPORT** en serverIA para certificación formal de cierre.
- **No hay bloqueo funcional crítico activo** en los ejes cubiertos por esta iteración.
- Mantener política de no-go-live hasta completar esa revalidación final documentada.
