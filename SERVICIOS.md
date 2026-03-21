Manual Técnico API -`API_Servicios`
====================================

Plataforma: ecoSoftWEB\
Dominio de las peticiones:`https://www.ecosoftapi.net`

* * * * *

🧭 Visión General
-----------------

Esta API permite gestionar registros del móduloServicios, ofreciendo endpoints REST para:

- Crear nuevos servicios técnicos
- Modificarlos
- Eliminarlos
- Consultar su estado y detalles
- Registrar entradas de histórico para seguimiento
- Obtener registros específicos
- Obtener registros filtrados

La gestión de Tokens consumidos por la API dependerán del tamaño de la entrada de la solicitud o de la salida en función del tipo de petición. Los tokens mostrados en los ejemplos son valores aleatorios que no deben tomarse como ejemplos válidos de los valores retornados.

* * * * *

🔐 Autenticación
----------------

Tipo: Bearer Token personalizado\
Formato requerido:

```http
Authorization: Bearer <token_auth>.<token_usuario>

```

* * * * *

🔍 MODO_ID - Identificación de entidades
----------------------------------------

| `MODO_ID` | Método de identificación |
| --- | --- |
| `0` | Por código interno (PKEY) |
| `1` | Por identificador externo (CIF, DNI, etc.) |
| `2` | Por email (Debe ser único para evitar aleatoriedades) |

* * * * *

🔍 NIVELCONTROL - Tipo de registro
----------------------------------

| `NIVELCONTROL` | Tipo de registro |
| --- | --- |
| `0` | Cita comercial |
| `1` | Tarea |
| `2` | Tarea planner |
| `3` | Tarea de fabricación |

* * * * *

🔍 TIPOCONTACTO - Tipo de contacto del servicio
-----------------------------------------------

```text
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable. Asegúrese de que existe el tipo de contacto, ya que es un campo requerido para la carga del servicio. Si no existe la grabación fallará o no será visible en las pantallas de gestión.

```

* * * * *

🔍 ESTADO - Estado del servicio
-------------------------------

```text
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable. Asegúrese de que existe el estado, ya que es un campo requerido para la carga del servicio. Si no existe la grabación fallará o no será visible en las pantallas de gestión.

```

* * * * *

🔍 TIPO_SERVICIO - Tipo de servicio del registro
------------------------------------------------

```text
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable. Asegúrese de que existe el tipo, ya que es un campo requerido para la carga del servicio. Si no existe la grabación fallará o no será visible en las pantallas de gestión.

```

* * * * *

✅ Ejemplo de entrada de servicio con MODO_ID 1
----------------------------------------------

```json
{
  "PKEY": 0,    //SOLO PARA MODIFICACIONES (INDICAR REGISTRO A MODIFICAR)
  "MODO_ID": 1,
  "TIPO_SERVICIO": 2,
  "CLIENTE": "B12345678",
  "CLIENTE_DELEGACION": 1,
  "ESTADO": 1,
  "FECHA_INICIO": "2025-06-25T08:00:00",
  "FECHA_FIN": "2025-06-25T12:00:00",
  "SERVICIO_DESCRIPCION": "Revisión técnica anual del sistema de climatización",
  "OBSERVACIONES": "Sin incidencias",
  "OPERARIO": "11122333P",
  "OPERARIO_RECEPTOR": "11223344X",
  "SUCURSAL": "1",
  "REFERENCIA": "REV-CLIMA-2025-06",
  "NIVELCONTROL":1,
  "TIPOCONTACTO":1,
  "AUX1": "CLIMA",
  "AUX2": "EDIFICIO A",
  "AUX3": "PISO 2"
}

```

* * * * *

✅ Ejemplo de filtro de servicios con MODO_ID 1
----------------------------------------------

```json
{
    "MODO_ID": 1,
    "TIPO_SERVICIO":2,
    "CLIENTE": "B12345678",
    "CLIENTE_DELEGACION": "1",
    "ESTADO": 0,
    "FECHA_INICIO_SERVICIO_DESDE":"2000-01-01T08:00:00",
    "FECHA_INICIO_SERVICIO_HASTA":"2100-01-01T08:00:00",
    "FECHA_FIN_SERVICIO_DESDE":"2000-01-01T08:00:00",
    "FECHA_FIN_SERVICIO_HASTA":"2100-01-01T08:00:00",
    "SERVICIO_DESCRIPCION":"",
    "OBSERVACIONES":"",
    "OPERARIO":"",
    "OPERARIO_RECEPTOR":"",
    "SUCURSAL":1,
    "REFERENCIA":"",
    "NIVELCONTROL":1,
    "TIPOCONTACTO":1,
    "AUX1":"",
    "AUX2":"",
    "AUX3":""
}

```

* * * * *

✅ Ejemplo de entrada de linea de historial de un servicio con MODO_ID 1
-----------------------------------------------------------------------

```json
{
    "PKEY": 1,
    "LINEA": 3,
    "MODO_ID": 1,
    "DESCRIPCION": "Datos actualizados correctamente",
    "OBSERVACIONES": "Observaciones generadas automaticamente",
    "OPERARIO": "135465488E",
    "FECHA": "2025-06-25T08:00:00",
    "AUX1": "",
    "AUX2": "",
    "AUX3": ""
}

```

* * * * *

✅ Ejemplo de salida de linea de historial de un servicio
--------------------------------------------------------

```json
{
    "PKEY": 1,
    "TIPO_SERVICIO": 1,
    "TIPO_SERVICIO_DESCRIPCION": "SERVICIOS ESPECIALES",
    "SERVICIO_DESCRIPCION":"Servicio de prueba",
    "SERVICIO_DESCRIPCION_FIN":"Resulución del servicio",
    "FECHA_INICIO_SERVICIO":"2025-01-01T08:00:00",
    "FECHA_FIN_SERVICIO":"2025-01-01T08:00:00",
    "REFERENCIA":"REF-123456",
    "SUCURSAL":1,
    "SUCURSAL_DESCRIPCION":"Mi Empresa",
    "TIPO_CONTACTO":0,
    "OPERARIO_RECEPTOR":1,
    "OPERARIO_RECEPTOR_DESCRIPCION":"Luis Arias",
    "OPERARIO":1,
    "OPERARIO_DESCRIPCION":"Luis Arias",
    "CLIENTE":430256,
    "CLIENTE_DESCRIPCION":"Cliente S.A.",
    "CLIENTE_TELEFONO":"902565256",
    "CLIENTE_EMAIL":"cliente@cliente.es",
    "PERCEPTOR": 430256,
    "PERCEPTOR_DESCRIPCION":"Cliente S.A.",
    "PERCEPTOR_TELEFONO":"902565256",
    "PERCEPTOR_EMAIL":"cliente@cliente.es",
    "TEXTO_HISTORIAL":"Datos actualizados correctamente",
    "OBSERVACIONES_HISTORIAL":"Datos actualizados correctamente",
    "FECHA_HISTORIAL":"2025-01-01T08:00:00",
    "OPERARIO_HISTORIAL":1
}

```

* * * * *

✅ Ejemplo borrado, obtener registro de servicios u obtener registros de historico de un servicio
------------------------------------------------------------------------------------------------

```json
{
  "PKEY": 123
}

```

✅ Ejemplo borrado y obtener registro de histórico de servicios
--------------------------------------------------------------

```json
{
  "PKEY": 123,
  "LINEA": 1
}

```

📎 Endpoints REST y descripción de métodos
------------------------------------------

### `/API_Servicios/Index`

- Verifica disponibilidad de la API en navegador.
- Responde si está operativa.
- Obtiene esta documentación.
- Obtiene el token de autorización necesario para utilizar el API

### `GET /API_Servicios/eco?mensaje=Hola`

- Devuelve el texto recibido como eco.\
    Respuesta:`"OK, Hola"`

### `GET /API_Servicios/ecoJson?mensaje=Hola`

- Devuelve el mensaje en JSON.

```json
{ "mensaje": "Hola" }

```

### `POST /API_Servicios/grabarServicio`

- Graba un nuevo servicio técnico.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- En el JSON de entrada EXCLUIR el PKEY (Solo para identificar registros en modificaciones).
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "El cliente indicado no existe o no está activo" }

```

### `POST /API_Servicios/modificarServicio`

- Modifica un servicio existente.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Podemos cargar únicamente los campos de la entrada que queremos modificar y no especificar el resto.
- En el JSON de entrada INCLUIR el PKEY del registro que se desea modificar, el un campo requerido (sin el no se procesará la llamada).
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró un servicio con el código indicado" }

```

### `POST /API_Servicios/borrarServicio`

- Elimina un servicio por su`PKEY`.
- Utiliza el modelo JSON de borrado que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar: el servicio ya está cerrado" }

```

### `POST /API_Servicios/ObtenerServicio`

- Devuelve todos los datos de un servicio por su`PKEY`.
- Utiliza el modelo JSON de obtener registro que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado del registro obtenido como se puede ver en la respuesta a continuación.
- Informa de los tokens consumidos en la petición.

Entrada:

```json
{ "PKEY": 123 }

```

Respuesta OK:

```json
{
  "mensaje": "OK",
  "tokens": 13,
  "registros": 1,
  "lista": [
    {
      "PKEY": 123,
      "TIPO_SERVICIO": 2,
      "TIPO_SERVICIO_DESCRIPCION": "Mantenimiento preventivo",
      "SERVICIO_DESCRIPCION": "Revisión general anual de equipos",
      "SERVICIO_DESCRIPCION_FIN": "Mantenimiento finalizado correctamente",
      "FECHA_INICIO_SERVICIO": "2025-06-25T08:00:00",
      "FECHA_FIN_SERVICIO": "2025-06-25T12:00:00",
      "REFERENCIA": "REV-CLIMA-2025-06",
      "SUCURSAL": 1,
      "SUCURSAL_DESCRIPCION": "Oficina Central",
      "TIPO_CONTACTO": 3,
      "OPERARIO_RECEPTOR": 102,
      "OPERARIO_RECEPTOR_DESCRIPCION": "Ana García",
      "OPERARIO": 101,
      "OPERARIO_DESCRIPCION": "Juan Pérez",
      "CLIENTE": 2001,
      "CLIENTE_DESCRIPCION": "Empresa Clima S.A.",
      "CLIENTE_TELEFONO": "123456789",
      "CLIENTE_EMAIL": "contacto@clima.com",
      "PERCEPTOR": 501,
      "PERCEPTOR_DESCRIPCION": "Luis Torres",
      "PERCEPTOR_TELEFONO": "987654321",
      "PERCEPTOR_EMAIL": "l.torres@clima.com"
    }
  ]
}

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró ningún servicio con ese código" }

```

### `POST /API_Servicios/ObtenerServicios`

- Devuelve todos los datos de los servicios que cumplan las condiciones solicitadas.
- Utiliza el modelo JSON de filtrar registros que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultados listados en formato JSON.
- Informa de los tokens consumidos en la petición.
- Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena y fechas) o a -1 para valores numéricos.
- Si no se quiere especificar una entidad, utilizamos "-1" en el valor de campo cadena.
- Si no se especifica un modo de ID para las entidades se asumirá 0 (PKEY) como valor.

### `POST /API_Servicios/grabarHistorico`

- Añade una entrada de linea de historial a un servicio.
- Utiliza el modelo JSON de entrada de linea de historial que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Se debe informar del código de servicio al que se va a incorporar el historial.
- Informa del resultado con el código cargado en el registro grabado (LINEA).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 3, "registros": 1, "lista": "67890" }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede registrar histórico: servicio inexistente" }

```

* * * * *

### `POST /API_Servicios/ObtenerHistorico`

- Obtiene una linea de historial de un servicio junto con los datos básicos del mismo.
- Utiliza el modelo JSON de obtención de datos de linea de historial que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Se debe informar del código de servicio y la linea de historial para su obtención.
- La salida se formatea con el formato de salida de linea de historial.
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 3, "registros": 1, "lista": [DATOS DE SALIDA DE LINEA DE HISTORIAL] }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede obtener la linea de histórico: servicio inexistente" }

```

* * * * *

### `POST /API_Servicios/ObtenerHistorico_Servicio`

- Obtiene las lineas de historial de un servicio junto con los datos básicos del mismo.
- Utiliza el modelo JSON de obtención de datos de servicio (solo su PKEY) que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Se debe informar del código de servicio.
- La salida se formatea con el formato de salida de linea de historial con multiples registros de haberlos.
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 3, "registros": 1, "lista": {LISTA[DATOS DE SALIDA DE LINEA DE HISTORIAL] }

```

Respuesta ERROR:

```json
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede obtener la linea de histórico: servicio inexistente" }

```

* * * * *

### `POST /API_Servicios/modificarHistorico`

- Modifica una linea de historial de un servicio.
- Utiliza el modelo JSON de entrada de linea de historial que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado con el código cargado en el registro grabado (LINEA).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

### `POST /API_Servicios/borrarHistorico`

- Elimina una linea de historial de un servicio por su`PKEY`y su linea dentro del mismo.
- Utiliza el modelo JSON de borrado de datos de linea de historial que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Se debe informar del código de servicio y la linea de historial para su eliminación.
- Informa de los tokens consumidos en la petición.
- Informa del resultado con el código eliminado en el registro grabado (LINEA).

Respuesta OK:

```json
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

⚠️ Errores generales
--------------------

Token inválido:

```json
{ "mensaje": "ERROR", "resultado": "-1", "body": "Token faltante o mal formado" }

```

Error interno:

```json
{
  "mensaje": "ERROR",
  "resultado": "-1",
  "body": "Error en el procesamiento de la petición",
  "error": "excepción detallada (si aplica)"
}

```

* * * * *

✅ Recomendaciones finales
-------------------------

- Validar todos los datos antes de enviar.
- Leer siempre el campo`"lista"`en caso de error.
- Usar`MODO_ID = 1`con códigos externos como CIF/DNI.
- Incluir manejo de errores en clientes que consumen la API.
