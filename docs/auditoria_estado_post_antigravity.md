# Auditoría de estado actual (post-cambios Antigravity)

Fecha de revisión: 2026-03-21 (UTC)

## Verificación rápida del estado Git (revisión adicional)

- En este entorno local de auditoría, el historial visible es:
  - `9066c81 (HEAD -> work) docs: add git-state verification and sync discrepancy note`
  - `d0c6fea docs: agregar auditoría Antigravity y estado post-cambios`
  - `2b792bf Initial commit - ecoFlow core system`
- En esta copia local **no existe remoto `origin` configurado**, por lo que no se puede contrastar directamente contra GitHub desde aquí.
- Evidencia aportada por consola de `serverIA/Windows` indica que en `main` remoto sí aparecen commits funcionales posteriores, incluido `8ab1ef4` y una secuencia previa (`e433dca`, `e65d30f`, `e077f37`, `95271de`).
- Conclusión operativa: hay una **divergencia de contexto** entre esta copia local de auditoría y el estado reportado en `origin/main`.

## 1) Qué ha cambiado realmente

Comparando el estado **de esta copia local** contra el commit base (`2b792bf`), los cambios reales introducidos son exclusivamente documentales:

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
4. **Riesgo de falsa sensación de avance en esta copia local**: aquí no hay cambios en `app/`.
5. **Riesgo de trazabilidad cruzada**: si se audita una copia local desalineada del remoto, se pueden sacar conclusiones incorrectas del estado real de producción.

## 3) Qué partes del sistema se han tocado

- En esta copia local: sólo documentación en `docs/`.
- Según evidencia de consola aportada por usuario en `main`: sí se tocaron `app/services/resolver.py` y varios documentos raíz (`ARTICULOS.md`, `CONTRATOS.md`, `ECOFLOW_CONTEXT.md`, `ENTIDADES.md`, `FACTURACION.md`, `SERVERIA_DEPLOYMENT_POLICY.md`, `SERVICIOS.md`).

## 4) Qué puede haberse roto o quedado frágil

### Roto por este cambio
- Nada funcionalmente (el cambio fue sólo docs).

### Frágil que sigue igual
- Contrato inconsistente entre ruta DB/jobs y clase `Orchestrator` real.
- Estado conversacional en `/tmp` expuesto a condiciones de carrera.
- Observabilidad baja por sobrescritura de trazas.
- Acoplamiento alto en `orchestrator.dispatch` para futuras iteraciones.

## 5) Siguiente paso lógico recomendado

Antes de nueva iteración funcional, hacer **conciliación de baseline**:
- auditar directamente el árbol de `main` en `serverIA` (commit `8ab1ef4` y anteriores),
- generar diff técnico real de `resolver.py` y del impacto en flujos,
- sólo después lanzar una iteración de bajo impacto (desambiguación + no regresión),
- con validación exclusivamente en `serverIA`.

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
