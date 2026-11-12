# Bitácora — CashDroController

Registro de problemas, decisiones y lecciones. Está escrito para que quien venga después **no repita los mismos errores**.

---

## 1. Contexto

El objetivo era una aplicación de consola en Windows que permitiese a una caja cobrar con un CashDro, anular operaciones y consultar su estado, sin SDK propietario y con la mínima dependencia posible.

Restricciones de partida:

- El hardware **no estaba disponible** en el entorno de desarrollo.
- El contrato era el manual de integración `v22.01.21.11`, no el firmware vivo.
- El PC objetivo era Windows 10, con posibilidad de usar un Python "embeddable".
- La red era local, sin Internet en el tramo del dispositivo.
- Se exigía una sola dependencia externa.

---

## 2. Problemas encontrados y cómo se resolvieron

### P-01 — `operation_id` sin inicializar

**Síntoma:** un fallo temprano en el cobro (por ejemplo, `startOperation` rechazado) producía `UnboundLocalError` al entrar en el `except` que intentaba cancelar.

**Causa:** `operation_id` se asignaba dentro del `try` y se usaba en los `except` como condición.

**Solución:** inicializar `operation_id = ""` **antes** del `try` y comprobar la verdad del valor antes de llamar a `finish_operation`.

**Lección:** cualquier variable que se use en un `except` debe existir en todos los caminos. En Python no hay "declaración", pero sí hay que darle un valor centinela.

---

### P-02 — `-1900` (System busy) terminaba como error de red

**Síntoma:** cuando el CashDro respondía `-1900`, el mensaje final era `Error de conexión tras 3 intentos: None`, sin código ni explicación.

**Causa:** el `-1900` se lanzaba como `CashDroError` dentro del `try`, pero ese `except` sólo capturaba excepciones de `requests`. El flujo caía al final del bucle, donde se comprobaba `last_exception is None` y se construía una `RequestException` genérica.

**Solución:** contador separado `system_busy_retries_left`, decremento y `continue` con espera de 5 s. Al agotarse, `CashDroError(-1900, "System busy...")` explícito.

**Lección:** los errores de **aplicación** y los de **transporte** no deben compartir el mismo camino de salida. Si se mezclan, el mensaje final miente.

---

### P-03 — Los reintentos de `-1900` y de red se pisaban

**Síntoma:** con el equipo ocupado, se agotaban los reintentos de red; con la red caída, se consumían los de *busy*.

**Causa:** un único contador para dos condiciones distintas.

**Solución:** dos contadores independientes (`attempt` del `for` y `system_busy_retries_left`).

**Matiz descubierto al documentar:** como el `-1900` hace `continue` dentro del `for`, consume igualmente una iteración. Con `MAX_RETRIES=3` y `MAX_RETRIES_SYSTEM_BUSY=3`, el contador de *busy* nunca llega a cero antes que el bucle; el máximo de peticiones es 3, no 6. Queda como deuda técnica: si se quiere "3 de red **más** 3 de busy", hay que separar los bucles o ampliar el rango.

**Lección:** "independiente" no es lo mismo que "aditivo". Al separar contadores hay que revisar el bucle que los contiene.

---

### P-04 — Ctrl+C cerraba el programa sin cancelar la operación

**Síntoma:** durante el sondeo, un Ctrl+C terminaba el proceso y dejaba la transacción abierta en el CashDro.

**Causa:** el manejador por defecto de `SIGINT` lanza `KeyboardInterrupt`, que no se capturaba en el punto adecuado; además, no había forma de distinguir "cancelar operación" de "salir".

**Solución:**

1. `signal.signal(SIGINT, _signal_handler)` en `main`.
2. Primera pulsación: `_cancel_requested = True`; el sondeo lo consulta mediante `cancel_event` y lanza `KeyboardInterrupt` controlado.
3. Segunda pulsación: `sys.exit(0)`.
4. `_reset_cancel()` antes de cada operación.

**Lección:** en una aplicación que maneja dinero, "salir" y "cancelar la operación" son acciones distintas y deben tener gestos distintos.

---

### P-05 — El estado `E` se trataba como error

**Síntoma:** la operación abortaba justo cuando el equipo empezaba a ejecutarse.

**Causa:** la lista de estados válidos durante la espera no incluía `E` (ejecutando).

**Solución:** aceptar `I`, `Q`, `E` y cadena vacía; sólo `F` finaliza y cualquier otro valor es error.

**Lección:** la máquina de estados del dispositivo debe copiarse del manual **completa**, no de los estados que uno recuerda. Un estado omitido convierte el camino feliz en excepción.

---

### P-06 — Estructura JSON anidada de forma variable

**Síntoma:** `No se recibió operationId en la respuesta` con un `code=1`.

**Causa:** el firmware devolvía `response.operation.operation.operationId` en lugar de `response.operation.operationId`.

**Solución:** en `start_operation`, `ask_operation`, `ask_levels`, `ask_alerts` y `ask_diagnosis`, si la clave esperada contiene a su vez la misma clave, bajar un nivel.

**Lección:** normalizar en el borde. Si la variabilidad se propaga al resto del programa, cada función acaba con su propio `if` defensivo.

**Deuda:** la normalización es de un solo nivel extra. Si apareciera un tercer nivel, no se cubre.

---

### P-07 — Acentos y caracteres especiales en la consola de Windows

**Síntoma:** mensajes con tildes y símbolos aparecían corruptos o rompían el formato en `cmd.exe` con codepage `cp850`/`cp1252`.

**Causa:** la consola no estaba en UTF-8 y el código fuente sí.

**Solución:** mensajes de salida **sin tildes ni símbolos no ASCII**; se conservan los acentos sólo en comentarios y docstrings. Los marcos usan `+`, `-`, `|` en lugar de caracteres de caja.

**Lección:** si el objetivo es Windows, el ASCII en la salida no es pereza: es compatibilidad. Si se quiere Unicode, hay que fijar `chcp 65001` y comprobarlo en la consola real, no en la del IDE.

---

### P-08 — Import del propio proyecto en Python embeddable

**Síntoma:** `ModuleNotFoundError: No module named 'config'` al ejecutar con el Python embeddable de Windows.

**Causa:** ese intérprete no añade el directorio del script a `sys.path`.

**Solución:** cada módulo inserta `os.path.dirname(os.path.abspath(__file__))` al principio de `sys.path` si no está.

**Lección:** el "Python embeddable" no se comporta como el instalador normal. Si se distribuye así, hay que probarlo explícitamente.

---

### P-09 — Credenciales duplicadas en los mensajes de error

**Síntoma:** `ERROR [-1]: [-1] Authentication Failed`.

**Causa:** `mostrar_error` imprimía el código y además `str(exc)`, que ya incluye `[código]`.

**Solución:** si el error es `CashDroError`, usar `error.code` y `error.message` por separado.

**Lección:** si una excepción formatea su mensaje, la capa de presentación no debe volver a formatearlo.

---

### P-10 — Import local de `_safe_input`

**Síntoma:** `NameError` en algunos caminos del menú.

**Causa:** la función se importaba dentro de una función en lugar de en la cabecera del módulo.

**Solución:** importar todas las funciones de `cashdro_cli` en la cabecera de `main.py`.

**Lección:** los imports locales son útiles para romper ciclos, pero no para "ahorrar" imports. Si se usan, deben ser deliberados y comentados.

---

### P-11 — Warning de SSL en cada arranque

**Síntoma:** `InsecureRequestWarning` llenaba la consola.

**Causa:** `verify=False` genera un aviso de `urllib3` por petición.

**Solución:** `urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)` al inicio de `main`, y `import urllib3` en la cabecera (no dentro de `main()`).

**Lección:** silenciar un warning es aceptable **si** se documenta por qué. Aquí está documentado en README y developer: el certificado es autofirmado y la red debe estar aislada.

---

### P-12 — IP y credenciales de ejemplo en el repositorio

**Síntoma:** el proyecto se desarrolló contra una instalación concreta y los valores quedaron en `config.py` y en el script de lanzamiento.

**Riesgo:** publicar una IP interna, un usuario y una contraseña, aunque sean de un equipo aislado.

**Solución aplicada:** los datos de conexión de `config.py` se leen de variables de entorno y los valores por defecto son marcadores (`192.0.2.10`, `USUARIO_CASHDRO`, `CLAVE_CASHDRO`). La documentación usa los mismos placeholders (`192.0.2.10`, `192.0.2.20`, `CAJA-01`).

**Pendiente:** `cashdro.sh` sigue siendo un script de conveniencia con valores de ejemplo; debe parametrizarse o dejarse fuera de la publicación. La documentación no puede arreglar un archivo que se publica tal cual.

**Lección:** los secretos se filtran por comodidad, no por malicia. El lugar de los placeholders es el repositorio; el de los valores reales, el equipo.

---

## 3. Enfoques descartados y por qué

| Enfoque | Por qué se descartó |
|---|---|
| **POST con body JSON** | La API del CashDro es GET con query params. No hay elección. |
| **`requests.Session`** | Ahorraría el handshake TLS en cada sondeo, pero una sesión persistente puede quedar en mal estado tras un fallo de red. Para 1 petición cada 2 s no compensa la complejidad. |
| **Hilos para el sondeo** | La consola es secuencial; un hilo obligaría a sincronizar la salida y el Ctrl+C. El sondeo bloqueante con `cancel_event` es más simple y suficiente. |
| **WebSocket / long-polling** | El firmware no ofrece push. |
| **`argparse` / `click`** | El uso es un menú interactivo, no una CLI de subcomandos. Añadir `argparse` habría duplicado la interfaz. |
| **`colorama`** | Windows 10+ interpreta ANSI. Una dependencia menos. |
| **GUI (Tkinter/Qt)** | El requisito era consola; una GUI multiplica la superficie y el esfuerzo de auditoría. |
| **`Decimal` para importes** | La API usa céntimos enteros. `Decimal` añadiría conversiones sin beneficio; el punto crítico es `round` antes de `int`. |
| **`float` sin `round`** | `18.25 * 100` puede dar `1824.999...`; truncar cobraría un céntimo de menos. Se usa `int(round(x*100))`. |
| **Un solo contador de reintentos** | Mezcla fallos de aplicación y de transporte. Ver P-02/P-03. |
| **Reintentar cualquier `code != 1`** | Un `-1` (autenticación) o un `-3` (importe) no se arreglan esperando. Sólo `-1900` se reintenta. |
| **`verify=True`** | Rompe la conexión con el certificado autofirmado. |
| **Instalar el certificado como CA** | Requiere tocar el almacén de Windows y distribuir el PEM. Se dejó como mejora, no como requisito. |
| **Guardar credenciales en `.env`** | Añade una dependencia y un archivo que también puede filtrarse. La configuración es un módulo Python; el problema real es no versionar los valores. |
| **Logging a archivo desde el inicio** | El riesgo de volcar la URL con la contraseña es alto. Se prefirió no tener logging a tenerlo mal. Pendiente: logging de eventos sin URL. |
| **Persistencia en base de datos** | Fuera del alcance: el controlador no es un TPV. Se documentó cómo añadirla sin duplicar ventas. |
| **Abrir la operación con `amount` en euros** | El manual especifica céntimos. Enviar `18.25` habría producido `-3` o, peor, un cobro erróneo. |
| **Interpretar las claves de `askLevels`** | Cambian con el firmware. Inventar un mapeo habría producido informes falsos. Se muestran tal cual. |

---

## 4. Decisiones técnicas y su justificación

| Decisión | Alternativa | Motivo |
|---|---|---|
| Cuatro módulos (`config`, `api`, `cli`, `main`) | Un solo archivo | La separación permite usar la API como biblioteca y auditar la lógica sin la consola. |
| `CashDroError` con `code` y `message` | Devolver códigos | Las excepciones obligan a manejar el fallo; un código de retorno se ignora. |
| `-99` como código local | Inventar códigos nuevos | `-99` ya significa "parámetros inválidos" en el contrato; se reutiliza para fallos del cliente. |
| `wait_for_completion` en la API, no en `main` | Bucle en `main` | El sondeo es parte del protocolo, no de la presentación. |
| `cancel_event` como *callable* | Booleano o `Event` | Evita acoplar la API a `threading` y permite cualquier fuente de cancelación. |
| `time.monotonic()` | `time.time()` | Inmune a ajustes de reloj (NTP, cambio de hora). |
| `str` para `type`, `amount`, `end_type` | Enviar enteros | El equipo espera cadenas; `requests` las serializaría igual, pero ser explícito evita sorpresas. |
| Normalización de JSON en cada método | Una función genérica | Cada operación tiene una clave distinta; una función genérica habría añadido parámetros y menos claridad. |
| Menú con `5` antes de `4` | Orden numérico | La reconfiguración no debe estar junto a "Salir" para evitar pulsaciones accidentales. |
| Confirmación literal `SI` | `s/N` | Una acción destructiva merece un gesto deliberado. |
| Colores ANSI sin dependencia | `colorama` | Menos superficie, Windows 10+ los soporta. |
| `verify=False` global | Pinning | El pinning requiere extraer y mantener el certificado; se dejó documentado como mejora. |
| Sin `logging` | `logging` básico | Evitar el volcado de credenciales. Se documentó cómo hacerlo bien. |
| `cashdro.sh` como atajo | Script de despliegue | Es una herramienta de desarrollo, no un mecanismo de producción. |

---

## 5. Cronología resumida

| Etapa | Qué ocurrió |
|---|---|
| Análisis | Se mapeó la API del manual y se definieron flujos, errores y timeouts. |
| Primera implementación | Cuatro módulos; flujo de cobro completo; consultas. |
| Primera auditoría | Se detectaron P-01, P-02, P-04, P-09 y P-10. |
| Correcciones | Inicialización de `operation_id`, contador de `-1900`, manejador de señal, mensajes. |
| Segunda auditoría | Se detectó P-03 (contadores que se pisaban) y se añadieron los tests de simulación. |
| Ajustes de uso | Configuración de conexión al inicio y opción 5; cambio de IP por defecto. |
| Documentación | README, datasheet, developer, referencias, bitácora y diagramas. |

---

## 6. Lecciones aplicables a proyectos futuros

### Sobre integración con hardware

1. **El manual no es el equipo.** Un contrato documentado deja flecos: anidación, estados, tiempos. Sin hardware, la confianza máxima es "media".
2. **Pide una unidad o un simulador antes de prometer fechas.** La deuda de validación se paga al final y con intereses.
3. **Diseña para el fallo físico.** Atascos, cassettes llenos y clientes que se van son el caso normal, no la excepción.
4. **Un dispositivo, un cliente.** Si el firmware admite una operación a la vez, la coordinación es parte del sistema, no del código.

### Sobre protocolos pobres

5. **Si el protocolo impone credenciales en la URL, la seguridad se resuelve en la red.** No hay biblioteca que arregle eso.
6. **`verify=False` es una decisión de despliegue, no un descuido.** Documéntala y acota la red.
7. **Los timeouts son contrato.** Sin ellos, una operación abandonada bloquea el puesto.

### Sobre el código

8. **Normaliza en el borde.** Cinco métodos tolerantes valen más que cincuenta `if` repartidos.
9. **Separa error de aplicación y error de transporte.** Distintos contadores, distintos mensajes, distintas acciones.
10. **Inicializa antes del `try`.** El `except` no perdona variables inexistentes.
11. **Un `continue` consume iteración.** Revisa el bucle cuando separas contadores.
12. **Los céntimos son enteros.** `round` antes de `int`, siempre.
13. **No inventes datos del dispositivo.** Si no sabes qué significa una clave, muéstrala.

### Sobre documentación y publicación

14. **Documenta lo que no probaste.** Un README honesto vale más que uno triunfal.
15. **Los placeholders van al repo; los secretos, al equipo.**
16. **Una captura de pantalla puede filtrar una URL con contraseña.**
17. **Los scripts de conveniencia son la vía habitual de filtración de credenciales.**

---

## 7. Pendientes priorizados

| Prioridad | Tarea |
|---|---|
| Alta | Validar el flujo completo contra un CashDro real. |
| Alta | Parametrizar `cashdro.sh` (o excluirlo de la publicación). |
| Alta | Confirmar la forma exacta del JSON del firmware y ajustar la normalización. |
| Media | Añadir `tests/` con `unittest` y mocks (los seis escenarios ya están diseñados). |
| Media | Proteger `response.json()` contra cuerpos no JSON. |
| Media | Corregir el consumo de iteraciones del contador de `-1900`. |
| Media | Pinning del certificado o CA interna. |
| Baja | `math.isfinite` en la validación de importes. |
| Baja | Usar `AMOUNT_MAX` en la CLI y eliminar el literal. |
| Baja | Logging de eventos sin URLs. |
| Baja | Selector de múltiples dispositivos. |

---

## 8. Nota final

Este proyecto demuestra una cosa sobre todo lo demás: **se puede construir un cliente de integración sólido y bien documentado sin tener el hardware**, siempre que se sea explícito sobre lo que se sabe y lo que se supone. Lo que no se puede es llamarlo "validado". La diferencia entre ambas cosas es la que separa una demo de un sistema.

La siguiente persona que lo despliegue debería empezar por el banco de pruebas, no por el README.
