import asyncio
import os
import sys
from typing import Any, Dict, Callable

from app.services.orchestrator import UnifiedOrchestrator
from app.services.orchestrator import cognitive_service, resolver, tool_registry
from app.services.chat_service import resolve_test_mode
import app.services.tools.facturacion_tools as fact_tools_module


class RegressionFailure(Exception):
    pass


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise RegressionFailure(message)


class AsyncRecorder:
    def __init__(self, response: Dict[str, Any]):
        self.calls = 0
        self.last_payload = None
        self.response = response

    async def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.calls += 1
        self.last_payload = payload
        return self.response


async def run_case(name: str, fn: Callable[[], Any]) -> None:
    print(f"\n[CASE] {name}")
    await fn()
    print(f"[PASS] {name}")


async def main() -> None:
    orchestrator = UnifiedOrchestrator()

    original_parse_intent = cognitive_service.parse_intent
    original_resolve_entity = resolver.resolve_entity
    original_env_mode = os.environ.get("ECOFLOW_TEST_MODE")

    originals = {
        "crear_articulo": tool_registry.crear_articulo.execute,
        "crear_contrato": tool_registry.crear_contrato.execute,
        "crear_servicio": tool_registry.crear_servicio.execute,
        "grabar_facturacion": tool_registry.grabar_facturacion.execute,
        "obtener_facturacion": tool_registry.obtener_facturacion.execute,
        "borrar_facturacion": tool_registry.borrar_facturacion.execute,
        "fact_connector_obtener": fact_tools_module._connector.obtener_facturacion,
        "fact_connector_borrar": fact_tools_module._connector.borrar_facturacion,
    }

    async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
        if context_pk:
            return {"status": "RESOLVED", "data": {"pkey": int(context_pk), "nombre": f"Entidad {context_pk}", "cif": ""}}
        if allowed_types == ["USUARIO", "P_LABORAL"]:
            return {"status": "RESOLVED", "data": {"pkey": 9101, "nombre": name or "Operario Demo", "cif": ""}}
        if name or cif:
            return {"status": "RESOLVED", "data": {"pkey": 23154, "nombre": name or "Entidad Demo", "cif": cif or ""}}
        return {"status": "NOT_FOUND"}

    resolver.resolve_entity = fake_resolve_entity

    try:
        # 1) cancelar alta de entidad a mitad
        async def case_cancel_entity_mid() -> None:
            intent_map = {
                "crea cliente parcial": {"intent": "create_entity", "entities": {"nombre_cliente": "Parcial SA"}},
                "cancela": {"intent": "cancel", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            session = {}
            r1 = await orchestrator.dispatch(session, "crea cliente parcial")
            assert_true(r1.get("state") == "AWAITING_ENTITY_CONFIRM", "Debe iniciar alta entidad")
            r2 = await orchestrator.dispatch(session, "cancela")
            assert_true(r2.get("state") == "idle", "Cancel debe devolver idle")
            assert_true("flow_mode" not in session and "flow_data" not in session, "Cancel debe limpiar contexto")

        await run_case("1. Cancelar alta entidad a mitad", case_cancel_entity_mid)

        # 2) cancelar contrato a mitad
        async def case_cancel_contract_mid() -> None:
            intent_map = {
                "crea contrato para demo": {"intent": "create_contract", "entities": {"nombre_cliente": "Demo", "descripcion": "Soporte"}},
                "olvidalo": {"intent": "unknown", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            session = {}
            r1 = await orchestrator.dispatch(session, "crea contrato para demo")
            assert_true(r1.get("state") == "AWAITING_CONTRATO_COLLECT", "Debe abrir flujo contrato")
            r2 = await orchestrator.dispatch(session, "olvidalo")
            assert_true(r2.get("state") == "idle", "Cancel debe cerrar contrato")
            assert_true("flow_mode" not in session, "Estado de contrato debe limpiarse")

        await run_case("2. Cancelar contrato a mitad", case_cancel_contract_mid)

        # 3) crear artículo sin caer en entidad
        async def case_article_not_entity() -> None:
            intent_map = {
                "dar de alta un artículo patch panel": {
                    "intent": "unknown",
                    "entities": {"descripcion": "Patch Panel", "referencia": "PP-24"},
                }
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            session = {}
            await orchestrator.dispatch(session, "dar de alta un artículo patch panel")
            assert_true(session.get("flow_mode") == "article", "No debe caer en entity")

        await run_case("3. Crear artículo sin caer en entidad", case_article_not_entity)

        # 4) double confirm preserva pending_delete
        async def case_double_confirm_preserves_pending() -> None:
            intent_map = {
                "borra factura 70001": {"intent": "delete_factura", "entities": {"pkey_factura": 70001}},
                "si": {"intent": "confirm", "entities": {}},
                "CONFIRMO": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_delete_fact = AsyncRecorder({"success": True})
            tool_registry.borrar_facturacion.execute = rec_delete_fact.execute

            session = {}
            await orchestrator.dispatch(session, "borra factura 70001")
            await orchestrator.dispatch(session, "si")
            assert_true(bool(session.get("pending_delete")), "Debe conservar pending_delete sin CONFIRMO exacto")
            await orchestrator.dispatch(session, "CONFIRMO")
            assert_true(rec_delete_fact.calls == 1, "Debe borrar solo tras CONFIRMO")

        await run_case("4. Double-confirm conserva pending_delete", case_double_confirm_preserves_pending)

        # 5) query/borrado factura coherentes tool<->connector
        async def case_factura_tools_connector_coherence() -> None:
            flags = {"obtener": 0, "borrar": 0}

            async def fake_obtener(pkey: int):
                flags["obtener"] += 1
                return {"mensaje": "OK", "lista": [{"PKEY": pkey}]}

            async def fake_borrar(pkey: int):
                flags["borrar"] += 1
                return {"mensaje": "OK", "lista": ""}

            fact_tools_module._connector.obtener_facturacion = fake_obtener
            fact_tools_module._connector.borrar_facturacion = fake_borrar

            r_query = await fact_tools_module.ObtenerFacturacionTool().execute({"pkey": 12345})
            r_del = await fact_tools_module.BorrarFacturacionTool().execute({"pkey": 12345})

            assert_true(flags["obtener"] == 1 and r_query.get("found"), "query_factura debe usar método real obtener_facturacion")
            assert_true(flags["borrar"] == 1 and r_del.get("success"), "delete_factura debe usar método real borrar_facturacion")

        await run_case("5. Query/Delete factura coherente", case_factura_tools_connector_coherence)

        # 6) PKEY directa conservadora en servicios/contratos/facturación
        async def case_direct_pkey_resolution() -> None:
            rec_service = AsyncRecorder({"success": True, "pkey": 90001})
            rec_contract = AsyncRecorder({"success": True, "pkey": 91001})
            rec_fact = AsyncRecorder({"success": True, "pkey": 92001})
            tool_registry.crear_servicio.execute = rec_service.execute
            tool_registry.crear_contrato.execute = rec_contract.execute
            tool_registry.grabar_facturacion.execute = rec_fact.execute

            intent_map = {
                "abre servicio para proveedor 12345": {
                    "intent": "open_task",
                    "entities": {"descripcion": "Visita técnica", "operario": "Juan"},
                },
                "crea contrato para pkey 22334": {
                    "intent": "create_contract",
                    "entities": {"descripcion": "Mantenimiento", "precio": 120},
                },
                "crea factura compra para proveedor 33445": {
                    "intent": "create_factura_compra",
                    "entities": {"descripcion": "Material", "total": 50.0},
                },
                "confirmo": {"intent": "confirm", "entities": {}},
                "ok": {"intent": "confirm", "entities": {}},
                "adelante": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent

            # Servicio por PKEY directa
            s1 = {}
            await orchestrator.dispatch(s1, "abre servicio para proveedor 12345")
            await orchestrator.dispatch(s1, "adelante")
            assert_true(rec_service.calls == 1, "Servicio debe resolver PKEY directa sin pedir nombre")

            # Contrato por PKEY directa
            s2 = {}
            await orchestrator.dispatch(s2, "crea contrato para pkey 22334")
            await orchestrator.dispatch(s2, "ok")
            assert_true(rec_contract.calls == 1, "Contrato debe resolver PKEY directa")

            # Facturación por PKEY directa
            s3 = {}
            await orchestrator.dispatch(s3, "crea factura compra para proveedor 33445")
            await orchestrator.dispatch(s3, "confirmo")
            assert_true(rec_fact.calls == 1, "Facturación debe resolver PKEY directa")

        await run_case("6. Uso de PKEY directa conservadora", case_direct_pkey_resolution)

        # 7) Modo determinista header+env con prioridad de header
        async def case_deterministic_mode_priority() -> None:
            os.environ["ECOFLOW_TEST_MODE"] = "raw"
            assert_true(resolve_test_mode(None) == "raw", "Env debe activar modo raw si no hay header")
            assert_true(resolve_test_mode("raw") == "raw", "Header raw debe activar raw")
            assert_true(resolve_test_mode("normal") == "normal", "Header debe tener prioridad sobre env")

        await run_case("7. Modo determinista (header > env)", case_deterministic_mode_priority)

        print("\nRESULTADO GLOBAL: PASS (7/7)")

    except Exception as exc:
        print(f"\nRESULTADO GLOBAL: FAIL -> {exc}")
        sys.exit(1)
    finally:
        if original_env_mode is None:
            os.environ.pop("ECOFLOW_TEST_MODE", None)
        else:
            os.environ["ECOFLOW_TEST_MODE"] = original_env_mode

        cognitive_service.parse_intent = original_parse_intent
        resolver.resolve_entity = original_resolve_entity
        tool_registry.crear_articulo.execute = originals["crear_articulo"]
        tool_registry.crear_contrato.execute = originals["crear_contrato"]
        tool_registry.crear_servicio.execute = originals["crear_servicio"]
        tool_registry.grabar_facturacion.execute = originals["grabar_facturacion"]
        tool_registry.obtener_facturacion.execute = originals["obtener_facturacion"]
        tool_registry.borrar_facturacion.execute = originals["borrar_facturacion"]
        fact_tools_module._connector.obtener_facturacion = originals["fact_connector_obtener"]
        fact_tools_module._connector.borrar_facturacion = originals["fact_connector_borrar"]


if __name__ == "__main__":
    asyncio.run(main())
