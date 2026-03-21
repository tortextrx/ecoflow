Manual Técnico API -`API_Entidades`
====================================

Plataforma: ecoSoftWEB\
Dominio de las peticiones:`https://www.ecosoftapi.net/`

* * * * *

🧭 Visión General
-----------------

Esta API permite gestionar registros del móduloEntidades, ofreciendo endpoints REST para:

- Crear nuevas Entidades para ecoSoftWeb
- Modificarlas
- Eliminarlas
- Consultar su estado y detalles
- Obtener registros específicos

La gestión de Tokens consumidos por la API dependerán del tamaño de la entrada de la solicitud o de la salida en función del tipo de petición. Los tokens mostrados en los ejemplos son valores aleatorios que no deben tomarse como ejemplos válidos de los valores retornados.

* * * * *

🔐 Autenticación
----------------

Tipo: Bearer Token personalizado\
Formato requerido:

```
Authorization: Bearer <token_auth>.<token_usuario>

```

* * * * *

🔍 ESTADO - Estado del registro de entidad
------------------------------------------

| `ESTADO` | Descripción del estado |
| --- | --- |
| `0` | ACTIVO |
| `1` | BAJA |
| `2` | PENDIENTE |
| `3` | BAJA TEMPORAL |

* * * * *

🔍 ACTIVIDAD - Actividad asignada a la entidad
----------------------------------------------

```
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable en cada base de datos. Asegúrate de que existe la actividad, ya que aunque no es un campo requerido para la
carga de la entidad, puede ser necesario que exista para algunos listados o utilidades de ecoSoftWEB.
Intenta cargar siempre la actividad que mejor describa a la entidad en la rama más baja de la
estructura (padres-hijos). Si no sabemos la actividad más adecuada, en caso de duda, enviar 0 para
valor por defecto.

```

* * * * *

🔍 GRUPO - Grupo asignado a la entidad
--------------------------------------

```
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable por la
empresa de la base de datos. Asegúrate de que existe el grupo, ya que es un campo que se utiliza muy
habitualmente en la gestión de la entidad. Si no existe, la grabación se realizará, pero puede perder
información en listados y gestiones con las entidades.
Intenta cargar siempre el grupo que mejor describa a la entidad en la rama más baja de la estructura de grupos.
Se carga el grupo principal, no se tienen en cuenta grupos adicionales.
El filtro de entidades (obtenerEntidades) se tienen en cuenta grupos adicionales.
Si no sabemos el grupo más adecuada, en caso de duda enviar 0 para valor por defecto.

```

* * * * *

🔍 ZONA - Zona asignada a la entidad
------------------------------------

```
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable.
Asegúrate de que existe la zona, ya que aunque no es un campo requerido para la carga de la entidad,
si no existe no será visible en listados y gestiones relacionadas con la entidad y su zona.
Intenta cargar siempre la zona que mejor encaje con la entidad.
Si no sabemos la zona más adecuada, en caso de duda enviar 0 para valor por defecto.

```

* * * * *

🔍 PAISES - Pais de la entidad
------------------------------

```
La numeración depende de cada código cargado en ecoSoftWeb ya que es dinamico y personalizable.
Asegúrate de que existe el país, ya que aunque no es un campo requerido para la carga de la entidad,
si no existe no será visible en listados y gestiones relacionadas con la entidad.
Intenta cargar siempre la zona que mejor encaje con la entidad.
Si no sabemos un pais adecuado, en caso de duda enviar 0 para valor por defecto.

```

* * * * *

🔍 SUCURSAL VS SUCURSALES
-------------------------

```
El campo SUCURSAL representa el código de entidad (almacen, tienda, empresa...) que estará asociada con la entidad. En ecoFlow se fija por defecto en 1 (sucursal principal) para mantener consistencia operativa.
El campo SUCURSALES identifica que el registro que deseamos insertar, editar, obtener o filtrar es una sucursal (0 para no, 1 para si)

```

* * * * *

🔍 CLIENTE, PROVEEDOR, ACREEDOR, USUARIO, PREENTIDAD, RESIDENTE (Perceptor), SUCURSALES, P_LABORAL (Personal laboral de la empresa), REPRESENTANTE, PERITO y DISTRIBUIDOR
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------

```
Los campos listados marcan si la entidad es lo que representa la variable (1 para SI y 0 para NO). Una entidad puedes tener más de un atributo a la vez, por ejemplo ser cliente y perceptor o acreedor y proveedor.

```

* * * * *

✅ Ejemplo de entrada
--------------------

```
{
    "PKEY":1,  //SOLO PARA MODIFICACIONES (INDICAR REGISTRO A MODIFICAR)
    "ESTADO":0,
    "SUCURSAL":1,
    "DENCOM":"ECOSOFT CONSULTING",
    "DENFIS":"ECOSOFT CONSULTING S.L.",
    "NOMBRE":"",
    "APELLIDO1":"",
    "APELLIDO2":"",
    "DIRECCION":"MARQUES DE VIDAL 5",
    "POBLACION":"OVIEDO",
    "PROVINCIA":"ASTURIAS",
    "CP":"33005",
    "CIF":"B335656558",
    "TLF1":"985256545",
    "TLF2":"",
    "TLF3":"",
    "TLF4":"",
    "EMAIL":"ECOSOFT@ECOSOFT.ES",
    "WWW":"WWW.ECOSOFT.ES",
    "OBSERVACIONES":"",
    "PAIS":1,
    "RE":0,
    "ACTIVIDAD":1,
    "FNAC":"1999-06-25T12:00:00",
    "GRUPO":1,
    "ZONA":0,
    "CLIENTE":1,
    "PROVEEDOR":0,
    "ACREEDOR":0,
    "USUARIO":0,
    "PREENTIDAD":0,
    "RESIDENTE":0,
    "SUCURSALES":0,
    "P_LABORAL":0,
    "REPRESENTANTE":0,
    "PERITO":0,
    "DISTRIBUIDOR":0,
    "CCCLIENTE":"",
    "CCPROVEEDOR":"",
    "CCACREEDOR":"",
    "CCVENTA":"",
    "CCCOMPRA":"",
    "CCGASTO":"",
    "RETENCION":0,
    "AUX1":"",
    "AUX2":"",
    "AUX3":""
}

```

* * * * *

✅ Ejemplo de Filtro
-------------------

```
{
    "ESTADO":0,
    "SUCURSAL":1,
    "DENCOM":"ECOSOFT CONSULTING",
    "DENFIS":"ECOSOFT CONSULTING S.L.",
    "NOMBRE":"",
    "APELLIDO1":"",
    "APELLIDO2":"",
    "DIRECCION":"MARQUES DE VIDAL 5",
    "POBLACION":"OVIEDO",
    "PROVINCIA":"ASTURIAS",
    "CP":"33005",
    "CIF":"B335656558",
    "TLF1":"985256545",
    "TLF2":"",
    "TLF3":"",
    "TLF4":"",
    "EMAIL":"ECOSOFT@ECOSOFT.ES",
    "WWW":"WWW.ECOSOFT.ES",
    "OBSERVACIONES":"",
    "PAIS":1,
    "RE":0,
    "ACTIVIDAD":1,
    "FNAC_DESDE":"1999-06-25T12:00:00",
    "FNAC_HASTA":"2026-06-25T12:00:00",
    "FALTA_DESDE":"1999-06-25T12:00:00",
    "FALTA_HASTA":"2026-06-25T12:00:00",
    "FBAJA_DESDE":"1999-06-25T12:00:00",
    "FBAJA_HASTA":"2026-06-25T12:00:00",
    "GRUPO":1,
    "ZONA":0,
    "CLIENTE":1,
    "PROVEEDOR":0,
    "ACREEDOR":0,
    "USUARIO":0,
    "PREENTIDAD":0,
    "RESIDENTE":0,
    "SUCURSALES":0,
    "P_LABORAL":0,
    "REPRESENTANTE":0,
    "PERITO":0,
    "DISTRIBUIDOR":0,
    "CCCLIENTE":"",
    "CCPROVEEDOR":"",
    "CCACREEDOR":"",
    "CCVENTA":"",
    "CCCOMPRA":"",
    "CCGASTO":"",
    "RETENCION":0,
    "AUX1":"",
    "AUX2":"",
    "AUX3":""
}

```

* * * * *

✅ Ejemplo borrado y obtener registro de Entidades
-------------------------------------------------

```
{
  "PKEY": 123
}

```

📎 Endpoints REST y descripción de métodos
------------------------------------------

### `/API_Entidades/Index`

- Verifica disponibilidad de la API en navegador.
- Responde si está operativa.
- Obtiene esta documentación.
- Obtiene el token de autorización necesario para utilizar el API.

### `GET /API_Entidades/eco?mensaje=Hola`

- Devuelve el texto recibido como eco.\
    Respuesta:`"OK, Hola"`

### `GET /API_Entidades/ecoJson?mensaje=Hola`

- Devuelve el mensaje en JSON.

```
{ "mensaje": "Hola" }

```

### `POST /API_Entidades/grabarEntidad`

- Graba una nueva entidad.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- En el JSON de entrada EXCLUIR el PKEY (Solo para identificar registros en modificaciones).
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "El cliente indicado no existe o no está activo" }

```

### `POST /API_Entidades/modificarEntidad`

- Modifica una entidad existente.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- En el JSON de entrada INCLUIR el PKEY del registro que se desea modificar.
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró una entidad con el código indicado" }

```

### `POST /API_Entidades/borrarEntidad`

- Elimina una entidad por su`PKEY`.
- Utiliza el modelo JSON de borrado que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar: la entidad no existe" }

```

### `POST /API_Entidades/ObtenerEntidad`

- Devuelve todos los datos de una entidad por su`PKEY`.
- Utiliza el modelo JSON de obtener registro que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado del registro obtenido como se puede ver en la respuesta a continuación.
- Informa de los tokens consumidos en la petición.

Entrada:

```
{ "PKEY": 123 }

```

Respuesta OK:

```
{
  "mensaje": "OK",
  "tokens": 13,
  "registros": 1,
  "lista": [
    {
        "PKEY":1,
        "ESTADO":0,
        "SUCURSAL":1,
        "DENCOM":"ECOSOFT CONSULTING",
        "DENFIS":"ECOSOFT CONSULTING S.L.",
        "NOMBRE":"",
        "APELLIDO1":"",
        "APELLIDO2":"",
        "DIRECCION":"c\ MARQUES DE VIDAL 5",
        "POBLACION":"OVIEDO",
        "PROVINCIA":"ASTURIAS",
        "CP":"33005",
        "CIF":"B335656558",
        "TLF1":"985256545",
        "TLF2":"",
        "TLF3":"",
        "TLF4":"",
        "EMAIL":"ECOSOFT@ECOSOFT.ES",
        "WWW":"WWW.ECOSOFT.ES",
        "OBSERVACIONES":"",
        "PAIS":1,
        "RE":0,
        "ACTIVIDAD":1,
        "FNAC":"1999-06-25T12:00:00",
        "GRUPO":1,
        "ZONA":0,
        "CCCLIENTE":"",
        "CCPROVEEDOR":"",
        "CCACREEDOR":"",
        "CCVENTA":"",
        "CCCOMPRA":"",
        "CCGASTO":"",
        "RETENCION":0,
        "AUX1":"",
        "AUX2":"",
        "AUX3":""
    }
  ]
}

```

### `POST /API_Entidades/ObtenerEntidades`

- Devuelve todos los datos de las entidades que cumplan las condiciones solicitadas.
- Utiliza el modelo JSON de entrada de registros que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultados listados en formato JSON.
- Informa de los tokens consumidos en la petición.
- Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena) o a 0 o -1 para valores numéricos.
- Las fechas en formato desde hasta si no se quiere especificar un rango, se darán valores que comprendan todas las entidades. En el ejemplo se utilizan 2000 a 2100 como años que contemplan todos los registros.

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró ningún contrato con ese código" }

```

⚠️ Errores generales
--------------------

Token inválido:

```
{ "mensaje": "ERROR", "resultado": "-1", "body": "Token faltante o mal formado" }

```

Error interno:

```
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
