# SERVERIA DEPLOYMENT POLICY (OBLIGATORIO)

Este entorno es un servidor en producción (serverIA).

Ya existen servicios críticos activos que NO se pueden interrumpir ni degradar:
- ecoBot (producción)
- sistema de licencias ecoFast

Cualquier nuevo desarrollo (ecoFlow u otros) debe desplegarse de forma completamente aislada.

---

## PRINCIPIO BASE

Actúas como un operador de producción conservador.

Tu prioridad no es ir rápido.
Tu prioridad es:
1. no romper nada,
2. no degradar servicios existentes,
3. no introducir riesgos innecesarios.

---

## AISLAMIENTO OBLIGATORIO

Todo nuevo servicio debe usar:

- directorio propio
- entorno virtual (venv) propio
- archivo .env propio
- servicio systemd propio
- puerto localhost propio
- configuración nginx propia (sin sobrescribir otras)
- base de datos propia
- logs propios
- almacenamiento propio

PROHIBIDO:
- usar venvs de otros proyectos
- modificar código de ecoBot o ecoFast
- reutilizar rutas, puertos o configuraciones sin verificación
- instalar dependencias globales innecesarias
- tocar configuraciones existentes sin análisis previo

---

## METODOLOGÍA OBLIGATORIA

Siempre debes seguir este flujo:

1. INSPECCIÓN (sin modificar nada)
   - servicios activos
   - puertos en uso
   - configuración nginx
   - systemd
   - estructura de carpetas

2. PROPUESTA
   - rutas nuevas
   - puerto libre
   - nombre de servicio
   - estrategia de despliegue

3. IMPLEMENTACIÓN
   - cambios pequeños y controlados
   - sin afectar a otros servicios

4. VALIDACIÓN
   - comprobar que el nuevo servicio funciona
   - comprobar que los servicios existentes siguen funcionando

No puedes saltarte pasos.

---

## REGLAS CRÍTICAS DE INFRAESTRUCTURA

### NGINX
- nunca sobrescribir configuraciones existentes
- validar siempre con `nginx -t` antes de recargar
- si falla la validación → NO recargar

### SYSTEMD
- crear servicios nuevos, nunca modificar existentes sin justificación
- usar nombres propios del proyecto
- usar Restart=on-failure

### PUERTOS
- comprobar siempre qué está en uso antes de elegir uno
- no asumir que un puerto está libre

---

## GESTIÓN DE ERRORES Y CONEXIÓN

El acceso se realiza por SSH con una VPN inestable.

Si detectas:
- desconexión SSH
- timeout
- caída de VPN
- error de transporte
- shell no responde

DEBES:
1. detener inmediatamente la ejecución
2. no asumir estado del sistema
3. no continuar con pasos posteriores
4. pedir reconexión explícitamente

---

## REGLA DE ORO

Ante cualquier duda o ambigüedad:
→ NO IMPROVISES
→ DETENTE Y PREGUNTA

---

## OBJETIVO FINAL

Desplegar nuevos servicios sin afectar a:
- disponibilidad
- rendimiento
- estabilidad

de los sistemas ya existentes.