Manual Técnico API -`API_Contratos`
====================================

Plataforma: ecoSoftWEB\
Dominio de las peticiones:`https://www.ecosoftapi.net`

* * * * *

🧭 Visión General
-----------------

Esta API permite gestionar registros del móduloContratos, ofreciendo endpoints REST para:

- Crear nuevos contratos para ecoSoftWeb
- Modificarlos
- Eliminarlos
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

🔍 MODO_ID - Identificación de entidades
----------------------------------------

```
| `MODO_ID_ENTIDAD` | Método de identificación                      |
|-----------|-------------------------------------------------------|
| `0`       | Por código interno (PKEY)                             |
| `1`       | Por identificador externo (CIF, DNI, etc.)            |
| `2`       | Por email (Debe ser único para evitar aleatoriedades) |

```

* * * * *

🔍 MODO_ID - Identificación de productos
----------------------------------------

```
| `MODO_ID_ARTICULO` | Método de identificación                   |
|--------------------|--------------------------------------------|
| `0`                | Por código interno (PKEY)                  |
| `1`                | Referencia                                 |
| `2`                | Modelo                                     |

```

* * * * *

🔍 MODO_ID - Identificación de proyectos
----------------------------------------

```
| `MODO_ID_PROYECTO` | Método de identificación                   |
|--------------------|--------------------------------------------|
| `0`                | Por código interno (PKEY)                  |
| `1`                | Código de proyectos                        |

```

* * * * *

✅ Ejemplo de entrada de contrato con MODO_ID 0
----------------------------------------------

```
{
  "PKEY": 0,
  "MODO_ID_ENTIDAD":0,
  "MODO_ID_ARTICULO":0,
  "MODO_ID_PROYECTO":0,
  "ENTIDAD":15,
  "ENTIDAD_PAGADORA":15,
  "ENTIDAD_ENDOSO":639,
  "ENTIDAD_ENVIO":2563,
  "SUCURSAL":1,
  "COMERCIAL":0,
  "PROYECTO":0,
  "ARTICULO":354,
  "DESCRIPCION": "Revisión técnica anual del sistema de climatización",
  "PRECIO_UNITARIO":10.25,
  "UNIDADES":1,
  "DTO":0,
  "FECHA_EMISION": "2025-06-25T12:00:00",
  "FECHA_FIN": "2025-06-25T12:00:00",
  "PERIODICIDAD":1,
  "ESTADO":0,
  "BLOQUE":1,
  "CODIGO_CONTRATO":"COD1235",
  "REFERENCIA": "REFCON-98565565",
  "OBSERVACIONES": "Revisar puntos habituales en los sistemas instados",
  "OBSERVACIONES_PRIVADAS": "Evitar sistemas en exteriores.",
  "TCOM_LINEA":1,
  "AUX1": "CLIMA",
  "AUX2": "EDIFICIO A",
  "AUX3": "PISO 2"
}

```

* * * * *

✅ Ejemplo filtrado de contratos MODO ID 0
-----------------------------------------

```

{
  "PKEY": 0,
  "MODO_ID_ENTIDAD": 0,
  "MODO_ID_ARTICULO": 0,
  "MODO_ID_PROYECTO": 0,
  "ENTIDAD": 0,
  "ENTIDAD_PAGADORA": 0,
  "ENTIDAD_ENDOSO": 0,
  "ENTIDAD_ENVIO": 0,
  "SUCURSAL": 1,
  "COMERCIAL": 0,
  "PROYECTO": 0,
  "ARTICULO": 0,
  "DESCRIPCION": "",
  "PRECIO_UNITARIO_DESDE": 0.00,
  "PRECIO_UNITARIO_HASTA": 999999999.00,
  "UNIDADES_DESDE": 0,
  "UNIDADES_HASTA": 999999999,
  "DTO": 0.00,
  "FECHA_EMISION_DESDE": "2010-06-25T12:00:00",
  "FECHA_EMISION_HASTA": "2100-06-25T12:00:00",
  "FECHA_FIN_DESDE": "2010-06-25T12:00:00",
  "FECHA_FIN_HASTA": "2100-06-25T12:00:00",
  "PERIODICIDAD": 0,
  "ESTADO": 0,
  "BLOQUE": 0,
  "CODIGO_CONTRATO": "",
  "REFERENCIA": "",
  "OBSERVACIONES": "",
  "OBSERVACIONES_PRIVADAS": "",
  "TCOM_LINEA": 0,
  "SERIE": "",
  "AUX1": "",
  "AUX2": "",
  "AUX3": ""
}

```

✅ Ejemplo borrado y obtener registro de contratos
-------------------------------------------------

```
{
  "PKEY": 123
}

```

📎 Endpoints REST y descripción de métodos
------------------------------------------

### `/API_Contratos/Index`

- Verifica disponibilidad de la API en navegador.
- Responde si está operativa.
- Obtiene esta documentación.
- Obtiene el token de autorización necesario para utilizar el API

### `GET /API_Contratos/eco?mensaje=Hola`

- Devuelve el texto recibido como eco.\
    Respuesta:`"OK, Hola"`

### `GET /API_Contratos/ecoJson?mensaje=Hola`

- Devuelve el mensaje en JSON.

```
{ "mensaje": "Hola" }

```

### `POST /API_Contratos/grabarContrato`

- Graba un nuevo contrato.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
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

### `POST /API_Contratos/modificarContrato`

- Modifica un contrato existente.
- Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró un contrato con el código indicado" }

```

### `POST /API_Contratos/borrarContrato`

- Elimina un contrato por su`PKEY`.
- Utiliza el modelo JSON de borrado que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultado con el código cargado en el registro grabado (PKEY).
- Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar: el contrato no existe" }

```

### `POST /API_Contratos/ObtenerContrato`

- Devuelve todos los datos de un contrato por su`PKEY`.
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
      "PKEY": 123,
      "ENTIDAD": 2,
      "ENTIDAD_DES": "MiCliente S.L.",
      "ENTIDAD_PAGADORA": 3,
      "ENTIDAD_PAGADORA_DES":"MiCliente2 S.L.",
      "ENTIDAD_ENDOSO": 4,
      "ENTIDAD_ENDOSO_DES":"MiCliente3 S.L.",
      "ENTIDAD_ENVIO": 1,
      "SUCURSAL":1,
      "SUCURSAL_DES":"MiEmpresa S.A.",
      "COMERCIAL":0,
      "PROYECTO":1,
      "ARTICULO":6,
      "DESCRIPCION": "Mantenimiento preventivo",
      "PRECIO_UNITARIO":10.50,
      "UNIDADES":1,
      "DTO":0,
      "FECHA_EMISION":"2025-06-25T12:00:00",
      "FECHA_FIN":"2025-06-25T12:00:00",
      "PERIODICIDAD":1,
      "ESTADO":0,
      "BLOQUE":1,
      "CODIGO_CONTRATO":"CODCON001",
      "REFERENCIA":"REF001",
      "OBSERVACIONES":"Revisar puntos habituales en los sistemas instados",
      "OBSERVACIONES_PRIVADAS":"Evitar sistemas en exteriores.",
      "TCOM_LINEA":1;
      "AUX1":"";
      "AUX2":"";
      "AUX3":"";
    }
  ]
}

```

### `POST /API_Servicios/ObtenerContratos`

- Devuelve todos los datos de los servicios que cumplan las condiciones solicitadas.
- Utiliza el modelo JSON de filtrar registros que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
- Informa del resultados listados en formato JSON, igual que la obtención individual, pero en formato de lista JSON.
- Informa de los tokens consumidos en la petición.
- Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena) o a 0 o -1 para valores numéricos.
- Las fechas en formato desde hasta si no se quiere especificar un rango, se darán valores que comprendan todos los servicios. En el ejemplo se utilizan 2000 a 2100 como años que contemplan todos los registros.

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
