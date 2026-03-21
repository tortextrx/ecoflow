import httpx, logging, json, os, contextvars
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

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3), retry=retry_if_exception_type(httpx.RequestError))
    async def _post(self, endpoint: str, data: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        headers = self._headers()
        trace_id = ecoflow_trace_ctx.get()
        
        logger.info(f"[TRACE:{trace_id}] Llamada ERP a endpoint={endpoint}")
        
        # TRAZADO CRÍTICO: Guardamos exactamente qué vamos a enviar
        trace = {
            "trace_id": trace_id,
            "url": url,
            "headers": headers,
            "payload": data
        }
        
        trace_file = f"/tmp/ecoflow_trace_{trace_id}.json" if trace_id != "no-trace" else "/tmp/ecoflow_trace.json"
        
        # Append seguro (un array de peticiones por trace_id)
        if os.path.exists(trace_file):
            try:
                with open(trace_file, "r") as f:
                    existing = json.load(f)
                    if not isinstance(existing, list): existing = [existing]
            except Exception:
                existing = []
            existing.append(trace)
            with open(trace_file, "w") as f: json.dump(existing, f, indent=2)
        else:
            with open(trace_file, "w") as f: json.dump([trace], f, indent=2)
        
        async with httpx.AsyncClient(http2=False) as client:
            resp = await client.post(url, json=data, headers=headers, timeout=30.0)
            
            # Guardamos la respuesta cruda también para ver el error del ERP
            log_resp_file = f"/tmp/ecoflow_response_{trace_id}.log" if trace_id != "no-trace" else "/tmp/ecoflow_response.log"
            with open(log_resp_file, "a") as f:
                f.write(f"\n--- POST {endpoint} ---\nSTATUS: {resp.status_code}\nBODY: {resp.text}\n")
                
            resp.raise_for_status()
            return resp.json()
