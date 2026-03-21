# ecoFlow 🌿

Asistente ERP conversacional e inteligente diseñado para ecoSoftWEB. 

ecoFlow permite interactuar con el ERP a través de lenguaje natural para gestionar entidades, artículos, servicios, contratos y facturación de forma ágil, segura y trazable.

## 🛠️ Capacidades Actuales (v4.0)

El sistema soporta las siguientes operaciones de forma completa:

- **Entidades**: Alta de clientes/proveedores, consulta de datos (NIF, teléfono, email) y borrado seguro.
- **Servicios**: Apertura de partes de trabajo, consulta de historial de actuaciones y cierre.
- **Contratos**: Gestión de contratos de mantenimiento, creación vinculada a cliente y facturación recurrente.
- **Artículos**: Búsqueda por descripción/referencia y alta de nuevos artículos.
- **Facturación**: Creación de presupuestos, pedidos, albaranes, gastos y prefacturas. (⚠️ Bloqueo de seguridad para facturas finales NC=13 y simplificadas NC=20).

Para un detalle técnico, consulta [FUNCTIONAL_CAPABILITIES.md](docs/FUNCTIONAL_CAPABILITIES.md).

## 🏗️ Arquitectura

ecoFlow utiliza una arquitectura segregada para garantizar la fiabilidad:

1.  **Capa Cognitiva**: Clasificación de intenciones y extracción de entidades mediante LLM.
2.  **Orquestador Determinista**: Máquina de estados que asegura que las operaciones ERP se ejecuten solo tras confirmaciones y validaciones.
3.  **Capa de Humanización**: Generación de respuestas naturales y empáticas sobre los resultados técnicos.
4.  **Conectores ERP**: Integración directa con las APIs de ecoSoftWEB.

## 🚀 Despliegue en serverIA

El despliegue está automatizado bajo la política [SERVERIA_DEPLOYMENT_POLICY.md](docs/SERVERIA_DEPLOYMENT_POLICY.md).

```bash
# Instalación
pip install -r requirements.txt

# Ejecución (Desarrollo)
uvicorn app.main:app --reload --port 18080
```

## 🔒 Seguridad y Privacidad

- **Sin Credenciales**: El repositorio no contiene contraseñas ni tokens. Toda la configuración se gestiona vía variables de entorno.
- **Borrado Seguro**: Las operaciones destructivas requieren una confirmación explícita con la palabra "CONFIRMO".
- **Trazabilidad**: Cada petición genera un `trace_id` único vinculado al `session_id` del usuario.

---
© 2026 ecoSoftWEB - ecoFlow Project
