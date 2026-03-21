Manual Técnico API -`API_Articulos`
====================================

Plataforma: ecoSoftWEB\
Dominio de las peticiones:`https://www.ecosoftapi.net`

* * * * *

🧭 Visión General
-----------------

Esta API permite gestionar registros del móduloArtículos, ofreciendo endpoints REST para:

-   Crear nuevos Artículos para ecoSoftWeb
-   Modificarlos
-   Eliminarlos
-   Consultar su estado y detalles
-   Obtener registros específicos
-   Crea el producto/servicio con precios de compra y venta a 0 y con el tipo de IVA por definir.

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

🔍 NIVELCONTROL - Tipo de producto/artículo/servicio
----------------------------------------------------

```
| `NIVELCONTROL` | Método de identificación del tipo de producto                                    |
|----------------|----------------------------------------------------------------------------------|
| `1`            | Producto/artículo, bien comercial que vendemos o compramos.                      |
| `2`            | Conceptos de ingresos y gastos relacionados con la gestión del negocio           |

```

* * * * *

🔍 CONTROLSTOCK - El software controla el stock del producto
------------------------------------------------------------

```
| `CONTROLSTOCK` | Control de stock                                                                 |
|----------------|----------------------------------------------------------------------------------|
| `0`            | NO controla el stock. Productos que no queremos controlar su stock               |
| `1`            | SI controla el stock. Productos que desemanos controlar su stock                 |

```

* * * * *

🔍 MULTITALLA - El software controla el stock del producto por TALLAS/TAMAÑOS
-----------------------------------------------------------------------------

```
| `MULTITALLA` | Tipo de producto según tiene talla/tamaños o si es talla/tamaño única/o o no tiene |
|--------------|------------------------------------------------------------------------------------|
| `0`          | NO tiene tallas/tamaños. Productos o servicios en general                          |
| `1`          | SI tiene tallas/tamaños. Productos de moda/calzado o que tienen tamaños diferentes |

```

* * * * *

🔍 PRECIOSTALLAS - El software controla los precios en función de la talla/tamaño del producto
----------------------------------------------------------------------------------------------

```
| `PRECIOSTALLAS` | Controla si el producto tiene diferentes precios por talla/tamaño               |
|-----------------|---------------------------------------------------------------------------------|
| `0`             | NO controla los precios por tamaño/talla. Precios únicos.                       |
| `1`             | SI tiene diferentes precios por tamaño/talla. Ej. moda y calzado infantil       |

```

* * * * *

🔍 ESTADO - Estado del producto dentro del software
---------------------------------------------------

```
| `ESTADO`       | Estado del producto                                                              |
|----------------|----------------------------------------------------------------------------------|
| `0`            | ACTIVO, puede utilizarse con normalidad                                          |
| `1`            | BAJA, según parametros este producto/servicio ya no se puede usar en el ciclo    |
| `2`            | PENDIENTE, aún no está activo pero no está de baja. Está en espera de ACTIVO     |

```

* * * * *

✅ Ejemplo de entrada de artículo
--------------------------------

```
{
    "REFERENCIA":"REF0001",
    "DESCRIPCION":"Producto de prueba",
    "MODELO":"MOD1011",
    "COLOR":0,
    "TALLAJE":0,
    "PROVEEDOR":5236,
    "MARCA":2,
    "FAMILIA":1,
    "ESTADO":0,
    "CONTROLSTOCK":1,
    "PRECIOSTALLAS":0,
    "OBSERVACIONES":"Producto para elaborar pruebas de ...",
    "MULTITALLA":0,
    "NIVELCONTROL":1,
    "STOCKMAXIMO":0,
    "STOCKMINIMO":0,
    "METAS":"",
    "MOSTRARWEB":1,
    "USALOTES":0,
    "USANUMSERIE":0,
    "DESCRIPCION_CORTA":"",
    "AUX1":"",
    "AUX2":"",
    "AUX3":""
}

```

* * * * *

✅ Ejemplo borrado y obtener registro de artículos
-------------------------------------------------

```
{
  "PKEY": 123
}

```

📎 Endpoints REST y descripción de métodos
------------------------------------------

### `/API_Articulos/Index`

-   Verifica disponibilidad de la API en navegador.
-   Responde si está operativa.
-   Obtiene esta documentación.
-   Obtiene el token de autorización necesario para utilizar el API

### `GET /API_Articulos/eco?mensaje=Hola`

-   Devuelve el texto recibido como eco.\
    Respuesta:`"OK, Hola"`

### `GET /API_Articulos/ecoJson?mensaje=Hola`

-   Devuelve el mensaje en JSON.

```
{ "mensaje": "Hola" }

```

### `POST /API_Articulos/grabarArticulo`

-   Graba un nuevo artículo.
-   Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "El cliente indicado no existe o no está activo" }

```

### `POST /API_Articulos/modificarArticulo`

-   Modifica un artículo existente.
-   Utiliza el modelo JSON de entrada que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró un artículo con el código indicado" }

```

### `POST /API_Articulos/borrarArticulo`

-   Elimina un artículo por su`PKEY`.
-   Utiliza el modelo JSON de borrado que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultado con el código cargado en el registro grabado (PKEY).
-   Informa de los tokens consumidos en la petición.

Respuesta OK:

```
{ "mensaje": "OK", "tokens": 1, "registros": 1, "lista": "12345" }

```

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se puede eliminar: el artículo no existe" }

```

### `POST /API_Articulos/ObtenerArticulo`

-   Devuelve todos los datos de un artículo por su`PKEY`.
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
        "PKEY": 123,
        "REFERENCIA":"REF0001",
        "DESCRIPCION":"Producto de prueba",
        "MODELO":"MOD1011",
        "COLOR":0,
        "TALLAJE":0,
        "PROVEEDOR":5236,
        "MARCA":2,
        "FAMILIA":1,
        "ESTADO":0,
        "CONTROLSTOCK":1,
        "PRECIOSTALLAS":0,
        "OBSERVACIONES":"Producto para elaborar pruebas de ...",
        "MULTITALLA":0,
        "NIVELCONTROL":1,
        "STOCKMAXIMO":0,
        "STOCKMINIMO":0,
        "METAS":"",
        "MOSTRARWEB":1,
        "USALOTES":0,
        "USANUMSERIE":0,
        "DESCRIPCION_CORTA":"",
        "AUX1":"",
        "AUX2":"",
        "AUX3":""
    }
  ]
}

```

### `POST /API_Servicios/ObtenerArticulos`

-   Devuelve todos los datos de los servicios que cumplan las condiciones solicitadas.
-   Utiliza el modelo JSON de filtrar registros que debe enviarse como parte de la petición como una cadena de texto como contenido de la petición.
-   Informa del resultados listados en formato JSON.
-   Informa de los tokens consumidos en la petición.
-   Si no se quiere especificar un dato del filtro se dejará en blanco (variables de cadena) o a 0 o -1 para valores numéricos.
-   Las fechas en formato desde hasta si no se quiere especificar un rango, se darán valores que comprendan todos los servicios. En el ejemplo se utilizan 2000 a 2100 como años que contemplan todos los registros.

Respuesta ERROR:

```
{ "mensaje": "ERROR", "registros": 1, "lista": "No se encontró ningún artículo con ese código" }

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

-   Validar todos los datos antes de enviar.
-   Leer siempre el campo`"lista"`en caso de error.
-   Usar`MODO_ID = 1`con códigos externos como CIF/DNI.
-   Incluir manejo de errores en clientes que consumen la API.