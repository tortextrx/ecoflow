import asyncio
import httpx
import uuid
import sys

BASE_URL = "http://127.0.0.1:18080/api/ecoflow/chat"

class E2ERunner:
    def __init__(self):
        self.results = []
        self.passes = 0
        self.fails = 0

    async def chat(self, sid: str, msg: str):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    BASE_URL, 
                    data={"session_id": sid, "message": msg}, 
                    timeout=20.0
                )
                if resp.status_code != 200:
                    return f"HTTP_ERROR_{resp.status_code}"
                return resp.json().get("reply", "")
        except Exception as e:
            return f"EXCEPTION: {str(e)}"

    async def run_scenario(self, name: str, steps: list):
        sid = f"e2e-{uuid.uuid4().hex[:6]}"
        print(f"\n▶ Ejecutando Escenario: {name} (Session: {sid})")
        
        scenario_passed = True
        for step in steps:
            msg = step.get("msg")
            expected_keywords = step.get("expected", [])
            forbidden_keywords = step.get("forbidden", [])
            
            print(f"  👤 Usuario: {msg}")
            reply = await self.chat(sid, msg)
            print(f"  🤖 ecoFlow: {reply}")
            
            # Validations
            step_passed = True
            for kw in expected_keywords:
                if kw.lower() not in reply.lower():
                    print(f"  ❌ Falla: Falta palabra clave esperada '{kw}'")
                    step_passed = False
                    
            for kw in forbidden_keywords:
                if kw.lower() in reply.lower():
                    print(f"  ❌ Falla: Contiene palabra prohibida '{kw}'")
                    step_passed = False
                    
            if not step_passed:
                scenario_passed = False
                break
                
        if scenario_passed:
            self.passes += 1
            self.results.append({"name": name, "status": "PASS"})
            print(f"✅ ESCENARIO OK: {name}")
        else:
            self.fails += 1
            self.results.append({"name": name, "status": "FAIL"})
            print(f"❌ ESCENARIO FALLIDO: {name}")

async def main():
    runner = E2ERunner()
    
    # 1. ENTIDAD CRUD (Basico)
    await runner.run_scenario("Entidad - Alta y Borrado", [
        {"msg": "Crea un cliente nuevo llamado E2ETestClient con NIF B99887766", "expected": ["E2ETestClient", "B99887766"]},
        {"msg": "sí, grábalo", "expected": ["éxito", "alta"]},
        {"msg": "borra el cliente E2ETestClient", "expected": ["confirmas", "borrar"]},
        {"msg": "CONFIRMO", "expected": ["borrado", "éxito"]}
    ])
    
    # 2. ARTÍCULO
    await runner.run_scenario("Artículo - Alta", [
        {"msg": "Da de alta un artículo llamado Cable Red 2M E2E por 5 euros", "expected": ["Cable", "5"]},
        {"msg": "ok dale", "expected": ["alta", "éxito"]}
    ])
    
    # 3. SERVICIOS (Apertura y notas)
    await runner.run_scenario("Servicios - Apertura y Notas", [
        {"msg": "Abre un parte de trabajo diciendo 'Reinstalar Windows E2E'", "expected": ["cliente", "falta"]},
        {"msg": "Es para el cliente Demo Opciones", "expected": ["confirm", "Windows"]},
        {"msg": "sí, adelante", "expected": ["parte", "éxito"]},
        # Asumimos que recuerda la PKEY en la sesión
        {"msg": "Añade una nota a ese parte diciendo que falta licencia", "expected": ["nota", "licencia"]},
        {"msg": "sí", "expected": ["éxito"]}
    ])
    
    # 4. CONTRATOS
    await runner.run_scenario("Contratos - Gestión Completa", [
        {"msg": "Crea un contrato de mantenimiento de servidores E2E por 150 euros al mes para PKEY 23154", "expected": ["150", "mantenimiento"]},
        {"msg": "ok graba", "expected": ["contrato", "éxito"]},
        {"msg": "lista los contratos de 23154", "expected": ["contratos"]}
    ])
    
    # 5. GASTOS
    await runner.run_scenario("Facturación - Gasto", [
        {"msg": "Quiero registrar un gasto de 50.50 euros en material de oficina para el proveedor 12345", "expected": ["50", "material"]},
        {"msg": "sí", "expected": ["éxito", "gasto"]}
    ])

    # 6. CANCELACIÓN
    await runner.run_scenario("Flujo - Cancelación Voluntaria", [
        {"msg": "crea un cliente llamado Falso", "expected": ["Falso"]},
        {"msg": "no, cancela", "expected": ["cancel", "anula"], "forbidden": ["éxito"]}
    ])

    # 7. ERRORES ERP
    await runner.run_scenario("Errores ERP - Borrar Factura Inexistente", [
        {"msg": "borra la factura número 999999", "expected": ["confirm"]},
        {"msg": "CONFIRMO", "expected": ["error", "no"], "forbidden": ["éxito"]}
    ])

    print("\n" + "="*40)
    print("📋 RESUMEN E2E")
    print("="*40)
    for r in runner.results:
        icono = "✅" if r["status"] == "PASS" else "❌"
        print(f"{icono} {r['name']}")
    
    print(f"\nTotal Pass: {runner.passes} | Total Fail: {runner.fails}")
    
    if runner.fails > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
