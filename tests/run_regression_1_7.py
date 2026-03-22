import asyncio
import sys
from typing import Any, Dict, Callable

from app.services.orchestrator import UnifiedOrchestrator
from app.services.orchestrator import cognitive_service, resolver, tool_registry
from app.connectors.facturacion import FacturacionConnector


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
    try:
        await fn()
        print(f"[PASS] {name}")
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        raise


async def main() -> None:
    orchestrator = UnifiedOrchestrator()

    original_parse_intent = cognitive_service.parse_intent
    original_resolve_entity = resolver.resolve_entity

    originals = {
        "crear_articulo": tool_registry.crear_articulo.execute,
        "crear_servicio": tool_registry.crear_servicio.execute,
        "grabar_facturacion": tool_registry.grabar_facturacion.execute,
        "borrar_servicio": tool_registry.borrar_servicio.execute,
        "borrar_entidad": tool_registry.borrar_entidad.execute,
        "connector_grabar_facturacion": FacturacionConnector.grabar_facturacion,
    }

    async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
        if context_pk:
            return {"status": "RESOLVED", "data": {"pkey": int(context_pk), "nombre": f"Entidad {context_pk}", "cif": ""}}
        if name or cif:
            return {"status": "RESOLVED", "data": {"pkey": 23154, "nombre": name or "Entidad Demo", "cif": cif or ""}}
        return {"status": "NOT_FOUND"}

    resolver.resolve_entity = fake_resolve_entity

    try:
        # 1) cancel global
        async def case_cancel_global() -> None:
            intent_map = {
                "crea un cliente llamado acme": {"intent": "create_entity", "entities": {"nombre_cliente": "ACME"}},
                "olvídalo": {"intent": "unknown", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            session = {}

            r1 = await orchestrator.dispatch(session, "crea un cliente llamado acme")
            assert_true(r1.get("state") == "AWAITING_ENTITY_CONFIRM", "Debe abrir flujo de entidad")
            assert_true(session.get("flow_mode") == "entity", "flow_mode debe ser entity")

            r2 = await orchestrator.dispatch(session, "olvídalo")
            assert_true(r2.get("state") == "idle", "Cancel global debe devolver idle")
            assert_true("flow_mode" not in session, "Cancel global debe limpiar flow_mode")
            assert_true("flow_data" not in session, "Cancel global debe limpiar flow_data")

        await run_case("1. Cancel global", case_cancel_global)

        # 2) double-confirm robusto
        async def case_double_confirm() -> None:
            intent_map = {
                "borra el servicio 32100": {"intent": "delete_service", "entities": {"pkey_servicio": 32100}},
                "si": {"intent": "confirm", "entities": {}},
                "CONFIRMO": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_delete_service = AsyncRecorder({"success": True})
            tool_registry.borrar_servicio.execute = rec_delete_service.execute

            session = {}
            r1 = await orchestrator.dispatch(session, "borra el servicio 32100")
            assert_true(r1.get("state") == "AWAITING_DELETE_CONFIRM", "Debe entrar en doble confirmación")
            assert_true(bool(session.get("pending_delete")), "Debe persistir pending_delete")

            r2 = await orchestrator.dispatch(session, "si")
            assert_true(r2.get("state") == "AWAITING_DELETE_CONFIRM", "Sin CONFIRMO exacto no debe borrar")
            assert_true(bool(session.get("pending_delete")), "No debe perderse pending_delete")
            assert_true(rec_delete_service.calls == 0, "No debe ejecutar borrado aún")

            r3 = await orchestrator.dispatch(session, "CONFIRMO")
            assert_true(r3.get("state") == "idle", "Tras CONFIRMO y éxito debe volver a idle")
            assert_true("pending_delete" not in session, "Debe limpiar pending_delete solo tras éxito")
            assert_true(rec_delete_service.calls == 1, "Debe ejecutar borrado exactamente una vez")

        await run_case("2. Double-confirm robusto", case_double_confirm)

        # 3) delete_entity end-to-end
        async def case_delete_entity_e2e() -> None:
            intent_map = {
                "borra la entidad 44556": {"intent": "delete_entity", "entities": {"pkey_entidad": 44556}},
                "CONFIRMO": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_delete_entity = AsyncRecorder({"success": True})
            tool_registry.borrar_entidad.execute = rec_delete_entity.execute

            session = {}
            await orchestrator.dispatch(session, "borra la entidad 44556")
            await orchestrator.dispatch(session, "CONFIRMO")
            assert_true(rec_delete_entity.calls == 1, "delete_entity debe pasar por tool real de borrado")
            assert_true(rec_delete_entity.last_payload == {"pkey": 44556}, "delete_entity debe enviar PKEY correcto")

        await run_case("3. delete_entity end-to-end", case_delete_entity_e2e)

        # 4) routing artículo vs entidad
        async def case_routing_articulo() -> None:
            intent_map = {
                "dar de alta un artículo cable cat6": {
                    "intent": "unknown",
                    "entities": {"descripcion": "Cable Cat6", "referencia": "CAT6-2M"},
                }
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            session = {}
            r = await orchestrator.dispatch(session, "dar de alta un artículo cable cat6")

            assert_true(session.get("flow_mode") == "article", "No debe caer en entity; debe enrutar a article")
            assert_true(r.get("state") == "AWAITING_ARTICULO_COLLECT", "Debe quedarse en collect/confirm de artículo")

        await run_case("4. Routing artículo vs entidad", case_routing_articulo)

        # 5) flujo multi-turno artículo
        async def case_article_multiturn() -> None:
            intent_map = {
                "crear artículo switch 24 puertos": {
                    "intent": "create_article",
                    "entities": {"descripcion": "Switch 24 puertos", "referencia": "SW24"},
                },
                "confirmo incompleta": {"intent": "unknown", "entities": {}},
                "ok": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_create_article = AsyncRecorder({"success": True, "pkey": 88888})
            tool_registry.crear_articulo.execute = rec_create_article.execute

            session = {}
            r1 = await orchestrator.dispatch(session, "crear artículo switch 24 puertos")
            assert_true(r1.get("state") == "AWAITING_ARTICULO_COLLECT", "Debe pedir confirmación guiada en flujo artículo")
            r2 = await orchestrator.dispatch(session, "confirmo incompleta")
            assert_true(r2.get("state") == "AWAITING_ARTICULO_COLLECT", "Tras confirmación fuerte de incompleta debe quedar listo para confirmar")
            r3 = await orchestrator.dispatch(session, "ok")
            assert_true(r3.get("state") == "idle", "Tras confirmar artículo debe cerrar en idle")
            assert_true(rec_create_article.calls == 1, "Debe ejecutar creación de artículo una vez")
            assert_true("flow_mode" not in session and "flow_data" not in session, "Debe limpiar estado de flujo artículo")

        await run_case("5. Multi-turno artículo", case_article_multiturn)

        # 6) facturación unificada sin llamadas inconsistentes
        async def case_facturacion_unificada() -> None:
            intent_map = {
                "crea factura compra demo": {
                    "intent": "create_factura_compra",
                    "entities": {"nombre_cliente": "Demo", "descripcion": "Mantenimiento mensual", "total": 100.0},
                },
                "confirmo": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_fact = AsyncRecorder({"success": True, "pkey": 70001})
            tool_registry.grabar_facturacion.execute = rec_fact.execute

            async def forbidden_connector_call(self, payload: dict):
                raise RuntimeError("NO_DIRECT_CONNECTOR_CALL")

            FacturacionConnector.grabar_facturacion = forbidden_connector_call

            session = {}
            r1 = await orchestrator.dispatch(session, "crea factura compra demo")
            assert_true(r1.get("state") == "AWAITING_FACTURA_COLLECT", "Debe entrar en flujo de facturación")
            r2 = await orchestrator.dispatch(session, "confirmo")
            assert_true(r2.get("state") == "idle", "Tras confirmar facturación debe cerrar en idle")
            assert_true(rec_fact.calls == 1, "Debe usar un único camino vía tool de facturación")

        await run_case("6. Facturación unificada", case_facturacion_unificada)

        # 7) no regresión básica de servicios
        async def case_servicios_basico() -> None:
            intent_map = {
                "abre servicio para demo operario juan": {
                    "intent": "open_task",
                    "entities": {"nombre_cliente": "Demo", "descripcion": "Revisión trimestral", "operario": "Juan"},
                },
                "adelante": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent
            rec_service = AsyncRecorder({"success": True, "pkey": 90001})
            tool_registry.crear_servicio.execute = rec_service.execute

            session = {}
            r1 = await orchestrator.dispatch(session, "abre servicio para demo operario juan")
            assert_true(r1.get("state") == "AWAITING_SERVICE_CONFIRM", "Servicio debe entrar en confirm")
            r2 = await orchestrator.dispatch(session, "adelante")
            assert_true(r2.get("state") == "idle", "Servicio confirmado debe cerrar en idle")
            assert_true(rec_service.calls == 1, "Debe crear servicio una sola vez")

        await run_case("7. No regresión básica de servicios", case_servicios_basico)

        print("\nRESULTADO GLOBAL: PASS (7/7)")

    except Exception:
        print("\nRESULTADO GLOBAL: FAIL")
        sys.exit(1)
    finally:
        cognitive_service.parse_intent = original_parse_intent
        resolver.resolve_entity = original_resolve_entity
        tool_registry.crear_articulo.execute = originals["crear_articulo"]
        tool_registry.crear_servicio.execute = originals["crear_servicio"]
        tool_registry.grabar_facturacion.execute = originals["grabar_facturacion"]
        tool_registry.borrar_servicio.execute = originals["borrar_servicio"]
        tool_registry.borrar_entidad.execute = originals["borrar_entidad"]
        FacturacionConnector.grabar_facturacion = originals["connector_grabar_facturacion"]


if __name__ == "__main__":
    asyncio.run(main())
