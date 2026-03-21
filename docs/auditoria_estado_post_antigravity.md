# Auditoría de estado actual (post-cambios Antigravity)

Fecha de revisión: 2026-03-21 (UTC)

## Verificación rápida del estado Git (revisión adicional)

- En el repositorio local revisado, el historial visible es:
  - `d0c6fea (HEAD -> work) docs: agregar auditoría Antigravity y estado post-cambios`
  - `2b792bf Initial commit - ecoFlow core system`
- **No aparece** el commit reportado `8ab1ef4` en esta copia local.
- Por tanto, en este entorno no hay evidencia de que se hayan aplicado/publicado cambios funcionales recientes en `app/services/resolver.py`.

## 1) Qué ha cambiado realmente

Comparando el estado actual contra el commit base del repositorio (`2b792bf`), los cambios reales introducidos son exclusivamente documentales:

- **Archivos nuevos:** `docs/auditoria_antigravity.md` y `docs/auditoria_estado_post_antigravity.md`.
- **No hay cambios en código ejecutable** de `app/`.

Conclusión: no se han modificado rutas, servicios, conectores, mappers ni lógica de negocio del asistente.

## 2) Si los cambios tienen sentido o hay chapuzas / riesgos claros

### Lo que sí tiene sentido
- El documento añade un marco de trabajo por iteraciones pequeñas y prompts acotados.
- Sirve como guía de gobernanza para reducir regresiones por cambios ambiguos.

### Riesgos / chapuzas detectables en el estado real (previos y aún vigentes)
1. **Deriva arquitectónica no resuelta**: `main.py` y `process_new.py` instancian `Orchestrator(intent_service=...)`, pero el `Orchestrator` activo sólo expone `dispatch(...)` y no constructor/`run` acorde a ese contrato.
2. **Sesión frágil por archivo global en `/tmp`** sin locking ni control de concurrencia.
3. **Trazas de ERP en archivos globales sobrescritos** (`/tmp/ecoflow_trace.json`, `/tmp/ecoflow_response.log`), dificultando auditoría concurrente.
4. **Riesgo de falsa sensación de avance**: al no haber cambios en `app/`, no hay mejora funcional real todavía.
5. **Desajuste entre narrativa y estado git local**: se reporta un push con cambios de `resolver.py`, pero en esta copia local `resolver.py` mantiene la implementación previa (sin estado `AWAITING_DISAMBIGUATION` en orquestador ni nuevo contrato de selección persistente).

## 3) Qué partes del sistema se han tocado

- Sólo documentación en `docs/`.
- Partes NO tocadas: API chat/interna, orquestador, resolver, tools, conectores, mappers, persistencia, job queue.

## 4) Qué puede haberse roto o quedado frágil

### Roto por este cambio
- Nada funcionalmente (el cambio fue sólo docs).

### Frágil que sigue igual
- Contrato inconsistente entre ruta DB/jobs y clase `Orchestrator` real.
- Estado conversacional en `/tmp` expuesto a condiciones de carrera.
- Observabilidad baja por sobrescritura de trazas.
- Acoplamiento alto en `orchestrator.dispatch` para futuras iteraciones.

## 5) Siguiente paso lógico recomendado

Aplicar una primera iteración **de bajo impacto** centrada sólo en:
- resolución de entidades por nombre + desambiguación controlada,
- manteniendo intactos los flujos estables de alta, servicio e ingreso de gasto,
- y validando exclusivamente en `serverIA`.

---

## Prompt siguiente para Antigravity (seguro y acotado)

```markdown
Eres Gemini 3 Flash trabajando en ecoFlow. Implementa SOLO la iteración descrita, sin creatividad extra.

## Objetivo único
Mejorar resolución por nombre de entidades y cerrar el loop de desambiguación en conversación, sin romper flujos estables.

## Restricciones duras
1. NO tocar ecoBot ni ecoFast (ni despliegues, ni configuración, ni código externo a ecoFlow).
2. NO tocar artículos (tools/mappers/connectors de artículos), salvo que exista bloqueo técnico demostrable.
3. NO hacer refactor global ni rediseño arquitectónico.
4. Cualquier validación/prueba debe ejecutarse SIEMPRE en `serverIA` (nunca en local).

## Archivos permitidos
- app/services/resolver.py
- app/services/orchestrator.py

## Archivos prohibidos
- app/services/tools/articulos_tools.py
- app/mappers/articulos_mapper.py
- app/connectors/articulos.py
- app/main.py
- app/process_new.py
- cualquier archivo de ecoBot o ecoFast

## Cambios requeridos
1. En `resolver.py`:
   - Mantener prioridad exacta: `context_pk > cif exacto > nombre`.
   - Mejorar búsqueda por nombre con normalización (minúsculas + trim + sin acentos).
   - Cuando haya múltiples candidatos, devolver estructura `AMBIGUOUS` con lista acotada y campos mínimos (`pkey`, `nombre`, `cif`).

2. En `orchestrator.py`:
   - Si `resolve_entity` devuelve `AMBIGUOUS`, entrar en estado explícito de desambiguación.
   - Mostrar opciones numeradas y aceptar respuesta numérica del usuario.
   - Al elegir opción válida, continuar el flujo original sin perder `flow_data`.
   - En opción inválida, volver a pedir selección sin resetear el flujo.

## No debes cambiar
- Payloads ERP de creación de entidad/servicio/gasto.
- Lógica del flujo multimodal ticket/factura -> gasto salvo efectos colaterales inevitables.
- Integraciones de ecoBot y ecoFast.

## Validación obligatoria (SOLO en serverIA)
Ejecuta y documenta en serverIA estos casos:
1. CIF exacto existente -> resolución única.
2. Nombre exacto único -> resolución única.
3. Nombre parcial con múltiples resultados -> pregunta de desambiguación.
4. Selección numérica válida -> continúa flujo correctamente.
5. Selección inválida -> repregunta sin romper estado.
6. Flujo de gasto con CIF existente -> comportamiento previo intacto.
7. Flujo de alta de entidad e inserción de servicio -> sin regresión.

## Evidencia obligatoria de cierre
- Lista exacta de archivos modificados.
- Diff resumido por archivo.
- Resultado de cada prueba en serverIA (PASS/FAIL con breve evidencia).
- Si algún test falla, NO ampliar alcance: reportar causa y detener.
```
