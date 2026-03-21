# Capacidades Funcionales Reales de ecoFlow

> Basado en la API de ecoSoftWEB. Solo se anuncian capacidades efectivamente soportadas.

## Tabla de Capacidades por Módulo

### ENTIDADES

| Operación | Soportado | Notas |
|-----------|-----------|-------|
| Crear entidad (cliente/proveedor/acreedor) | ✅ | Multi-turno con recolección de nombre + CIF |
| Consultar entidad por nombre o CIF | ✅ | Resolución con desambiguación |
| Consultar campo específico (teléfono, email, dirección) | ✅ | |
| Modificar entidad | ⚠️ Parcial | Requiere PKEY, endpoint disponible |
| Borrar entidad | ✅ | Doble confirmación con "CONFIRMO" literal |
| Listado filtrado | ✅ | Por DENCOM (wildcard) o CIF |

### SERVICIOS

| Operación | Soportado | Notas |
|-----------|-----------|-------|
| Crear servicio | ✅ | Resuelve cliente, valida descripción, confirma antes |
| Consultar servicio por PKEY | ✅ | Proactivo al detectar ID de 5 dígitos |
| Ver historial de actuaciones | ✅ | ObtenerHistorico_Servicio |
| Añadir nota/actuación al historial | ✅ | Con PKEY detectado proactivamente |
| Borrar servicio | ✅ | Doble confirmación ("CONFIRMO") |
| Modificar servicio | ⚠️ Parcial | Endpoint existe, flujo conversacional pendiente |

### ARTÍCULOS

| Operación | Soportado | Notas |
|-----------|-----------|-------|
| Buscar artículo por nombre/referencia | ✅ | Búsqueda por wildcard en DESCRIPCION |
| Crear artículo | ✅ | Flujo conversacional con recolección |
| Consultar artículo por PKEY | ✅ | ObtenerArticulo directo |
| Borrar artículo | ❌ No soportado | La API sí lo permite, pero no está integrado conversacionalmente por riesgo |
| Modificar artículo | ❌ No soportado | Pendiente |

### CONTRATOS

| Operación | Soportado | Notas |
|-----------|-----------|-------|
| Crear contrato | ✅ | Flujo completo: cliente + descripción + precio + confirmación |
| Consultar contrato por PKEY | ✅ | |
| Listar contratos de un cliente | ✅ | Filtrado por pkey_entidad |
| Modificar contrato | ⚠️ Parcial | Endpoint disponible, flujo pendiente |
| Borrar contrato | ✅ | Doble confirmación ("CONFIRMO") |

### FACTURACIÓN

> **⚠️ Restricciones de la API de ecoSoftWEB:**
> - **NO** se pueden crear facturas de venta finales (NC=13).
> - **NO** se pueden crear facturas simplificadas (NC=20).
> - **NO** se pueden borrar facturas de venta ni simplificadas.

| Tipo de Documento | NC | Crear | Consultar | Borrar |
|---------------------|-----|--------|-----------|--------|
| Presupuesto de Compra | 1 | ✅ | ✅ | ✅ |
| Pedido de Compra | 2 | ✅ | ✅ | ✅ |
| Albarán de Compra | 4 | ✅ | ✅ | ✅ |
| Factura de Compra | 5 | ✅ | ✅ | ✅ |
| Factura de Gasto | 6 | ✅ | ✅ | ✅ |
| Presupuesto de Venta | 10 | ✅ | ✅ | ✅ |
| Pedido de Venta | 11 | ✅ | ✅ | ✅ |
| Albarán de Venta | 12 | ✅ | ✅ | ✅ |
| **Factura de Venta** | **13** | **❌ Prohibido** | ✅ | **❌ Prohibido** |
| Prefactura de Venta | 17 | ✅ | ✅ | ✅ |
| **Factura Simplificada** | **20** | **❌ Prohibido** | ✅ | **❌ Prohibido** |

## Ejemplos de Prompts de Usuario

### Entidades
- "Quiero dar de alta un cliente nuevo → Francisco Leal, CIF B82345670"
- "¿Cuál es el teléfono de EcoSoft?"
- "Borra la entidad 4503" (exige CONFIRMO)

### Servicios
- "Crea un servicio para EcoSoft: revisión del sistema de refrigeración central"
- "Muéstrame el historial del servicio 12345"
- "Añade al 12345 que se revisó el compresor y estaba sucio"

### Contratos
- "Crea un contrato de mantenimiento anual para Ferretería López, 50€/mes"
- "¿Qué contratos tiene EcoTech?"
- "Consulta el contrato 892"

### Artículos
- "Busca artículos con 'compresor'"
- "Crea un artículo: Filtro HEPA H14, referencia FLT-001"

### Facturación
- "Crea un presupuesto de venta para EcoTech, concepto: mantenimiento, importe 1200€"
- "Genera una prefactura para el cliente 4503 por 800€ de materiales"
- "Consulta el documento 9876"
- "Lista las facturas de EcoSoft de este año"

## Mecanismos de Seguridad

| Mecanismo | Descripción |
|-----------|-------------|
| Doble confirmación de borrado | Se exige escribir "CONFIRMO" letteralmente para eliminar entidades, servicios, contratos y documentos |
| Blocking de NC prohibidos | El orquestador bloquea conversacionalmente NC=13 y NC=20 antes de intentar el ERP |
| Validación de descripción | Rechaza descripciones de menos de 8 caracteres o sin contenido real |
| Resolución antes de ejecutar | Siempre verifica que la entidad existe antes de vincularla |
| Resumen previo | Toda operación de escritura presenta un resumen para confirmación antes de ejecutar |
