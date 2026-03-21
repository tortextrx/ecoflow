import base64, logging, json
from pathlib import Path
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger("ecoflow")

EXTRACTION_PROMPT = """
Eres un asistente de extracción de documentos contables.
Analiza el documento y extrae los siguientes campos en formato JSON:
{
  "proveedor": "nombre del emisor de la factura",
  "cif": "CIF/NIF del emisor",
  "fecha": "fecha en formato YYYY-MM-DD",
  "total": "importe total con IVA",
  "base": "base imponible",
  "iva": "porcentaje o importe de IVA",
  "descripcion": "descripción breve del concepto",
  "referencia": "número de factura o referencia"
}
Si no encuentras un campo, déjalo como cadena vacía. Responde SOLO con el JSON, sin explicaciones.
"""

class ExtractorMultimodalTool:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    async def extract_from_image(self, image_bytes: bytes, mime: str = "image/jpeg") -> dict:
        b64 = base64.b64encode(image_bytes).decode()
        response = await self.client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": EXTRACTION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
            ]}],
            max_tokens=500
        )
        raw = response.choices[0].message.content.strip()
        try:
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw = raw[4:]
            return json.loads(raw)
        except Exception:
            logger.warning(f"Could not parse extraction: {raw}")
            return {}

    async def extract_from_text(self, text: str) -> dict:
        response = await self.client.chat.completions.create(
            model="openai/gpt-4o",
            messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nTexto del documento:\n{text}"}],
            max_tokens=500
        )
        raw = response.choices[0].message.content.strip()
        try:
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"): raw = raw[4:]
            return json.loads(raw)
        except Exception:
            logger.warning(f"Could not parse extraction from text: {raw}")
            return {}

    async def extract(self, file_bytes: bytes, filename: str) -> dict:
        name = filename.lower()
        if name.endswith(".pdf"):
            return await self._extract_pdf(file_bytes)
        else:
            mime = "image/png" if name.endswith(".png") else "image/jpeg"
            return await self.extract_from_image(file_bytes, mime)

    async def _extract_pdf(self, pdf_bytes: bytes) -> dict:
        import io as _io
        try:
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
                text = "".join(p.extract_text() or "" for p in pdf.pages[:3])
            if len(text.strip()) > 80:
                logger.info("PDF: usando extracción por texto")
                return await self.extract_from_text(text)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")
        # Fallback: convertir a imagen
        try:
            from pdf2image import convert_from_bytes
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
            buf = _io.BytesIO()
            images[0].save(buf, format="PNG")
            logger.info("PDF: usando visión (imagen)")
            return await self.extract_from_image(buf.getvalue(), "image/png")
        except Exception as e:
            logger.error(f"pdf2image failed: {e}")
            return {}
