import httpx, logging, json, os
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from app.core.config import settings

logger = logging.getLogger("ecoflow")

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
        
        # TRAZADO CRÍTICO: Guardamos exactamente qué vamos a enviar
        trace = {
            "url": url,
            "headers": headers,
            "payload": data
        }
        with open("/tmp/ecoflow_trace.json", "w") as f:
            json.dump(trace, f, indent=2)
        
        async with httpx.AsyncClient(http2=False) as client:
            resp = await client.post(url, json=data, headers=headers, timeout=30.0)
            
            # Guardamos la respuesta cruda también para ver el error del ERP
            with open("/tmp/ecoflow_response.log", "w") as f:
                f.write(f"STATUS: {resp.status_code}\n")
                f.write(f"BODY: {resp.text}")
                
            resp.raise_for_status()
            return resp.json()
