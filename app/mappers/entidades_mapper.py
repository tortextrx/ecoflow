
from app.mappers.base import BaseEcoSoftPayloadMapper
from app.models.schemas.domain import DomainCommand

class EntidadesMapper(BaseEcoSoftPayloadMapper):
    def build(self, command: DomainCommand) -> dict:
        f = command.fields

        dencom = f.get("DENCOM", "").strip()
        denfis = f.get("DENFIS", "").strip()
        if not denfis:
            denfis = dencom

        # Tipo de entidad — por defecto pre-entidad
        # Soporta: PREENTIDAD, ACREEDOR, PROVEEDOR, CLIENTE, USUARIO, P_LABORAL, SUCURSAL
        tipo = f.get("TIPO_ENTIDAD", "PREENTIDAD").upper()

        return {
            "ESTADO":     2,
            "SUCURSAL":   0,
            "DENCOM":     dencom,
            "DENFIS":     denfis,
            "NOMBRE":     f.get("NOMBRE", ""),
            "APELLIDO1":  f.get("APELLIDO1", ""),
            "APELLIDO2":  f.get("APELLIDO2", ""),
            "DIRECCION":  f.get("DIRECCION", ""),
            "POBLACION":  f.get("POBLACION", ""),
            "PROVINCIA":  f.get("PROVINCIA", ""),
            "CP":         f.get("CP", ""),
            "CIF":        f.get("CIF", ""),
            "TLF1":       f.get("TLF1", ""),
            "TLF2":       "",
            "TLF3":       "",
            "TLF4":       "",
            "EMAIL":      f.get("EMAIL", ""),
            "WWW":        f.get("WWW", ""),
            "OBSERVACIONES": f.get("OBSERVACIONES", ""),
            "PAIS":       1,
            "RE":         0,
            "ACTIVIDAD":  0,
            "GRUPO":      0,
            "ZONA":       0,
            "CLIENTE":    1 if tipo == "CLIENTE"   else 0,
            "PROVEEDOR":  1 if tipo == "PROVEEDOR" else 0,
            "ACREEDOR":   1 if tipo == "ACREEDOR"  else 0,
            "USUARIO":    1 if tipo == "USUARIO" else 0,
            "PREENTIDAD": 1 if tipo == "PREENTIDAD" else 0,
            "RESIDENTE":  0,
            "SUCURSALES": 1 if tipo == "SUCURSAL" else 0,
            "P_LABORAL":  1 if tipo == "P_LABORAL" else 0,
            "REPRESENTANTE": 0,
            "PERITO":     0,
            "DISTRIBUIDOR": 0,
            "CCCLIENTE":  "",
            "CCPROVEEDOR": "",
            "CCACREEDOR": "",
            "CCVENTA":    "",
            "CCCOMPRA":   "",
            "CCGASTO":    "",
            "RETENCION":  0,
            "AUX1":       "",
            "AUX2":       "",
            "AUX3":       ""
        }
