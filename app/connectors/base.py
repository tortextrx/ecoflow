import httpx, logging, contextvars
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from app.core.config import settings

logger = logging.getLogger("ecoflow")

ecoflow_trace_ctx = contextvars.ContextVar("ecoflow_trace_id", default="no-trace")

class BaseEcoSoftConnector:
    def __init__(self):
        self.base_url = "https://www.ecosoftapi.net"
        self._auth = settings.ecosoft_token_auth
        self._user = settings.ecosoft_token_usuario

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._auth}.{self._user}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)))
    async def _post(self, endpoint: str, data: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = self._headers()
        trace_id = ecoflow_trace_ctx.get()
        
        # Ocultamos información confidencial en los logs
        safe_headers = {**headers, "Authorization": "***"}
        logger.info({"action": "erp_request_start", "endpoint": endpoint, "payload": data, "headers": safe_headers, "trace_id": trace_id})
        
        # Timeout robusto: 10s connect, 45s read
        timeout = httpx.Timeout(10.0, read=45.0)
        
        try:
            async with httpx.AsyncClient(http2=False, timeout=timeout) as client:
                resp = await client.post(url, json=data, headers=headers)
                
                try:
                    resp_data = resp.json()
                except Exception:
                    resp_data = {"raw_text": resp.text[:500]}

                logger.info({"action": "erp_response", "endpoint": endpoint, "status_code": resp.status_code, "resp_data": resp_data, "trace_id": trace_id})
                
                resp.raise_for_status()
                return resp_data
        except httpx.TimeoutException as te:
            logger.error({"action": "erp_timeout", "endpoint": endpoint, "trace_id": trace_id, "error": str(te)})
            return {"error": "Timeout conectando con el ERP. Es posible que el servidor esté saturado.", "success": False}
        except httpx.HTTPStatusError as hse:
            logger.error({"action": "erp_http_error", "endpoint": endpoint, "status_code": hse.response.status_code, "trace_id": trace_id, "error": str(hse)})
            # Devolvemos error seguro en vez de romper la promesa, para que falle graciosamente en la capa de resolver/tools
            return {"error": f"Error HTTP {hse.response.status_code} del ERP.", "success": False}
        except Exception as e:
            logger.error({"action": "erp_unexpected_error", "endpoint": endpoint, "trace_id": trace_id, "error": str(e)}, exc_info=True)
            return {"error": "Fallo inesperado al conectar con el ERP.", "success": False}
