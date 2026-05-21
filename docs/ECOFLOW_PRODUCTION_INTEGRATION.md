# Guía de Integración ecoFlow (Producción)

Este documento describe el contrato de API para integrar el widget de chat de ecoFlow en ecoSoftWEB u otras aplicaciones autorizadas.

## 1. Endpoint
**POST** `https://ecobot.es/api/ecoflow/chat`

## 2. Autenticación y Seguridad
ecoFlow utiliza un sistema de **doble cabecera** para separar la seguridad de acceso de la identidad operativa.

### A) Seguridad de Acceso (ecoFlow)
Obligatorio para autorizar la petición.
*   **Header**: `Authorization`
*   **Formato**: `Bearer <ECOFLOW_SECURITY_TOKEN>`
*   **Propósito**: Valida que la llamada proviene de una instancia autorizada de ecoSoftWEB.
*   **Qué pedir**: Solicita al administrador de ecoFlow el `ECOFLOW_SECURITY_TOKEN`.

### B) Identidad Operativa (ecoSoftWEB ERP)
Obligatorio para que ecoFlow pueda operar con los datos del ERP.
*   **Header**: `X-EcoSoft-Authorization`
*   **Formato**: `Bearer <TOKEN_REAL_ECOSOFTWEB>`
*   **Propósito**: Identifica la base de datos, empresa y usuario. ecoFlow reenvía este token en cada llamada al ERP.
*   **Nota**: ecoFlow trata este token como una cadena opaca. No intentes trocearlo.

## 3. Formato de Petición (Request)
*   **Content-Type**: `multipart/form-data` o `application/x-www-form-urlencoded`
*   **Campos**:
    *   `session_id` (obligatorio): String alfanumérico (max 100). Identifica la sesión de chat.
    *   `message` (opcional): Texto del usuario.
    *   `file` (opcional): Archivo adjunto (JPEG, PNG, PDF, max 10MB).

### Ejemplo con cURL
```bash
curl -X POST "https://ecobot.es/api/ecoflow/chat" \
  -H "Authorization: Bearer <TU_TOKEN_SEGURIDAD>" \
  -H "X-EcoSoft-Authorization: Bearer <TOKEN_ERP_USUARIO>" \
  -F "session_id=chat_user_001" \
  -F "message=Hola, ¿puedes buscar al cliente Javier?"
```

## 4. Respuestas y Errores
*   **200 OK**: Petición procesada. Devuelve JSON con `reply` y `state`.
*   **401 Unauthorized**: Token de seguridad de ecoFlow ausente o incorrecto.
*   **400 Bad Request**: Falta el header `X-EcoSoft-Authorization` o el `session_id` tiene formato inválido.

## 5. Mejores Prácticas
*   No compartas el `ECOFLOW_SECURITY_TOKEN` en el frontend público de forma visible.
*   Usa siempre `https` para proteger ambos tokens.
*   El `session_id` debe ser persistente durante la conversación para mantener el contexto.
