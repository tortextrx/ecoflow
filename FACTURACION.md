🧭 Visión General
-----------------

Esta API permite gestionar registros del móduloFacturacion, ofreciendo endpoints REST para:

-   Crear nuevos documentos de facturacion
-   Modificarlos
-   Eliminarlos
-   Consultar su estado y detalles
-   Obtener registros específicos
-   Obtener registros filtrados
-   Solo se pueden gestionar los documentos listados en el apartado "NIVELCONTROL".
-   No pueden crearse facturas de venta ni facturas simplificadas. Si se pueden crear prefacturas de venta.

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

🔍 MODO_ID_ENTIDAD - Identificación de entidades
------------------------------------------------

```
| `MODO_ID` | Método de identificación                   |
|-----------|--------------------------------------------|
| `0`       | Por código interno (PKEY)                  |
| `1`       | Por identificador externo (CIF, DNI, etc.) |
| `2`       | Por correo electrónico (debe ser único)    |

```

* * * * *

🔍 MODO_ID_ARTICULO - Identificación de productos
-------------------------------------------------

```
| `MODO_ID` | Método de identificación                   |
|-----------|--------------------------------------------|
| `0`       | Por código interno (PKEY)                  |
| `1`       | Referencia                                 |
| `2`       | Modelo                                     |

```

* * * * *

🔍 NIVELCONTROL - Identificación de tipo de documento
-----------------------------------------------------

```
| `NIVELCONTROL` | Tipo de documento                          |
|----------------|--------------------------------------------|
| `1`	         | PRESUPUESTO DE COMPRA                      |
| `2`	         | PEDIDO DE COMPRA                           |
| `3`	         | PEDIDO DE REPOSICION DE COMPRA             |
| `4`	         | ALBARAN DE COMPRA                          |
| `5`	         | FACTURA DE COMPRA                          |
| `6`	         | FACTURA DE GASTO                           |
| `10`	         | PRESUPUESTO DE VENTA                       |
| `11`	         | PEDIDO DE VENTA                            |
| `12`	         | ALBARAN DE VENTA                           |
| `13`	         | FACTURAS DE VENTA                          |
| `17`	         | PREFACTURA DE VENTA                        |
| `20`	         | FACTURA SIMPLIFICADA                       |
| `40`	         | SALIDA PREVIA                              |
| `41`	         | INVENTARIO TOTAL                           |
| `42`	         | INVENTARIO PARCIAL                         |
| `43`	         | INVENTARIO AUTOMTICO                       |
| `44`	         | SALIDA DE MERCANCIA                        |
| `45`	         | ENTRADA DE MERCANCIA                       |
| `46`	         | DEVOLUCION A FABRICA                       |
| `47`	         | AJUSTE DE STOCK NEGATIVO                   |
| `48`	         | AJUSTE DE STOCK POSITIVO                   |
| `49`	         | INVENTARIO TRANSFORMACION                  |

```

* * * * *

✅ Ejemplo de entrada de facturacion con MODO_ID_ENTIDAD 0
---------------------------------------------------------

```
{
  "Cabecera": {
    "MODO_ID_ENTIDAD": 0,
    "SUCURSAL": "1",
    "SUCURSAL_ENVIO": "2",
    "ENTIDAD": "25",
    "ENTIDAD_ENDOSO": "",
    "ENTIDAD_ENVIO": "C002",
    "AGENTE": 1,
    "PERIODICIDAD": 1,
    "FORMAPAGO": 2,
    "REFERENCIA": "FAC-2025-0001",
    "SERIE": "A",
    "FECHA": "2025-09-11T00:00:00",
    "NIVELCONTROL": 12,
    "OBSERVACIONES": "Factura de septiembre",
    "AUX1": "",
    "AUX2": "",
    "AUX3": ""
  },
  "Detalle": [
    {
      "MODO_ID_ARTICULO": 1,
      "ARTICULO": "PROD001",
      "DESCRIPCION": "Producto de prueba 1",
      "PRECIO_UNITARIO": 50.0,
      "UNIDADES": 2,
      "DTO": 0,
      "AUX1": "",
      "AUX2": "",
      "AUX3": ""
    },
    {
      "MODO_ID_ARTICULO": 1,
      "ARTICULO": "PROD002",
      "DESCRIPCION": "Producto de prueba 2",
      "PRECIO_UNITARIO": 100.0,
      "UNIDADES": 1,
      "DTO": 10.0,
      "AUX1": "",
      "AUX2": "",
      "AUX3": ""
    }
  ]
}

```

* * * * *

✅ Ejemplo de entrada de facturacionlineas con MODO_ID 1
-------------------------------------------------------

```
{
    "PKEY": 6598,
    "LINEA": 1,
    "MODO_ID_ARTICULO": 1,
    "ARTICULO": "PROD001",
    "DESCRIPCION": "Producto de prueba 1",
    "PRECIO_UNITARIO": 50.0,
    "UNIDADES": 2,
    "DTO": 0,
    "AUX1": "",
    "AUX2": "",
    "AUX3": ""
}

```

* * * * *

✅ Ejemplo de salida de facturacionlineas
----------------------------------------

```
{
    "PKEY": "2569",
    "LINEA": "2",
    "CODART": "2456",
    "DESCRIPCION": "",
    "MODELO": "",
    "COLOR": "",
    "REFERENCIA": "",
    "PUNI": "5",
    "TALLA": "",
    "TOTAL": "2",
    "TOTALNETO": "12.1",
    "IMPORTE": "10",
    "ESCANDALLO": "0",
    "DOC_ER": "0",
    "MULTITALLA": "0",
    "PRECIOSTALLAS": "0",
    "DTO": "0",
    "TOTALBASEIMP": "10",
    "TALLAJE": "0",
    "GESTIONSTOCK": "1",
    "MARCA": "5",
    "FAMILIA": "21",
    "VISIBLE": "1",
    "COSTE1": "3.2",
    "TOTALBRUTO": "10",
    "USALOTES": "0",
    "AUX1": "",
    "AUX2": "",
    "AUX3": ""
}

```

* * * * *

✅ Ejemplo de filtro/obtener registros de Facturacion con MODO_ID 0
------------------------------------------------------------------

```
{
    "MODO_ID_ENTIDAD": 0,
    "SUCURSAL":1,
    "SUCURSAL_ENVIO":0,
    "ENTIDAD":0,
    "ENTIDAD_ENDOSO":0,
    "ENTIDAD_ENVIO":0,
    "AGENTE":0,
    "PERIODICIDAD":0,
    "FORMAPAGO":0,
    "REFERENCIA":"",
    "SERIE":"",
    "CODOPERACION":0,
    "FECHA_DESDE":"2025-01-01T00:00:00",
    "FECHA_HASTA":"2025-12-31T00:00:00",
    "NIVELCONTROL":13,
    "OBSERVACIONES":"",
    "AUX1":"",
    "AUX2":"",
    "AUX3":""
}

```

* * * * *

✅ Ejemplo borrado y obtener registro de facturación
---------------------------------------------------

```
{
  "PKEY": 123
}

```

✅ Ejemplo borrado y obtener registro de lineas de facturación
-------------------------------------------------------------

```
{
  "PKEY": 123,
  "LINEA": 1
}

```

📎 Endpoints REST y descripción de métodos
------------------------------------------

### `/API_Facturacion/Index`

-   Verifica disponibilidad de la API en navegador.
-   Responde si está operativa.
-   Obtiene esta documentación.
-   Obtiene el token de autorización necesario para utilizar el API

### `GET /API_Facturacion/eco?mensaje=Hola`

-   Devuelve el texto recibido como eco.\
    Respuesta:`"OK, Hola"`

### `GET /API_Facturacion/ecoJson?mensaje=Hola`

-   Devuelve el mensaje en JSON.

```
{ "mensaje": "Hola" }

```

### `POST /API_Facturacion/grabarFacturacion`

-   Graba un nuevo registro de facturación.
-   Utiliza el modelo JSON de entrada de facturación que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Se graba la cabecera de la factura y las lineas de la misma.
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "El cliente indicado no existe o no está activo" }

```

### `POST /API_Facturacion/grabarFacturacionLinea`

-   Graba un nuevo registro de facturación.
-   Utiliza el modelo JSON de entrada de facturación líneas que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY,LINEA).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "El cliente indicado no existe o no está activo" }

```

### `POST /API_Facturacion/modificarFacturacion`

-   Modifica un registro de facturación existente.
-   Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró un documento con el código indicado" }

```

### `POST /API_Facturacion/borrarFacturacion`

-   Elimina un documento de facturacion por su`PKEY`.
-   No se pueden eliminar facturas ni facturas simplificadas.
-   Utiliza el modelo JSON de borrado que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar el documento" }

```

### `POST /API_Facturacion/borrarFacturacionLineas`

-   Elimina un documento de facturacion por su`PKEY`y`LINEA`.
-   Utiliza el modelo JSON de borrado de lineas que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar el documento" }

```

### `POST /API_Facturacion/ObtenerFacturacion`

-   Devuelve todos los datos de un facturacion por su`PKEY`.
-   Utiliza el modelo JSON de obtener registro que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado del registro obtenido como se puede ver en la respuesta a continuación.
-   Informa de los tokens consumidos en la petición.

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
            "PKEY":12546,
		    "SUCURSAL":1,
		    "SUCURSAL_DES":"Empresa Ejemplo",
		    "SUCURSAL_ENVIO":0,
		    "ENTIDAD":430256,
		    "ENTIDAD_DES":"Cliente de prueba",
		    "ENTIDAD_ENDOSO":0,
		    "ENTIDAD_ENDOSO_DES":"",
		    "ENTIDAD_ENVIO":0,
		    "PERIODICIDAD":3,
		    "PERIODICIDAD_DES":"30,60,90",
		    "FORMAPAGO":2,
		    "FORMAPAGO_DES":"DOMICILIACIÓN",
		    "REFERENCIA":"REF_001",
		    "SERIE":"A",
		    "CODOPERACION":20250002536",
		    "FECHA":2025-01-01T00:00:00"
		    "NIVELCONTROL":13,
		    "OBSERVACIONES":"",
            "AUX1": "",
            "AUX2": "",
            "AUX3": ""
          }
      ]
}

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró ningún documento con ese código" }

```

### `POST /API_Facturacion/ObtenerFacturaciones`

-   Devuelve todos los datos de facturacion que cumplan las condiciones solicitadas.
-   Utiliza el modelo JSON de filtrar registros que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultados listados en formato JSON.
-   Informa de los tokens consumidos en la petición.
-   Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena) o a 0 o -1 para valores numéricos.
-   Las fechas en formato desde hasta si no se quiere especificar un rango, se darán valores que comprendan todos los Facturacion. En el ejemplo se utilizan 2000 a 2100 como años que contemplan todos los registros.

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

### `POST /API_Facturacion/ObtenerFacturacionLineas`

-   Devuelve todos los datos de lineas un documento de facturacion por su`PKEY`.
-   Utiliza el modelo JSON de obtener factura que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultados listados en formato JSON.
-   Informa de los tokens consumidos en la petición.
-   Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena) o a 0 o -1 para valores numéricos.
-   Las fechas en formato desde hasta si no se quiere especificar un rango, se darán valores que comprendan todos los Facturacion. En el ejemplo se utilizan 2000 a 2100 como años que contemplan todos los registros.

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

### `POST /API_Facturacion/ObtenerFacturacionLinea`

-   Devuelve los datos de la linea un documento de facturacion por su`PKEY`y`LINEA`.
-   Utiliza el modelo JSON de obtener registros de linea que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultados listados en formato JSON.
-   Informa de los tokens consumidos en la petición.

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

-   Validar todos los datos antes de enviar.
-   Leer siempre el campo`"lista"`en caso de error.
-   Usar`MODO_ID = 1`con códigos externos como CIF/DNI.
-   Incluir manejo de errores en clientes que consumen la API.