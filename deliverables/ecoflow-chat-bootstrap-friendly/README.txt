ecoFlow Bootstrap-friendly package

Contenido:
- bootstrap-chat.html
- ecoflow-bootstrap.css
- ecoflow-bootstrap.js
- avatar.png
- ecoScanCalidad.png

Objetivo:
- Versión visualmente equivalente a ecoFlow pero más integrable en entornos Bootstrap.
- Sin dependencia del CSS global del proyecto original.
- Pensada para sidebar, offcanvas o card embebida dentro de ecoSoftWEB.

Integración:
- El JS envía a /api/ecoflow/chat por defecto.
- Si el endpoint está en otra ruta o dominio, definir:
  window.ECOFLOW_API_BASE = 'https://tu-dominio-o-base'
  antes de cargar ecoflow-bootstrap.js

Sugerencia:
- Integrar primero esta versión dentro de un contenedor Bootstrap del ERP.
- Compararla con el paquete original y decidir cuál encaja mejor.
