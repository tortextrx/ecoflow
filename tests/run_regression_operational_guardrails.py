import asyncio
import sys
from typing import Any, Dict, Callable

from app.services.orchestrator import UnifiedOrchestrator
from app.services.orchestrator import cognitive_service, resolver, tool_registry


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
    original_detect_duplicates = resolver.detect_entity_duplicates

    originals = {
        "crear_entidad": tool_registry.crear_entidad.execute,
        "obtener_servicio": tool_registry.obtener_servicio.execute,
        "grabar_historico": tool_registry.grabar_historico.execute,
        "crear_articulo": tool_registry.crear_articulo.execute,
    }

    try:
        # 1) alta mínima vs guiada entidad
        async def case_entity_min_vs_guided() -> None:
            intent_map = {
                "alta cliente acme cif b12345678": {
                    "intent": "create_entity",
                    "entities": {"nombre_cliente": "ACME", "cif": "B12345678", "tipo_entidad": "CLIENTE"},
                },
                "CONFIRMO INCOMPLETA": {"intent": "unknown", "entities": {}},
                "ok": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                return {"status": "NOT_FOUND"}

            async def fake_detect_duplicates(name=None, cif=None, allowed_types=None):
                return {"status": "NOT_FOUND", "options": []}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity
            resolver.detect_entity_duplicates = fake_detect_duplicates

            rec_create = AsyncRecorder({"success": True, "pkey": 11001})
            tool_registry.crear_entidad.execute = rec_create.execute

            session = {}
            r1 = await orchestrator.dispatch(session, "alta cliente acme cif b12345678")
            assert_true("Recomendado completar ficha" in r1.get("reply", ""), "Debe activar alta guiada")

            r2 = await orchestrator.dispatch(session, "CONFIRMO INCOMPLETA")
            assert_true(r2.get("state") == "AWAITING_ENTITY_CONFIRM", "Tras confirmar incompleta debe pasar a confirmación final")

            r3 = await orchestrator.dispatch(session, "ok")
            assert_true(r3.get("state") == "idle", "Debe permitir alta mínima tras confirmación fuerte")
            assert_true(rec_create.calls == 1, "Debe grabar exactamente una vez")

        await run_case("1. Entidad alta mínima vs guiada", case_entity_min_vs_guided)

        # 2) detección duplicados entidad
        async def case_entity_duplicates() -> None:
            intent_map = {
                "alta proveedor acme cif b12345678": {
                    "intent": "create_entity",
                    "entities": {
                        "nombre_cliente": "ACME",
                        "cif": "B12345678",
                        "tipo_entidad": "PROVEEDOR",
                        "direccion": "Calle A",
                        "poblacion": "Oviedo",
                        "provincia": "Asturias",
                        "cp": "33001",
                        "telefono": "600111222",
                        "email": "acme@acme.es",
                    },
                },
                "CONFIRMO NUEVA": {"intent": "unknown", "entities": {}},
                "ok": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                return {"status": "NOT_FOUND"}

            calls = {"dup": 0}

            async def fake_detect_duplicates(name=None, cif=None, allowed_types=None):
                calls["dup"] += 1
                return {
                    "status": "POSSIBLE_DUPLICATE",
                    "options": [{"pkey": 7001, "nombre": "ACME", "cif": "B12345678"}],
                }

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity
            resolver.detect_entity_duplicates = fake_detect_duplicates

            rec_create = AsyncRecorder({"success": True, "pkey": 11002})
            tool_registry.crear_entidad.execute = rec_create.execute

            session = {}
            r1 = await orchestrator.dispatch(session, "alta proveedor acme cif b12345678")
            assert_true("Posibles duplicados" in r1.get("reply", ""), "Debe advertir duplicados")

            await orchestrator.dispatch(session, "CONFIRMO NUEVA")
            await orchestrator.dispatch(session, "ok")

            assert_true(calls["dup"] >= 1, "Debe ejecutar chequeo de duplicados")
            assert_true(rec_create.calls == 1, "Debe permitir continuar solo tras confirmación fuerte")

        await run_case("2. Duplicados de entidad", case_entity_duplicates)

        # 3) tipología correcta + 4) país por defecto + 5) observaciones solo explícitas
        async def case_entity_payload_flags() -> None:
            intent_map = {
                "alta proveedor netplus cif b99887766": {
                    "intent": "create_entity",
                    "entities": {
                        "nombre_cliente": "NetPlus",
                        "cif": "B99887766",
                        "tipo_entidad": "PROVEEDOR",
                        "direccion": "Polígono X",
                        "poblacion": "Gijón",
                        "provincia": "Asturias",
                        "cp": "33201",
                        "telefono": "699000111",
                        "email": "compras@netplus.es",
                    },
                },
                "ok": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                return {"status": "NOT_FOUND"}

            async def fake_detect_duplicates(name=None, cif=None, allowed_types=None):
                return {"status": "NOT_FOUND", "options": []}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity
            resolver.detect_entity_duplicates = fake_detect_duplicates

            rec_create = AsyncRecorder({"success": True, "pkey": 11003})
            tool_registry.crear_entidad.execute = rec_create.execute

            session = {}
            await orchestrator.dispatch(session, "alta proveedor netplus cif b99887766")
            await orchestrator.dispatch(session, "ok")

            p = rec_create.last_payload or {}
            assert_true(p.get("PROVEEDOR") == 1 and p.get("CLIENTE") == 0, "Debe respetar tipología proveedor")
            assert_true(p.get("PAIS") == 1, "PAIS por defecto debe ser 1")
            assert_true("OBSERVACIONES" not in p, "No debe inyectar observaciones automáticas")

        await run_case("3-5. Tipología, país y observaciones", case_entity_payload_flags)

        # 6) operario ambiguo en servicio
        async def case_service_ambiguous_operario() -> None:
            intent_map = {
                "abre servicio para demo operario juan": {
                    "intent": "open_task",
                    "entities": {"nombre_cliente": "Demo", "descripcion": "Revisión anual"},
                }
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                if allowed_types == ["USUARIO", "P_LABORAL"]:
                    return {
                        "status": "AMBIGUOUS",
                        "options": [
                            {"pkey": 9101, "nombre": "Juan García", "cif": ""},
                            {"pkey": 9102, "nombre": "Juan Pérez", "cif": ""},
                        ],
                    }
                if name == "Demo":
                    return {"status": "RESOLVED", "data": {"pkey": 23154, "nombre": "Demo", "cif": ""}}
                return {"status": "NOT_FOUND"}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity

            session = {}
            r = await orchestrator.dispatch(session, "abre servicio para demo operario juan")
            assert_true(r.get("state") == "AWAITING_DISAMBIGUATION", "Operario ambiguo debe pedir selección")

        await run_case("6. Operario ambiguo en servicio", case_service_ambiguous_operario)

        # 7) histórico limpio
        async def case_history_clean() -> None:
            async def fake_parse_intent(message: str, _: str):
                return {"intent": "add_history", "entities": {"pkey_servicio": 12345}}

            cognitive_service.parse_intent = fake_parse_intent

            rec_get_service = AsyncRecorder({"success": True, "data": {"OPERARIO": 9101}})
            rec_hist = AsyncRecorder({"success": True})
            tool_registry.obtener_servicio.execute = rec_get_service.execute
            tool_registry.grabar_historico.execute = rec_hist.execute

            session = {}
            await orchestrator.dispatch(session, "mete una línea de historial que diga que el cliente anula el servicio 12345")
            saved = (rec_hist.last_payload or {}).get("DESCRIPCION", "")
            assert_true("mete una" not in saved.lower(), "No debe guardar la orden literal")
            assert_true("cliente anula" in saved.lower(), "Debe conservar el contenido útil")

        await run_case("7. Historial limpio", case_history_clean)

        # 8) artículo guiado familia/proveedor
        async def case_article_guided() -> None:
            intent_map = {
                "crear articulo cable cat6": {
                    "intent": "create_article",
                    "entities": {"descripcion": "Cable Cat6", "referencia": "CAT6"},
                }
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent

            session = {}
            r = await orchestrator.dispatch(session, "crear articulo cable cat6")
            assert_true("Recomendado completar" in r.get("reply", ""), "Debe sugerir familia y proveedor")

        await run_case("8. Artículo alta guiada", case_article_guided)

        # 9) proveedor ambiguo en artículo
        async def case_article_ambiguous_provider() -> None:
            intent_map = {
                "crear articulo switch proveedor net": {
                    "intent": "create_article",
                    "entities": {"descripcion": "Switch", "referencia": "SW-1"},
                }
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                if allowed_types == ["PROVEEDOR"]:
                    return {
                        "status": "AMBIGUOUS",
                        "options": [
                            {"pkey": 501, "nombre": "Net Distribución", "cif": "A111"},
                            {"pkey": 502, "nombre": "Net Soluciones", "cif": "A222"},
                        ],
                    }
                return {"status": "NOT_FOUND"}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity

            session = {}
            r = await orchestrator.dispatch(session, "crear articulo switch proveedor net")
            assert_true(r.get("state") == "AWAITING_DISAMBIGUATION", "Proveedor ambiguo debe pedir selección")

        await run_case("9. Proveedor ambiguo en artículo", case_article_ambiguous_provider)

        # 10) resolución segura global en referencias ambiguas
        async def case_safe_resolution_query() -> None:
            intent_map = {
                "consulta cliente demo": {"intent": "query_entity", "entities": {"nombre_cliente": "Demo"}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                return {
                    "status": "POSSIBLE_DUPLICATE",
                    "options": [
                        {"pkey": 1, "nombre": "Demo Norte", "cif": "B100"},
                        {"pkey": 2, "nombre": "Demo Sur", "cif": "B200"},
                    ],
                }

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity

            session = {}
            r = await orchestrator.dispatch(session, "consulta cliente demo")
            assert_true(r.get("state") == "AWAITING_DISAMBIGUATION", "Referencias ambiguas deben resolverse con selección")

        await run_case("10. Resolución segura en ambigüedad", case_safe_resolution_query)

        # 11) duplicado por nombre antes de pedir CIF
        async def case_entity_name_duplicate_precheck() -> None:
            intent_map = {
                "dar de alta entidad": {"intent": "create_entity", "entities": {}},
                "Perico Delgado": {"intent": "unknown", "entities": {}},
                "Efectivamente, ya está dada de alta": {"intent": "unknown", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                if name == "Perico Delgado":
                    return {
                        "status": "POSSIBLE_DUPLICATE",
                        "options": [{"pkey": 43010001, "nombre": "Perico Delgado", "cif": "B12345678"}],
                    }
                return {"status": "NOT_FOUND"}

            async def fake_detect_duplicates(name=None, cif=None, allowed_types=None):
                return {"status": "NOT_FOUND", "options": []}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity
            resolver.detect_entity_duplicates = fake_detect_duplicates

            session = {}
            await orchestrator.dispatch(session, "dar de alta entidad")
            r = await orchestrator.dispatch(session, "Perico Delgado")
            assert_true("posibles coincidencias por nombre" in r.get("reply", "").lower(), "Debe prevenir duplicado por nombre antes del CIF")

            r2 = await orchestrator.dispatch(session, "Efectivamente, ya está dada de alta")
            assert_true(r2.get("state") == "idle", "Confirmación natural debe cerrar alta nueva")
            assert_true("no doy de alta" in r2.get("reply", "").lower() or "ya existe" in r2.get("reply", "").lower(), "Debe confirmar que no crea duplicado")

        await run_case("11. Duplicado por nombre pre-CIF", case_entity_name_duplicate_precheck)

        # 12) cancelación con mensaje limpio no técnico
        async def case_cancel_clean_message() -> None:
            intent_map = {
                "dar de alta entidad": {"intent": "create_entity", "entities": {}},
                "cancela": {"intent": "cancel", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            cognitive_service.parse_intent = fake_parse_intent

            session = {}
            await orchestrator.dispatch(session, "dar de alta entidad")
            r = await orchestrator.dispatch(session, "cancela")
            low = r.get("reply", "").lower()
            assert_true("operación cancelada" in low, "Debe confirmar cancelación")
            assert_true("idle" not in low and "flujo" not in low, "No debe exponer detalles técnicos internos")

        await run_case("12. Cancelación con mensaje limpio", case_cancel_clean_message)

        # 13) no tiene email no bloquea y dirección no guarda basura
        async def case_semantic_fields_no_email() -> None:
            intent_map = {
                "dar de alta entidad": {"intent": "create_entity", "entities": {}},
                "Instalaciones Martinez QA": {"intent": "unknown", "entities": {}},
                "78978978A": {"intent": "unknown", "entities": {}},
                "La dirección es, calle falsa numero 10. En oviedo, asturias. El teléfono es 654654658": {"intent": "unknown", "entities": {}},
                "El codigo postal es 33054. No tiene email": {"intent": "unknown", "entities": {}},
                "ok": {"intent": "confirm", "entities": {}},
            }

            async def fake_parse_intent(message: str, _: str):
                return intent_map.get(message, {"intent": "unknown", "entities": {}})

            async def fake_resolve_entity(name=None, cif=None, context_pk=None, allowed_types=None):
                return {"status": "NOT_FOUND"}

            async def fake_detect_duplicates(name=None, cif=None, allowed_types=None):
                return {"status": "NOT_FOUND", "options": []}

            cognitive_service.parse_intent = fake_parse_intent
            resolver.resolve_entity = fake_resolve_entity
            resolver.detect_entity_duplicates = fake_detect_duplicates

            rec_create = AsyncRecorder({"success": True, "pkey": 11099})
            tool_registry.crear_entidad.execute = rec_create.execute

            session = {}
            await orchestrator.dispatch(session, "dar de alta entidad")
            await orchestrator.dispatch(session, "Instalaciones Martinez QA")
            await orchestrator.dispatch(session, "78978978A")
            await orchestrator.dispatch(session, "La dirección es, calle falsa numero 10. En oviedo, asturias. El teléfono es 654654658")
            r5 = await orchestrator.dispatch(session, "El codigo postal es 33054. No tiene email")
            assert_true("faltan" not in r5.get("reply", "").lower() or "email" not in r5.get("reply", "").lower(), "No debe bloquear por email explícitamente ausente")
            if r5.get("state") != "idle":
                await orchestrator.dispatch(session, "ok")

            p = rec_create.last_payload or {}
            assert_true(p.get("DIRECCION", "").lower() == "calle falsa numero 10", "Dirección debe limpiarse correctamente")
            assert_true(p.get("POBLACION", "").lower() == "oviedo", "Población debe extraerse")
            assert_true(p.get("PROVINCIA", "").lower() == "asturias", "Provincia debe extraerse")
            assert_true(p.get("TLF1", "") == "654654658", "Teléfono debe extraerse")
            assert_true(p.get("CP", "") == "33054", "CP debe extraerse")
            assert_true("EMAIL" not in p, "Email no informado explícitamente no debe forzarse")

        await run_case("13. Extracción semántica + no email", case_semantic_fields_no_email)

        print("\nRESULTADO GLOBAL: PASS (13/13)")

    except Exception:
        print("\nRESULTADO GLOBAL: FAIL")
        sys.exit(1)
    finally:
        cognitive_service.parse_intent = original_parse_intent
        resolver.resolve_entity = original_resolve_entity
        resolver.detect_entity_duplicates = original_detect_duplicates
        tool_registry.crear_entidad.execute = originals["crear_entidad"]
        tool_registry.obtener_servicio.execute = originals["obtener_servicio"]
        tool_registry.grabar_historico.execute = originals["grabar_historico"]
        tool_registry.crear_articulo.execute = originals["crear_articulo"]


if __name__ == "__main__":
    asyncio.run(main())

