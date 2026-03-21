# ecoFlow — Contexto Completo de Desarrollo

## Documento de Continuidad — Última actualización: 2026-03-20T18:40

> ⚠️ Este documento contiene todo el contexto necesario para continuar el desarrollo de ecoFlow en una nueva sesión de chat. Lee este archivo COMPLETO antes de ejecutar cualquier acción.

---

## 1. IDENTIDAD DEL PROYECTO

**Proyecto:** ecoFlow  
**Descripción:** Capa conversacional transaccional multimodal para ecoSoftWEB. Sistema que permite operar el ERP mediante lenguaje natural y contenido multimodal (texto, imágenes, PDF), ejecutando operaciones reales a través de las APIs de ecoSoftWEB.  
**Canal actual:** Chat web en producción (`https://ecobot.es/ecoflow-chat/`)  
**Canal futuro:** WhatsApp, Teams, email, app ecoSoft  
**Estado:** Sprint 2 completado. Sprint 3 en curso (APIs completas).

---

## 2. ACCESO AL SERVIDOR

```
Servidor:  serverIA
IP:        10.20.167.5
Usuario:   root
Password:  o1wrNtxq2?fA
Protocolo: SSH (acceso por VPN — la VPN puede ser inestable)
```

**⚠️ REGLA CRÍTICA:** Si la conexión SSH falla → DETENTE Y PIDE RECONEXIÓN. No asumas el estado del sistema.

---

## 3. SERVICIOS EN PRODUCCIÓN

| Servicio | Puerto | Estado | No tocar |
|---|---|---|---|
| **ecoflow** | `127.0.0.1:18080` | ✅ active | Nuestro servicio |
| **ecoBot** | `127.0.0.1:8000` | ✅ active (uvicorn multi-worker) | ❌ NUNCA tocar |
| **ecoFast licencias** | (systemd) | ✅ active | ❌ NUNCA tocar |
| **nginx** | 80 / 443 | ✅ active | Solo añadir location, nunca modificar existente |
| **PostgreSQL** | `127.0.0.1:5432` | ✅ active | BD separada por proyecto |

---

## 4. CONFIGURACIÓN ECOFLOW EN SERVIDOR

### Directorios

```
/home/ecoflow/           ← Home del usuario del servicio
/home/ecoflow/app/       ← Código fuente de la aplicación
/home/ecoflow/venv/      ← Virtualenv Python (NO compartir con otros proyectos)
/home/ecoflow/.env       ← Variables de entorno (ver §5)
```

### Systemd

```ini
# /etc/systemd/system/ecoflow.service
[Unit]
Description=ecoFlow - Capa conversacional transaccional para ecoSoftWEB
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=ecoflow
Group=ecoflow
WorkingDirectory=/home/ecoflow
EnvironmentFile=/home/ecoflow/.env
ExecStart=/home/ecoflow/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 18080 --workers 1
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ecoflow
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### Nginx (location existente)

```nginx
# Parte del bloque server de ecobot.es
location /ecoflow-chat/ {
    proxy_pass http://127.0.0.1:18080/ecoflow-chat/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /api/ecoflow/ {
    proxy_pass http://127.0.0.1:18080/api/ecoflow/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 120s;
    client_max_body_size 20M;
}
```

### Variables de entorno (`.env`)

Las claves exactas están en `/home/ecoflow/.env`. Las variables necesarias son:

```
ECOSOFT_TOKEN_AUTH=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
ECOSOFT_TOKEN_USUARIO=lUpN8au+eneOkQ4IgVup8Q==
ECOSOFT_API_BASE=https://www.ecosoftapi.net
OPENROUTER_API_KEY=sk-or-...
```

### Dependencias Python en venv

```
fastapi==0.135.1
openai==2.29.0       # Para multimodal con OpenRouter
pdfplumber           # Extracción PDF con texto
# + uvicorn, pydantic, python-multipart, paramiko...
```

---

## 5. APIs DE ECOSOFTWEB — REFERENCIA COMPLETA

**Base URL:** `https://www.ecosoftapi.net`  
**Auth:** `Authorization: Bearer {ECOSOFT_TOKEN_AUTH}.{ECOSOFT_TOKEN_USUARIO}`

### 5.1 API_Entidades

- `POST /API_Entidades/grabarEntidad` — Crear entidad
- `POST /API_Entidades/modificarEntidad` — Modificar entidad (requiere PKEY)
- `POST /API_Entidades/borrarEntidad` — Borrar entidad (requiere PKEY)
- `POST /API_Entidades/ObtenerEntidad` — Obtener por PKEY
- `POST /API_Entidades/ObtenerEntidades` — Buscar/filtrar entidades

**Tipos de entidad (campo en mapper):**

| TIPO_ENTIDAD (interno) | Campo ERP | Uso |
|---|---|---|
| PREENTIDAD | PREENTIDAD=1 | Pre-entidad/precliente |
| CLIENTE | CLIENTE=1 | Cliente de venta |
| PROVEEDOR | PROVEEDOR=1 | Proveedor de compra |
| ACREEDOR | ACREEDOR=1 | Proveedor de gasto (tickets) |

### 5.2 API_Facturacion

- `POST /API_Facturacion/grabarFacturacion` — Crear documento
- `POST /API_Facturacion/modificarFacturacion` — Modificar (requiere PKEY)
- `POST /API_Facturacion/borrarFacturacion` — Borrar (requiere PKEY)
- `POST /API_Facturacion/ObtenerFacturacion` — Obtener por PKEY
- `POST /API_Facturacion/ObtenerFacturaciones` — Listar/filtrar
- `POST /API_Facturacion/grabarFacturacionLinea` — Añadir línea

**NIVELCONTROL (tipo de documento):**

| NC | Tipo |
|---|---|
| 1 | Presupuesto compra |
| 2 | Pedido compra |
| 4 | Albarán compra |
| 5 | Factura compra |
| **6** | **Factura gasto** ✅ implementado |
| 10 | Presupuesto venta |
| 11 | Pedido venta |
| 12 | Albarán venta |
| 17 | Prefactura venta |

**MODO_ID_ENTIDAD:** 0=PKEY, 1=CIF, 2=Email

### 5.3 API_Servicios

- `POST /API_Servicios/grabarServicio` — Crear servicio técnico
- `POST /API_Servicios/modificarServicio`
- `POST /API_Servicios/borrarServicio`
- `POST /API_Servicios/ObtenerServicio`
- `POST /API_Servicios/ObtenerServicios`
- `POST /API_Servicios/grabarHistorico` — Añadir entrada historial
- `POST /API_Servicios/ObtenerHistorico`
- `POST /API_Servicios/ObtenerHistorico_Servicio`
- `POST /API_Servicios/modificarHistorico`
- `POST /API_Servicios/borrarHistorico`

**NIVELCONTROL Servicios:** 0=Cita comercial, 1=Tarea, 2=Tarea planner, 3=Fab.

### 5.4 API_Articulos

- `POST /API_Articulos/grabarArticulo`
- `POST /API_Articulos/modificarArticulo`
- `POST /API_Articulos/borrarArticulo`
- `POST /API_Articulos/ObtenerArticulo`
- `POST /API_Articulos/ObtenerArticulos`

**NIVELCONTROL:** 1=Artículo físico, 2=Concepto/servicio

### 5.5 API_Contratos

- `POST /API_Contratos/grabarContrato`
- `POST /API_Contratos/modificarContrato`
- `POST /API_Contratos/borrarContrato`
- `POST /API_Contratos/ObtenerContrato`
- `POST /API_Contratos/ObtenerContratos`

---

## 6. ESTRUCTURA DE ARCHIVOS ACTUAL EN SERVIDOR

```
/home/ecoflow/app/
├── __init__.py
├── main.py
├── process_new.py
│
├── api/
│   ├── routes_chat.py        ✅ POST /api/ecoflow/chat (multipart)
│   └── routes_internal.py    ✅ GET /health
│
├── connectors/
│   ├── base.py               ✅ BaseEcoSoftConnector (httpx, auth, retry)
│   ├── entidades.py          ✅ grabar + buscar
│   └── facturacion.py        ✅ grabar_factura_gasto (NC=6)
│
├── mappers/
│   ├── base.py               ✅
│   ├── buscar_entidades_mapper.py ✅
│   ├── entidades_mapper.py   ✅ con TIPO_ENTIDAD (ACREEDOR/CLIENTE/PROVEEDOR/PREENTIDAD)
│   └── facturacion_mapper.py ✅ NC=6
│
├── services/
│   ├── chat_service.py       ✅ flujo completo: ticket → acreedor → factura gasto
│   ├── identity_resolver.py  ✅
│   ├── intent_service.py     ✅
│   ├── orchestrator.py       ✅
│   └── tools/
│       ├── base.py           ✅
│       ├── registry.py       ✅ registra: buscar_entidad, crear_preentidad, registrar_gasto, extraer_documento
│       ├── buscar_entidad.py ✅
│       ├── crear_preentidad.py ✅
│       ├── extraer_documento.py ✅ GPT-4o multimodal via OpenRouter
│       └── registrar_gasto.py ✅ NC=6 con creación de acreedor si no existe
│
├── models/
│   ├── schemas/ (domain.py, extraction.py, identity.py, incoming.py, llm.py, tools.py, chat.py)
│   └── db/ (actor.py, conversation.py, event.py, idempotency.py, job.py, media.py, operation.py, raw_message.py)
│
├── core/
│   ├── config.py, db.py, exceptions.py, job_queue.py, logging_config.py
│
├── providers/
│   ├── llm_provider.py, openai_responses.py
│
├── repositories/
│   ├── actor_repo, conversation_repo, event_repo, job_repo, operation_repo, raw_message_repo
│
└── static/
    ├── index.html            ✅ Chat web dark mode glassmorphism
    ├── style.css             ✅
    └── chat.js               ✅
```

---

## 7. LO QUE FUNCIONA HOY (SPRINT 2 COMPLETADO)

| Funcionalidad | Estado | Cómo probarlo |
|---|---|---|
| Chat web en producción | ✅ | `https://ecobot.es/ecoflow-chat/` |
| Crear pre-entidad por texto | ✅ | "Crear precliente Empresa X CIF B123" |
| Buscar entidad por CIF | ✅ | "Busca entidad CIF B85364495" |
| Subir ticket/foto → extracción GPT-4o | ✅ | Adjuntar imagen en chat web |
| Crear acreedor si no existe en ERP | ✅ | Automático en flujo de ticket |
| Grabar factura de gasto (NC=6) | ✅ | Automático tras confirmación |
| Flujo completo: foto → acreedor → factura | ✅ | Demo con ticket Flying Tiger |
| Sesiones en memoria por session_id | ✅ | Persistente durante sesión |

**Último test exitoso:**

- Ticket Flying Tiger Copenhagen → CIF B85364495
- Acreedor creado ID `43013582` (ACREEDOR=1)
- Factura gasto creada ID `12465` — Ref A/1188 — 4,50€

---

## 8. SPRINT 3 — PENDIENTE DE IMPLEMENTAR

### Prioridad 1: Entidades completa

| Operación | Endpoint | Tool a crear |
|---|---|---|
| Crear cualquier tipo de entidad | `grabarEntidad` | `CrearEntidadTool` (generalizar crear_preentidad) |
| Modificar entidad | `modificarEntidad` | `ModificarEntidadTool` |
| Borrar entidad | `borrarEntidad` | `BorrarEntidadTool` |
| Obtener entidad por PKEY | `ObtenerEntidad` | `ObtenerEntidadTool` |

### Prioridad 2: Facturación completa (todos los tipos)

| Operación | Herramienta |
|---|---|
| Grabar cualquier NC (1,2,4,5,6,10,11,12,17) | `GrabarFacturacionTool` (generalizar registrar_gasto) |
| Modificar documento | `ModificarFacturacionTool` |
| Borrar documento | `BorrarFacturacionTool` |
| Obtener documento | `ObtenerFacturacionTool` |
| Listar documentos | `ListarFacturacionesTool` |

### Prioridad 3: Servicios (CRUD + historial)

### Prioridad 4: Artículos (CRUD)

### Prioridad 5: Contratos (CRUD)

### Intenciones del ChatService a añadir

```python
# Palabras clave → herramienta
"crear cliente" / "nuevo cliente"      → CrearEntidadTool(CLIENTE)
"crear proveedor"                      → CrearEntidadTool(PROVEEDOR)
"crear acreedor"                       → CrearEntidadTool(ACREEDOR)
"modificar entidad" / "actualizar"     → ModificarEntidadTool
"borrar entidad" / "eliminar entidad"  → BorrarEntidadTool
"crear pedido compra"                  → GrabarFacturacionTool(NC=2)
"crear albarán compra"                 → GrabarFacturacionTool(NC=4)
"crear factura compra"                 → GrabarFacturacionTool(NC=5)
"crear presupuesto"                    → GrabarFacturacionTool(NC=10)
"crear pedido venta"                   → GrabarFacturacionTool(NC=11)
"crear prefactura"                     → GrabarFacturacionTool(NC=17)
"consultar factura" / "ver factura"    → ObtenerFacturacionTool
"crear servicio" / "nueva tarea"       → CrearServicioTool
"crear artículo" / "nuevo artículo"    → CrearArticuloTool
"crear contrato"                       → CrearContratoTool
```

---

## 9. PRINCIPIOS ARQUITECTÓNICOS CRÍTICOS

### SUCURSAL por defecto (política activa)

- Para altas operativas iniciadas desde ecoFlow, el valor por defecto de `SUCURSAL` queda fijado en `1`.
- No usar `SUCURSAL=0` como valor por defecto en payloads de creación.

### ExtractionSchema → DomainCommand → Mapper → Connector

La IA nunca toca el payload del ERP directamente. El flujo siempre es:

```
IA extrae → DomainCommand (interno) → Mapper (determinista) → Connector → ERP
```

### Canal agnóstico

ChatService es el núcleo. Los canales son adaptadores:

- Web: `routes_chat.py` ya implementado
- WhatsApp futuro: `routes_whatsapp.py` que llama al mismo ChatService

### Tipos de entidad

Siempre usar el campo `TIPO_ENTIDAD` en DomainCommand:

- `PREENTIDAD` → cuando el usuario pide "precliente" o "pre-entidad"
- `CLIENTE` → cuando el usuario pide "cliente"
- `PROVEEDOR` → cuando viene de factura de compra
- `ACREEDOR` → cuando viene de ticket/gasto (crédito)

### ConfirmationPolicy

- `registrar_gasto` → SIEMPRE pedir confirmación antes de crear
- `crear_entidad` → ejecutar directo (bajo riesgo)
- `borrar_*` → SIEMPRE pedir confirmación

---

## 10. SERVERIA_DEPLOYMENT_POLICY (REGLAS INQUEBRANTABLES)

```
METODOLOGÍA OBLIGATORIA:
1. INSPECCIÓN (sin modificar nada)
2. PROPUESTA
3. IMPLEMENTACIÓN (cambios pequeños y controlados)
4. VALIDACIÓN (ecoFlow OK + ecoBot OK)

PROHIBIDO:
- Tocar ecoBot o ecoFast
- Modificar nginx sin nginx -t previo
- Asumir estado si SSH falla (→ STOP y pedir reconexión)
- Instalar deps globales
- Usar venv de otros proyectos

DESPUÉS DE CADA DEPLOY VERIFICAR:
- systemctl is-active ecoflow.service → active
- systemctl is-active ecobot.service → active
- curl http://127.0.0.1:18080/health → {"status":"ok"}
```

---

## 11. PATRÓN DE DEPLOY (siempre el mismo flujo)

```python
# Patrón estándar de script de deploy
import paramiko, io, time

HOST, USER, PASS = "10.20.167.5", "root", "o1wrNtxq2?fA"
HOME = "/home/ecoflow/app"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(CODE.encode()), f"{HOME}/ruta/archivo.py")
sftp.close()

client.exec_command("systemctl restart ecoflow.service")
time.sleep(4)
_, o, _ = client.exec_command("systemctl is-active ecoflow.service")
assert o.read().decode().strip() == "active", "SERVICE FAILED"

# Verificar ecoBot sigue activo
_, o, _ = client.exec_command("systemctl is-active ecobot.service")  
assert o.read().decode().strip() == "active", "ECOBOT AFFECTED - STOP"

client.close()
```

---

## 12. ENDPOINT DE CHAT (REFERENCIA)

```
POST https://ecobot.es/api/ecoflow/chat
Content-Type: multipart/form-data

Campos:
  session_id: str      (identificador de sesión, libre)
  message: str         (texto del usuario, opcional si hay file)
  file: UploadFile     (imagen/PDF, opcional)

Respuesta:
{
  "reply": "Texto de respuesta del asistente",
  "state": "idle|confirming|done",
  "extracted_data": {...} | null,
  "erp_result": {"entidad_pkey": "...", "factura_pkey": "..."} | null
}
```

---

## 13. PRÓXIMAS ACCIONES INMEDIATAS

Al retomar el desarrollo, ejecutar en este orden:

### Paso 1: Inspección previa

```bash
# En servidor - verificar estado antes de tocar nada
systemctl is-active ecoflow ecobot
cat /home/ecoflow/app/connectors/entidades.py
cat /home/ecoflow/app/connectors/facturacion.py
cat /home/ecoflow/app/services/chat_service.py
```

### Paso 2: Sprint 3 - Iteración 1

Implementar en un solo script controlado:

1. `connectors/entidades.py` → añadir: modificar_entidad, borrar_entidad, obtener_entidad
2. `connectors/facturacion.py` → añadir: modificar, borrar, obtener, listar
3. `mappers/facturacion_mapper.py` → generalizar para todos los NIVELCONTROL
4. `services/tools/` → crear: ModificarEntidadTool, BorrarEntidadTool, ObtenerEntidadTool, GrabarFacturacionTool, ObtenerFacturacionTool
5. `services/tools/registry.py` → registrar nuevas tools
6. `services/chat_service.py` → añadir detección de nuevas intenciones

### Paso 3: Iteración 2

1. `connectors/servicios.py` → CRUD completo + historial
2. `mappers/servicios_mapper.py`
3. `services/tools/servicios_tools.py`

### Paso 4: Iteración 3

1. `connectors/articulos.py` + `contratos.py`
2. Mappers y tools correspondientes

---

## 14. PROMPT MAESTRO ORIGINAL

El prompt maestro establece los principios filosóficos del proyecto:

- **No es un bot de WhatsApp ni un OCR aislado** → es una plataforma conversacional transaccional
- **Canal agnóstico**: WhatsApp es el primer adaptador, el núcleo es independiente
- **IA como capa cognitiva, no como ejecutor** → la IA detecta y extrae, el código determinista ejecuta
- **Diseño por intención y acciones**, no por tipo de input
- **Observabilidad desde el día 1**
- **Sin sobrearquitectura**: no Kubernetes, no microservicios, no colas distribuidas
- **Prioridades**: viabilidad real > rapidez > bajo acoplamiento > extensibilidad > infra existente > demo temprana

---

## 15. CONTEXTO DE CONVERSACIONES PREVIAS

| Conversación | Contenido key |
|---|---|
| `d61d4061-dcc6-4c5e-8999-1ad6acbbb640` | Esta conversación (Sprint 2 + inicio Sprint 3) |
| Artifacts en `.gemini/antigravity/brain/d61d4061...` | architecture_plan v1/v2/v2.1, sprint2_plan, sprint3_plan, task.md, screenshots |

### Links a artifacts críticos

- [Plan arq. v1](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/ecoflow_architecture_plan.md)
- [Plan arq. v2](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/ecoflow_architecture_plan_v2.md)
- [Plan arq. v2.1](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/ecoflow_architecture_plan_v2_1.md)
- [Sprint 2 plan](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/sprint2_plan.md)
- [Sprint 3 plan](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/ecoflow_sprint3_plan.md)
- [Este doc](file:///C:/Users/Javier/.gemini/antigravity/brain/d61d4061-dcc6-4c5e-8999-1ad6acbbb640/ecoflow_continuity_context.md)
