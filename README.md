# ecoFlow - Asistente IA para Gestión ecoSoftWEB

ecoFlow es un asistente conversacional inteligente desarrollado sobre **FastAPI** y **OpenRouter/GPT-4o**, diseñado para actuar como puente natural entre usuarios y el ERP **ecoSoftWEB**.

Permite la gestión de entidades (clientes/acreedores), el registro de partes de trabajo y el procesado multimodal de facturas de gasto mediante visión artificial.

## 🚀 Funcionalidades Principales

- **Alta Conversacional**: Crea clientes y acreedores solo hablando con el bot.
- **Flujo de Servicios**: Genera partes de trabajo (NC=x) y consulta históricos de mantenimiento.
- **Multimodal (Gasto OCR)**: Sube una foto de un ticket; ecoFlow extrae el CIF, fecha e importes, asocia el acreedor y graba la factura de gasto (NC=6).
- **Resolución Inteligente**: Búsqueda flexible por nombre o CIF con gestión de ambigüedad.
- **Conexión Real ERP**: Integración directa con la API de ecoSoftWEB.

## 🏛️ Estructura del Proyecto

```text
/ecoflow
  /app
    /services      # Lógica de negocio (Orchestrator, Cognitive, Resolver)
    /tools         # Herramientas funcionales (Search, Create, Register)
    /connectors    # Conexión con la API de ecoSoftWEB
    /mappers       # Transformadores de datos chat <-> ERP
    /models        # Esquemas Pydantic y modelos SQLAlchemy
    /api           # Endpoints de FastAPI
    /core          # Configuración, DB y Logging
  /docs            # Documentación técnica (Arquitectura, Flujos, Decisiones)
  /tests           # Pruebas unitarias e integración
  README.md        # Este archivo
  requirements.txt # Dependencias del proyecto
  .env.example     # Plantilla de configuración
```

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.12+ / FastAPI.
- **IA/LLM**: GPT-4o vía OpenRouter API.
- **ERP**: ecoSoftWEB API (NC=1, 2, 6, etc).
- **OCR/Vision**: GPT-4o Vision + pdfplumber.
- **Base de Datos**: PostgreSQL (para persistencia de jobs e histórica).

## ⚙️ Configuración y Arranque

1. Clona el repositorio.
2. Crea un entorno virtual e instala dependencias:

```bash
python -m venv venv
source venv/bin/activate # o venv\Scripts\activate en Windows
pip install -r requirements.txt
```

3. Configura las variables de entorno:

```bash
cp .env.example .env
# Edita .env con tus tokens de ecoSoftWEB y OpenRouter
```

4. Arranca el servicio:

```bash
uvicorn app.main:app --port 18080 --reload
```

## 🧪 Cómo probarlo

### Endpoint de Chat (JSON)

Puedes interactuar con el bot enviando un POST a:
`http://localhost:18080/api/ecoflow/chat`

**Payload ejemplo**:

```json
{
  "session_id": "TEST_01",
  "message": "Busca la dirección de Tiger Stores"
}
```

---
*Desarrollado para la automatización avanzada de procesos de gestión en ecoBot.*
