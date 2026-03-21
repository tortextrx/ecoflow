# Arquitectura de ecoFlow

ecoFlow es un asistente inteligente de gestión conectado mediante API a ecoSoftWEB (ERP).

## Componentes Principales

1. **Orquestador (Orchestrator)**: Es el "cerebro" central que gestiona el flujo de la conversación, el estado de la sesión y la llamada a las herramientas funcionales.
2. **Servicio Cognitivo (Cognitive Service)**: Capa de IA (GPT-4o) que traduce el lenguaje natural del usuario en intenciones (intents) y entidades (entities) estructuradas.
3. **Resolver**: Lógica de negocio encargada de "aterrizar" nombres humanos a identificadores únicos (PKEYs) del ERP mediante búsquedas flexibles.
4. **Herramientas (Tools)**: Unidades funcionales que ejecutan acciones reales (crear cliente, grabar servicio, registrar gasto).
5. **Conectores (Connectors)**: Capa de bajo nivel que habla con la API de ecoSoftWEB manejando autenticación y trazas.

## Flujo Lógico

```text
[Usuario] --(Chat/WhatsApp)--> [Orquestador]
                                     |
                                     v
                          [Servicio Cognitivo] (Detectar intención)
                                     |
                                     v
                                 [Resolver] (Asignar PKEYs)
                                     |
                                     v
                        [Herramientas / Tools] (Ejecutar acción)
                                     |
                                     v
                                [Conectores] --(API)--> [ERP]
                                     |
                                     v
[Usuario] <--(Respuesta)------ [Orquestador]
```
