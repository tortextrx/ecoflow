
from datetime import datetime
from app.mappers.base import BaseEcoSoftPayloadMapper

NIVELCONTROL_SERVICIO = {
    0: "Cita comercial",
    1: "Tarea",
    2: "Tarea planner",
    3: "Tarea de fabricacion",
}

class ServicioMapper(BaseEcoSoftPayloadMapper):
    def build(
        self,
        nivelcontrol: int = 1,
        cif_cliente: str = "",
        pkey_cliente: int = 0,
        descripcion: str = "",
        fecha_inicio: str = "",
        fecha_fin: str = "",
        referencia: str = "",
        observaciones: str = "",
        tipo_servicio: int = 1,
        tipocontacto: int = 1,
        estado: int = 1,
        sucursal: str = "1",
        operario: str = "",
        pkey: int = 0,      # Solo para modificaciones
    ) -> dict:
        def fmt(d):
            try: return datetime.fromisoformat(d).strftime("%Y-%m-%dT%H:%M:%S")
            except: return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        modo_id = 0 if pkey_cliente else 1
        cliente = str(pkey_cliente) if pkey_cliente else cif_cliente

        payload = {
            "MODO_ID": modo_id,
            "TIPO_SERVICIO": tipo_servicio,
            "CLIENTE": cliente,
            "CLIENTE_DELEGACION": 1,
            "ESTADO": estado,
            "FECHA_INICIO": fmt(fecha_inicio),
            "FECHA_FIN": fmt(fecha_fin) if fecha_fin else fmt(fecha_inicio),
            "SERVICIO_DESCRIPCION": descripcion[:200] if descripcion else "",
            "OBSERVACIONES": observaciones or "Servicio via ecoFlow",
            "OPERARIO": operario,
            "OPERARIO_RECEPTOR": "",
            "SUCURSAL": sucursal,
            "REFERENCIA": referencia,
            "NIVELCONTROL": nivelcontrol,
            "TIPOCONTACTO": tipocontacto,
            "AUX1": "", "AUX2": "", "AUX3": ""
        }
        if pkey:
            payload["PKEY"] = pkey
        return payload
