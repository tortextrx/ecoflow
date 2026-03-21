class BuscarEntidadesMapper:
    def build(self, cif: str = "", email: str = "", dencom: str = "") -> dict:
        payload = {
            "ESTADO": -1,
            "CIF": cif,
            "EMAIL": email,
            "DENCOM": dencom,
            "CLIENTE": -1,
            "PROVEEDOR": -1,
            "ACREEDOR": -1,
            "PREENTIDAD": -1,
            "SUCURSAL": 0
        }
        return payload
