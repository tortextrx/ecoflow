# Informe de Viabilidad de Producción (GO_LIVE_REPORT)

**Fecha de Ejecución:** Marzo 2026
**Candidato a Release:** ecoFlow v4.1 (Hardened)

Este informe detalla los resultados de la suite completa de tests de integración end-to-end (E2E) ejecutados en el servidor de pre-producción `serverIA` simulando condiciones reales de conversación y casuísticas complejas.

---

## 🟢 1. Qué Pasa (Funcionalidades Exitosas)

- **Manejo Seguro de Inputs:** El sistema rechaza tramas malformadas, path traversal en IDs y ficheros gigantes (protecciones API).
- **Procesamiento de LLM Resiliente:** Los mecanismos de timeout e interceptación de caídas responden correctamente ("degradación elegante").
- **Flujo Feliz de Entidades:** El alta funciona estructural y procedimentalmente. Solicita confirmación si faltan datos, acumula estado y ejecuta la llamada ERP.
- **Humanización:** La *Response Layer* reformula eficientemente el código técnico ("✅ Alta Realizada") por un lenguaje cálido ("¡Genial! Ya está registrado con el ID...").

## 🔴 2. Qué Falla (Bugs y Regresiones Detectadas)

1. **Cortocircuito en Cancelaciones (Ignora Abortos):**
   - *Detalle:* Estando en un estado de recolecta de datos (ej. `AWAITING_ENTITY_COLLECT`), si el usuario responde "no, cancela", el orquestador ignora la intención `cancel` y sigue reclamando el campo faltante (*"Entendido, quieres cancelar. Solo necesito el CIF..."*).
2. **Confusión de Dominios (Artículos vs Clientes):**
   - *Detalle:* Al solicitar "Da de alta un **artículo**", el modelo de intenciones cruza dominios e inicia un flujo de alta de **cliente**, confirmando "Cliente: Artículo X". Posible ambigüedad en la definición del prompt o pérdida de peso en keywords.
3. **Pérdida de Contexto en Double-Confirm (Borrado):**
   - *Detalle:* Al enviar "CONFIRMO" para ejecutar un borrado de factura, el sistema olvida el objeto que iba a borrar y recae a un estado de pérdida (*"Genial... necesito que me digas en qué categoría puedo ayudarte"*), abortando de facto los borrados.
4. **Ceguera de PKEY Directas en Servicios/Gastos:**
   - *Detalle:* Aportar un "PKEY XXXXX" o "Proveedor 12345" crudo en lenguaje natural a veces no es resuelto por la extracción y el sistema se queda atascado pidiendo irremediablemente el nombre de la empresa para resolverlo por nombre.

## 🟡 3. Qué Queda Pendiente

- Refinar los descriptores del clasificador de intenciones (CognitiveService) para asilar mejor la diferencia semántica entre *crear artículo* y *crear entidad*.
- Hacer que la transición a `idle` / `cancel` en la máquina de estados sea un *Override* absoluto sobre cualquier estado `AWAITING_*`.
- Asegurar que la `PKEY` en memoria no se limpie antes del disparo del tool cuando retorna de un `AWAITING_DELETE_CONFIRM`.
- Relajar los asserts del E2E local para que coincidan con la aleatoriedad tolerada por la capa de Humanización, validando IDs generados o acciones en ERP y no strings puras.

## ⛔ 4. Consideraciones Bloqueantes para Producción

1. **El bug de Cancelación:** Un usuario atrapado en un bucle pidiendo un dato es una pésima UX, inoperable.
2. **El bug del Double-Confirm vacío:** Hace imposible borrar nada de forma natural.
3. **Crear artículos dispara entidades:** Supone ensuciar la base de datos de clientes del ERP con basura.

---

## 👩‍⚖️ Recomendación Binaria Final

**[ NOT READY ]**

**Motivo:** Aunque la arquitectura es segura, trazable y no filtra datos (requisitos técnicos top-tier), la máquina de estado conversacional contiene fisuras de usabilidad gravísimas. Los bloqueos de cancelación y el cruce de dominios (artículos metidos como clientes) generarían tickets de soporte masivos y corrupción leve de la BD del cliente final tras los primeros días de uso. Requiere una iteración estricta sobre las transiciones del orquestador y el sistema de intenciones antes de exponerlo a usuarios.
