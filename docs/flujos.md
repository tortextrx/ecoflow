# Flujos Principales de ecoFlow

## 1. Alta de Entidad (NC=1, 2, 10)

- **Inicio**: Usuario pide crear un cliente/acreedor.
- **Detección**: El `cognitive_service` extrae el `nombre` y el `cif` (o los pide interactivamente).
- **Mapeo**: `entidades_mapper` construye el payload de alta (NC=1 para Cliente, NC=2 para Acreedor).
- **Confirmación**: El orquestador pide confirmación antes de llamar a `grabarEntidad`.

## 2. Creación de Servicio (NC=x)

- **Inicio**: El usuario pide "Crear revisión de la máquina X".
- **Resolución**: `resolver` busca la ficha técnica de la máquina por nombre o PKEY previa.
- **Inserción**: `servicios_tools` registra el nuevo parte de trabajo vinculado a la PKEY de la entidad.

## 3. Registro de Gasto (Gasto Multimodal OCR)

- **Inicio**: Usuario sube una imagen/PDF de un ticket.
- **Extracción**: `extraer_documento` llama a GPT-4o Vision para obtener CIF del emisor, Fecha, Base e IVA.
- **Resolución de Acreedor**: `resolver_entity` busca al emisor por CIF. Si no existe, lo crea automáticamente como ACREEDOR (NC=2).
- **Grabación**: `registrar_gasto` genera el payload de Cabecera y Detalle para NC=6 (Factura Gasto).
- **Identificador**: El sistema devuelve al usuario el **Doc ID** devuelto por el ERP.

## 4. Resolución de Entidad por CIF

- **Lógica**: Se realiza una búsqueda por CIF exacto en ecoSoftWEB.
- **Persistencia**: Si se encuentra, se guarda el `PKEY` en la sesión para evitar nuevas búsquedas durante el flujo conversacional.
- **Evitar duplicados**: Se prioriza siempre la `PKEY` existente antes de proceder a cualquier creación automática.
