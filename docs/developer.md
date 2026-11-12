# Developer Guide — CashDroController

Arquitectura, API interna, configuración y guía de extensión.

---

## Índice

1. [Visión general](#1-visión-general)
2. [Mapa de módulos](#2-mapa-de-módulos)
3. [config.py](#3-configpy)
4. [cashdro_api.py](#4-cashdro_apipy)
5. [cashdro_cli.py](#5-cashdro_clipy)
6. [main.py](#6-mainpy)
7. [Flujo de una llamada HTTP](#7-flujo-de-una-llamada-http)
8. [Contrato de la API CashDro](#8-contrato-de-la-api-cashdro)
9. [Referencia de la API interna](#9-referencia-de-la-api-interna)
10. [Guía de extensión](#10-guía-de-extensión)
11. [Pruebas y simulación](#11-pruebas-y-simulación)
12. [Convenciones](#12-convenciones)
13. [Deuda técnica](#13-deuda-técnica)
14. [Seguridad en el código](#14-seguridad-en-el-código)

---

## 1. Visión general

La aplicación tiene **cuatro módulos** y una regla de dependencias estricta:

```
main.py ──► cashdro_cli.py
   │              │
   └──────────────┴──► cashdro_api.py ──► config.py
```

- `config.py` no importa nada del proyecto.
- `cashdro_api.py` importa `config` y `requests`. **No imprime nada.**
- `cashdro_cli.py` importa `config` (indirectamente) y `cashdro_api` sólo para `CashDroError` dentro de una función. **No hace HTTP.**
- `main.py` orquesta ambos y es el único que arranca el programa.

Esto permite usar `CashDroAPI` como biblioteca en otro programa (un TPV, un servicio, un script) sin arrastrar la consola.

### Principios aplicados

| Principio | Cómo se refleja |
|---|---|
| Separación de capas | API sin `print`; CLI sin `requests`. |
| Dependencia mínima | Sólo `requests`; el resto es biblioteca estándar. |
| Fallo explícito | Excepciones tipadas (`CashDroError`, `TimeoutError`, `RequestException`). |
| Estado en el servidor | El cliente no cachea operaciones; siempre pregunta. |
| Configuración central | Un único módulo de constantes. |
| Sin estado global salvo el flag de Ctrl+C | `_cancel_requested` es el único estado de proceso. |

### Compatibilidad

- Python 3.8+ por las anotaciones `dict[str, Any]` (con `from __future__ import annotations`) y `tuple[str, str, str]`.
- Windows es el objetivo; el código no usa APIs específicas de plataforma.
- Cada módulo inserta su directorio en `sys.path` para funcionar con el Python "embeddable" de Windows, que no añade el directorio del script.

---

## 2. Mapa de módulos

| Archivo | Líneas aprox. | Responsabilidad | Depende de |
|---|---|---|---|
| `main.py` | 405 | Punto de entrada, menú, flujos de cobro/anulación/estado, señales. | `cashdro_api`, `cashdro_cli`, `requests`, `urllib3` |
| `cashdro_api.py` | 404 | Cliente HTTP, reintentos, normalización de JSON, excepción `CashDroError`. | `requests`, `config` |
| `cashdro_cli.py` | 324 | Entrada/salida, colores, menús, formateo de resultados. | `cashdro_api` (sólo `CashDroError`) |
| `config.py` | 37 | Constantes: host, credenciales, timeouts, códigos, POS. | — |

### Flujo de dependencias en tiempo de ejecución

```
python main.py
   └─ import cashdro_api  → import config
   └─ import cashdro_cli  → (import diferido de cashdro_api)
   └─ main()
        ├─ signal.signal(SIGINT, _signal_handler)
        ├─ urllib3.disable_warnings(...)
        ├─ mostrar_banner()
        ├─ configurar_conexion() → solicitar_conexion()
        ├─ crear_api() → CashDroAPI(...)
        ├─ verificar_conexion(api) → api.test_connection()
        └─ while True: menu_principal() → operacion_*
```

---

## 3. config.py

Módulo de constantes. No tiene funciones ni clases; se importa y se lee.

```python
import os

CASHDRO_HOST = os.getenv("CASHDRO_HOST", "192.0.2.10")
CASHDRO_USER = os.getenv("CASHDRO_USER", "USUARIO_CASHDRO")
CASHDRO_PASSWORD = os.getenv("CASHDRO_PASSWORD", "CLAVE_CASHDRO")
API_BASE_PATH: str = "/Cashdro3WS/index3.php"

REQUEST_TIMEOUT: int = 10
MAX_RETRIES: int = 3
MAX_RETRIES_SYSTEM_BUSY: int = 3
RETRY_DELAY_SYSTEM_BUSY: int = 5
POLL_INTERVAL: int = 2
POLL_TIMEOUT: int = 120

ERROR_CODES: dict[int, str] = {...}

POS_ID: str = "1"
POS_USER = os.getenv("POS_USER", "USUARIO_CASHDRO")
ALIAS_ID = os.getenv("ALIAS_ID", "CAJA-01")
AMOUNT_MAX: float = 9999.99
```

> El ejemplo refleja el diseño actual: los datos de conexión se leen del entorno con valores por defecto seguros. No se versionan credenciales reales. `192.0.2.10` pertenece a TEST-NET-1 (RFC 5737), reservado para documentación.

### Uso de cada constante

| Constante | Consumidor | Efecto de cambiarla |
|---|---|---|
| `CASHDRO_HOST` | `CashDroAPI.__init__` | Cambia la URL base. |
| `CASHDRO_USER` / `CASHDRO_PASSWORD` | `_call` | Autenticación de cada petición. |
| `API_BASE_PATH` | `__init__` | Ruta del endpoint. |
| `REQUEST_TIMEOUT` | `requests.get` | Corte por llamada. |
| `MAX_RETRIES` | `_call` | Intentos ante error de red. |
| `MAX_RETRIES_SYSTEM_BUSY` | `_call` | Intentos ante `-1900`. |
| `RETRY_DELAY_SYSTEM_BUSY` | `_call` | Espera entre intentos de `-1900`. |
| `POLL_INTERVAL` | `wait_for_completion` | Frecuencia de sondeo. |
| `POLL_TIMEOUT` | `wait_for_completion` | Duración máxima. |
| `POS_ID` / `POS_USER` / `ALIAS_ID` | `start_operation` | Metadatos de la operación. |
| `AMOUNT_MAX` | `cashdro_cli.solicitar_monto` | Tope de entrada. |
| `ERROR_CODES` | `CashDroError` | Texto por defecto de cada código. |

`ERROR_CODES` se usa como diccionario de respaldo: si el equipo envía `errorMessage`, ese texto tiene prioridad; si no, se busca el código.

Las cinco constantes de conexión (`CASHDRO_HOST`, `CASHDRO_USER`, `CASHDRO_PASSWORD`, `POS_USER`, `ALIAS_ID`) pueden fijarse por variable de entorno; el resto sólo se edita en el archivo. El módulo se evalúa una vez, al importar: cambiar una variable de entorno después de arrancar no tiene efecto.

### Limitación de diseño

`ERROR_CODES` está en `config.py` pero es una tabla de mensajes, no configuración. Si el proyecto crece, conviene moverlo a `cashdro_api.py` o a un módulo `errors.py`.

---

## 4. cashdro_api.py

### 4.1. `CashDroError`

```python
class CashDroError(Exception):
    def __init__(self, code: int, message: str = "") -> None:
        self.code = code
        self.message = message or ERROR_CODES.get(code, f"Error desconocido ({code})")
        super().__init__(f"[{code}] {self.message}")
```

- `code`: código numérico del equipo (o `-99` para errores locales).
- `message`: texto del equipo o el de `ERROR_CODES`.
- `str(exc)` produce `"[código] mensaje"`.
- `cashdro_cli.mostrar_error` usa `code` y `message` por separado para no duplicar el prefijo.

Se usa `-99` como código "local" cuando el fallo no viene del equipo: falta de `operationId`, estado inesperado o `withError`.

### 4.2. `CashDroAPI.__init__`

```python
def __init__(
    self,
    host: str = CASHDRO_HOST,
    user: str = CASHDRO_USER,
    password: str = CASHDRO_PASSWORD,
    timeout: int = REQUEST_TIMEOUT,
    max_retries: int = MAX_RETRIES,
) -> None:
    self.base_url = f"https://{host}{API_BASE_PATH}"
```

- No valida el host: si lleva `https://` o una barra final, la URL queda mal formada. Es responsabilidad del llamador.
- `self.base_url` se muestra en la verificación inicial, así que un error de formato es visible.
- No abre conexiones: `requests` las gestiona por llamada.

### 4.3. `_call` — el núcleo

```python
def _call(self, operation: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]
```

**Construcción de parámetros**

```python
query_params = {"operation": operation, "name": self.user, "password": self.password}
for key, value in (params or {}).items():
    query_params[key] = json.dumps(value) if isinstance(value, (dict, list)) else value
```

- Los `dict`/`list` se serializan con `json.dumps` (sin `ensure_ascii=False`, así que los acentos se escapan; los importes son ASCII y no afecta).
- `requests` URL-encodea automáticamente al pasar `params=`.
- Los valores numéricos se convierten a `str` explícitamente en los métodos públicos (`type`, `amount`, `end_type`), porque el equipo espera cadenas.

**Bucle de intentos**

```python
for attempt in range(1, self.max_retries + 1):
    try:
        response = requests.get(self.base_url, params=query_params,
                                timeout=self.timeout, verify=False)
        response.raise_for_status()
        data = response.json()
        code = data.get("code", -99)
        if code != 1:
            if code == -1900 and system_busy_retries_left > 0:
                system_busy_retries_left -= 1
                time.sleep(RETRY_DELAY_SYSTEM_BUSY)
                continue
            raise CashDroError(code, error_msg)
        return data
    except (ConnectionError, Timeout, RequestException) as e:
        last_exception = e
        if attempt < self.max_retries:
            time.sleep(1)
        continue
```

Notas finas:

1. `raise_for_status()` convierte un 4xx/5xx en `HTTPError` (subclase de `RequestException`), que entra por la rama de reintentos. **Un 401 se reintenta tres veces** antes de fallar; no es ideal, pero es coherente con "fallo de transporte".
2. `response.json()` puede lanzar `ValueError` si el cuerpo no es JSON. **No se captura**: sale como excepción no controlada. Es una deuda técnica (ver §13).
3. `code` ausente se trata como `-99`.
4. `errorMessage` se busca en `response`; si no existe, queda `""` y `CashDroError` usa `ERROR_CODES`.
5. El `continue` del `-1900` **no incrementa** el contador de red, pero sí consume una iteración del `for`. Con `max_retries=3` y `MAX_RETRIES_SYSTEM_BUSY=3`, el máximo real de peticiones es 3: el contador de *busy* no puede agotarse antes que el bucle. Si se quiere permitir 3 reintentos **además** de los 3 de red, hay que ampliar el rango del `for` o separar los bucles. Este es un matiz importante al ajustar los parámetros.
6. Al salir del bucle:
   - Si no hubo excepción de red y el contador de *busy* llegó a 0 → `CashDroError(-1900)`.
   - En cualquier otro caso → `RequestException("Error de conexión tras N intentos: ...")`.

**Por qué `verify=False`**

El certificado del CashDro es autofirmado. `requests` lo rechaza con `SSLError`. Desactivar la verificación es la única forma de conectar sin instalar el certificado. `urllib3.disable_warnings` en `main()` silencia el aviso asociado.

### 4.4. Métodos públicos

#### `test_connection() -> dict`

```python
return self._call("doTest")
```

Devuelve la respuesta completa. `main.verificar_conexion` inspecciona `response.errorMessage`: si es `"none"`, la conexión es correcta. Es una convención del equipo, no del código.

#### `start_operation(...) -> str`

```python
def start_operation(self, op_type=4, amount=None, posid=POS_ID,
                    posuser=POS_USER, aliasid=ALIAS_ID) -> str
```

- Construye `type`, `posid`, `posuser`, `aliasid`.
- Si `amount` no es `None`, añade `parameters={"amount": str(int(round(amount*100)))}`.
- Extrae `response.operation`; si dentro hay otra clave `operation`, baja un nivel.
- Si no hay `operationId`, lanza `CashDroError(-99, "No se recibió operationId en la respuesta")`.
- Devuelve el ID como cadena.

**Por qué no valida el importe**: la validación de negocio está en la CLI. Como biblioteca, `start_operation` acepta cualquier `float`; el equipo rechazará con `-3` si no le cuadra.

#### `acknowledge_operation(operation_id) -> dict`

```python
return self._call("acknowledgeOperationId", {"operationId": operation_id})
```

#### `ask_operation(operation_id) -> dict`

Llama a `askOperation` y normaliza `response.operation`, incluyendo el caso de doble anidación. Devuelve el diccionario de la operación (posiblemente vacío si el equipo no lo envía).

#### `finish_operation(operation_id, end_type=1) -> dict`

`end_type=1` finaliza; `2` anula. El valor se envía como cadena (`"1"`/`"2"`).

#### `set_operation_imported(operation_id) -> dict`

Marca la operación como importada. Se llama **después** de mostrar el resultado. Si falla, la venta ya está hecha: el error se propaga y la CLI lo muestra, pero el dinero ya se movió. En un sistema contable real esto exige reconciliación.

#### `ask_levels() -> dict`

```python
data = self._call("askLevels")
levels = data.get("response", {}).get("levels", {})
if "levels" in levels:
    levels = levels["levels"]
return levels
```

#### `ask_alerts() -> list[dict]`

Normaliza `response.alerts`; si viene envuelto en otra clave `alerts`, lo desenvuelve. Si no es lista, devuelve `[]`. Es defensivo: el tipo de retorno siempre es lista.

#### `ask_diagnosis() -> dict`

Igual que `ask_levels`, con `diagnosis`.

### 4.5. `wait_for_completion`

```python
def wait_for_completion(self, operation_id, poll_interval=POLL_INTERVAL,
                        poll_timeout=POLL_TIMEOUT, cancel_event=None) -> dict
```

Algoritmo:

```
inicio = monotonic()
loop:
    si cancel_event() → KeyboardInterrupt
    si monotonic() - inicio >= poll_timeout → TimeoutError
    estado = ask_operation(id)
    si state == "F":
        si withError == "true" → CashDroError(-99, ...)
        return estado
    si state not in ("I","Q","E",""): → CashDroError(-99, ...)
    sleep(poll_interval)
```

Detalles:

- Usa `time.monotonic()`, no `time.time()`: inmune a cambios de reloj.
- `withError` se compara como cadena en minúsculas; tolera `"True"`, `"TRUE"`, etc.
- Los estados vacíos se toleran porque el equipo puede responder antes de tener estado.
- El timeout se comprueba **antes** de consultar: con `poll_timeout=0` falla de inmediato sin llamar.
- `cancel_event` se evalúa en cada iteración, así que la cancelación tarda como máximo `poll_interval`.

---

## 5. cashdro_cli.py

### 5.1. Constantes de color

```python
RESET="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
RED="\033[91m"; GREEN="\033[92m"; YELLOW="\033[93m"; BLUE="\033[94m"
MAGENTA="\033[95m"; CYAN="\033[96m"; WHITE="\033[97m"
```

`_color(texto, código, bold=False)` compone `prefijo + código + texto + RESET`. No comprueba si la terminal soporta color; en una consola sin ANSI se verán secuencias, algo aceptable en Windows 10+.

### 5.2. Entrada segura

```python
def _safe_input(prompt="") -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""
    except KeyboardInterrupt:
        return ""
```

Devuelve cadena vacía ante EOF o Ctrl+C. Esto hace que los bucles de menú no exploten en un pipe o en una sesión remota sin TTY. **Efecto lateral:** un Ctrl+C durante una pregunta se interpreta como "Enter vacío", no como cancelación; el manejador de señal de `main` sigue activo y decide.

### 5.3. Funciones de presentación

| Función | Salida | Notas |
|---|---|---|
| `mostrar_banner()` | Marco de 52 columnas | Estático. |
| `menu_principal()` | Menú y validación `1..5` | Bucle hasta opción válida. |
| `solicitar_conexion()` | Tres prompts | Devuelve tupla; Enter mantiene. |
| `solicitar_monto()` | Prompt y validación | Acepta coma; `None` si cancela. |
| `mostrar_progreso()` | `* mensaje (detalle)` | Detalle opcional. |
| `mostrar_paso_ok()` | `OK ...` verde | — |
| `mostrar_paso_error()` | `FAIL ...` rojo | — |
| `mostrar_resultado()` | Bloque de transacción | Convierte céntimos. |
| `mostrar_estado_cashdro()` | Niveles, alertas, diagnóstico | Colorea valores "ok". |
| `mostrar_error()` | `ERROR [código]: mensaje` | Evita duplicar el código. |
| `mostrar_info()` | `i mensaje` | — |
| `confirmar_cancelacion()` | Pide `SI` | `True` sólo con `"SI"`. |
| `_cents_to_euro()` | `"2000"` → `"20.00"` | Devuelve el original si falla. |

### 5.4. Validación de importes

```python
entrada = entrada.replace(",", ".")
monto = float(entrada)
if monto <= 0: ...
if monto > 9999.99: ...
```

- Acepta `18,25`, `18.25`, ` 18 ` (por el `strip` de `_safe_input`).
- `float("nan")` e `float("inf")` **pasarían** la validación (`nan > 9999.99` es `False`). Es un caso raro pero real si alguien teclea `nan`. Se puede cerrar con `math.isfinite`.
- El límite está duplicado: `9999.99` literal en `solicitar_monto` y `AMOUNT_MAX` en `config.py`. La constante **no se usa** en la CLI. Deuda técnica menor.

### 5.5. Formato del resultado

`mostrar_resultado` convierte `totalin`, `totalout` y `change` con `_cents_to_euro`, y muestra `operationId`, `date`, `type`, `posid`, `aliasid` si vienen. El cambio sólo se imprime si es `> 0`. Si el equipo devuelve estos campos con otro nombre, no se verán: el código no los busca por alias.

### 5.6. `mostrar_error`

```python
if isinstance(error, CashDroError):
    codigo_real = error.code if codigo is None else codigo
    print(f"ERROR [{codigo_real}]: {error.message}")
elif codigo is not None:
    print(f"ERROR [{codigo}]: {error}")
else:
    print(f"ERROR: {error}")
```

El `import` de `CashDroError` es diferido (dentro de la función) para evitar un ciclo de importación `api → cli → api`. Funciona, pero un módulo de excepciones separado sería más limpio.

---

## 6. main.py

### 6.1. Estado global y señal

```python
_cancel_requested: bool = False

def _signal_handler(sig, frame):
    if not _cancel_requested:
        print(); mostrar_info("Presione Ctrl+C nuevamente...")
        _cancel_requested = True
    else:
        sys.exit(0)
```

- Primera pulsación: activa el flag. El sondeo lo lee mediante `_check_cancel`.
- Segunda: salida inmediata, sin limpieza. No hay recursos abiertos que cerrar.
- `_reset_cancel()` se llama antes de cada operación y en cada vuelta del menú, para que un flag viejo no cancele la siguiente venta.

**Limitación:** si el usuario pulsa Ctrl+C mientras el programa está bloqueado en `requests.get` (timeout de 10 s), la señal se atiende al volver, no interrumpe la llamada. El retardo máximo es el timeout.

### 6.2. `verificar_conexion`

```python
result = api.test_connection()
response = result.get("response", {})
error_msg = response.get("errorMessage", "none")
if error_msg.lower() == "none": return True
```

`doTest` puede devolver `code=1` con un `errorMessage` distinto de `"none"`; en ese caso se considera fallo. Es una convención del fabricante.

### 6.3. `operacion_cobro`

Secuencia exacta:

```
monto = solicitar_monto()          # None → return
operation_id = ""                  # ANTES del try
try:
    operation_id = api.start_operation(4, monto)
    api.acknowledge_operation(operation_id)
    state = api.wait_for_completion(operation_id, cancel_event=_check_cancel)
    mostrar_resultado(state)
    api.set_operation_imported(operation_id)
except KeyboardInterrupt: _finalizar_o_cancelar(...)
except CashDroError as e: mostrar_error; finish(2) si hay id
except RequestException as e: mostrar_error; finish(2) si hay id
except TimeoutError as e: mostrar_error; finish(2) si hay id
```

Puntos a tener en cuenta al modificar:

- `operation_id` debe seguir inicializándose antes del `try`; si se mueve dentro, un fallo en `start_operation` provoca `UnboundLocalError` en el `except`.
- Los tres `except` de fallo intentan `finish_operation(..., 2)` en un `try/except Exception: pass`. Es deliberado: si la red está caída, no tiene sentido enmascarar el error original con otro.
- Si `set_operation_imported` falla, se propaga: la venta está hecha pero no marcada. El mensaje lo muestra la CLI.

### 6.4. `operacion_anular`

Pide el ID, consulta estado y cancela si no es `F`. No busca operaciones abiertas automáticamente porque la API no ofrece un "listar operaciones": sólo se puede preguntar por ID.

### 6.5. `operacion_estado`

Tres llamadas secuenciales. Si la primera falla, no se ejecutan las siguientes (el `except` envuelve las tres). No hay tolerancia parcial: o se muestran las tres secciones o se muestra el error.

### 6.6. `main`

```
signal.signal(SIGINT, _signal_handler)
urllib3.disable_warnings(InsecureRequestWarning)
mostrar_banner()
host, user, pass = configurar_conexion()
api = crear_api(host, user, pass)
if not verificar_conexion(api):
    preguntar continuar; si no → exit
while True:
    _reset_cancel(); opcion = menu_principal()
    1 → cobro; 2 → anular; 3 → estado; 5 → reconfigurar; 4 → salir
    pausa "Enter para continuar"
```

`crear_api` y `configurar_conexion` importan `config` **dentro** de la función. Es redundante (el módulo ya está importado por `cashdro_api`), pero evita un import circular si en el futuro `config` importa algo de `main`. Se puede limpiar.

La reconfiguración (opción 5) **reemplaza** la instancia `api`; la anterior se descarta. No hay cierre de sesión porque no hay sesión.

---

## 7. Flujo de una llamada HTTP

Ejemplo: `api.start_operation(4, 18.25)`.

```
1. start_operation construye:
   type="4", posid="1", posuser="USUARIO", aliasid="CAJA-01"
   parameters={"amount": "1825"}   ← int(round(18.25*100))

2. _call("startOperation", params) añade:
   operation="startOperation", name=..., password=...

3. requests.get(base_url, params=query_params, timeout=10, verify=False)
   URL resultante:
   https://192.0.2.10/Cashdro3WS/index3.php
     ?operation=startOperation
     &name=USUARIO_CASHDRO
     &password=CLAVE_CASHDRO
     &type=4
     &posid=1
     &posuser=USUARIO_CASHDRO
     &aliasid=CAJA-01
     &parameters=%7B%22amount%22%3A%221825%22%7D

4. Respuesta (ilustrativa):
   {"code":1,"response":{"errorMessage":"none",
     "operation":{"operation":{"operationId":"OP-..."}}}}

5. Normalización: operation → operation → operationId
6. Retorno: "OP-..."
```

### Codificación del JSON

`parameters` se serializa como `{"amount": "1825"}` (sin espacios, porque `json.dumps` usa `separators=(', ', ': ')` por defecto → realmente produce `{"amount": "1825"}` con espacio tras `:`). El servidor lo decodifica tras el URL-decode. Si el firmware es estricto con el formato, `json.dumps(..., separators=(",", ":"))` produce una cadena más compacta; conviene probarlo en banco.

---

## 8. Contrato de la API CashDro

### 8.1. Petición

| Elemento | Valor |
|---|---|
| Método | `GET` |
| Esquema | `https` |
| Ruta | `/Cashdro3WS/index3.php` |
| Autenticación | `name`, `password` (query) |
| Formato de parámetros compuestos | JSON serializado + URL-encode |
| Cabeceras especiales | Ninguna |

### 8.2. Respuesta

```json
{"code": 1, "response": { ... }}
```

| Campo | Tipo | Significado |
|---|---|---|
| `code` | int | `1` = éxito; negativo = error. |
| `response` | object | Cuerpo específico de la operación. |
| `response.errorMessage` | string | `"none"` en éxito; texto en error. |

### 8.3. Operaciones y campos

| Operación | Campos de respuesta relevantes |
|---|---|
| `doTest` | `errorMessage` |
| `startOperation` | `operation.operationId` (posible doble anidación) |
| `acknowledgeOperationId` | `errorMessage` |
| `askOperation` | `state`, `totalin`, `totalout`, `change`, `withError`, `operationId`, `date` |
| `finishOperation` | `errorMessage` |
| `setOperationImported` | `errorMessage` |
| `askLevels` | `levels` (mapa clave→unidades) |
| `askAlerts` | `alerts` (lista o mapa) |
| `askDiagnosis` | `diagnosis` (mapa clave→valor) |

Los nombres exactos de las claves de `levels` y `diagnosis` dependen del firmware. **No los asumas**: trátalos como opacos.

### 8.4. Estados

| Estado | Interpretación |
|---|---|
| `I` | Inicial / pendiente de acknowledge. |
| `Q` | En cola. |
| `E` | Ejecutándose (espera efectivo). |
| `F` | Finalizada. |
| Otro | Desconocido → error. |

`withError` se evalúa como booleano en texto (`"true"`).

---

## 9. Referencia de la API interna

### 9.1. `cashdro_api`

```python
class CashDroError(Exception):
    code: int
    message: str

class CashDroAPI:
    base_url: str
    user: str
    password: str
    timeout: int
    max_retries: int

    def __init__(self, host=CASHDRO_HOST, user=CASHDRO_USER,
                 password=CASHDRO_PASSWORD, timeout=REQUEST_TIMEOUT,
                 max_retries=MAX_RETRIES) -> None

    def _call(self, operation: str,
              params: dict[str, Any] | None = None) -> dict[str, Any]

    def test_connection(self) -> dict[str, Any]
    def start_operation(self, op_type: int = 4, amount: float | None = None,
                        posid: str = POS_ID, posuser: str = POS_USER,
                        aliasid: str = ALIAS_ID) -> str
    def acknowledge_operation(self, operation_id: str) -> dict[str, Any]
    def ask_operation(self, operation_id: str) -> dict[str, Any]
    def finish_operation(self, operation_id: str, end_type: int = 1) -> dict[str, Any]
    def set_operation_imported(self, operation_id: str) -> dict[str, Any]
    def ask_levels(self) -> dict[str, Any]
    def ask_alerts(self) -> list[dict[str, Any]]
    def ask_diagnosis(self) -> dict[str, Any]
    def wait_for_completion(self, operation_id: str,
                            poll_interval: int = POLL_INTERVAL,
                            poll_timeout: int = POLL_TIMEOUT,
                            cancel_event: Callable[[], bool] | None = None) -> dict[str, Any]
```

### 9.2. `cashdro_cli`

```python
def _color(text: str, color_code: str, bold: bool = False) -> str
def _safe_input(prompt: str = "") -> str
def _cents_to_euro(valor: str) -> str

def mostrar_banner() -> None
def menu_principal() -> str
def solicitar_conexion(host_actual="", user_actual="", pass_actual="") -> tuple[str, str, str]
def solicitar_monto() -> float | None
def mostrar_progreso(mensaje: str, detalle: str = "") -> None
def mostrar_paso_ok(mensaje: str) -> None
def mostrar_paso_error(mensaje: str) -> None
def mostrar_resultado(data: dict) -> None
def mostrar_estado_cashdro(levels: dict, alerts: list, diagnosis: dict) -> None
def mostrar_error(error: Exception, codigo: int | None = None) -> None
def mostrar_info(mensaje: str) -> None
def confirmar_cancelacion() -> bool
```

### 9.3. `main`

```python
def _signal_handler(sig: int, frame) -> None
def _check_cancel() -> bool
def _reset_cancel() -> None
def operacion_cobro(api: CashDroAPI) -> None
def _finalizar_o_cancelar(api: CashDroAPI, operation_id: str) -> None
def operacion_anular(api: CashDroAPI) -> None
def operacion_estado(api: CashDroAPI) -> None
def verificar_conexion(api: CashDroAPI) -> bool
def crear_api(host="", user="", password="") -> CashDroAPI
def configurar_conexion() -> tuple[str, str, str]
def main() -> None
```

---

## 10. Guía de extensión

### 10.1. Usar `CashDroAPI` como biblioteca

```python
from cashdro_api import CashDroAPI, CashDroError
import requests

api = CashDroAPI(host="192.0.2.10", user="...", password="...")

try:
    api.test_connection()
    op_id = api.start_operation(amount=12.50)
    api.acknowledge_operation(op_id)
    estado = api.wait_for_completion(op_id, poll_timeout=180)
    print(estado.get("totalin"), estado.get("change"))
    api.set_operation_imported(op_id)
except CashDroError as e:
    print(f"CashDro: [{e.code}] {e.message}")
except requests.exceptions.RequestException as e:
    print(f"Red: {e}")
```

Advertencia: este fragmento no gestiona la cancelación ni el cierre de la operación ante un fallo. En producción, envuelve el flujo igual que `operacion_cobro`.

### 10.2. Añadir una operación de la API

1. Añade el método en `cashdro_api.py`:

```python
def ask_statistics(self) -> dict[str, Any]:
    data = self._call("askStatistics")
    stats = data.get("response", {}).get("statistics", {})
    if "statistics" in stats:
        stats = stats["statistics"]
    return stats
```

2. Añade la presentación en `cashdro_cli.py`:

```python
def mostrar_estadisticas(stats: dict) -> None:
    print(f"\n{_color('Estadisticas:', BOLD)}")
    for k, v in stats.items():
        print(f"  {_color(f'{k}:', DIM)} {v}")
```

3. Llámalo desde `main.operacion_estado` o desde una opción nueva.

4. Añade el código de error a `ERROR_CODES` si el fabricante define uno nuevo.

### 10.3. Añadir una opción al menú

`menu_principal` valida contra una tupla literal. Hay que tocar tres sitios:

```python
# cashdro_cli.py
print(f"  {_color('6.', MAGENTA)} {_color('Nueva opcion', BOLD)} - ...")
if opcion in ("1", "2", "3", "4", "5", "6"):
    return opcion
```

```python
# main.py
elif opcion == "6":
    operacion_nueva(api)
```

El menú muestra `5` antes que `4`; mantén el criterio o reordena todo, pero no dejes un hueco sin explicar.

### 10.4. Cambiar el tipo de operación

`start_operation` ya acepta `op_type`. Para una operación distinta de venta:

```python
op_id = api.start_operation(op_type=5, amount=amount)
```

Antes de hacerlo, confirma en el manual qué significa cada `type` para tu firmware. No está validado en este proyecto.

### 10.5. Configuración por entorno (implementada)

`config.py` resuelve la conexión con `os.getenv`:

```python
CASHDRO_HOST = os.getenv("CASHDRO_HOST", "192.0.2.10")
CASHDRO_USER = os.getenv("CASHDRO_USER", "USUARIO_CASHDRO")
CASHDRO_PASSWORD = os.getenv("CASHDRO_PASSWORD", "CLAVE_CASHDRO")
POS_USER = os.getenv("POS_USER", "USUARIO_CASHDRO")
ALIAS_ID = os.getenv("ALIAS_ID", "CAJA-01")
```

Precedencia: **variable de entorno > valor por defecto**. Los valores por defecto son marcadores públicos; el repositorio nunca debe contener credenciales reales.

```bat
set CASHDRO_HOST=192.0.2.10
set CASHDRO_USER=USUARIO_CASHDRO
set CASHDRO_PASSWORD=CLAVE_CASHDRO
set ALIAS_ID=CAJA-01
python main.py
```

Advertencias:

- El programa **no carga** un archivo `.env` por sí solo. Sin `python-dotenv` (dependencia que este proyecto evita), hay que exportar las variables en la sesión o en un lanzador local que no se versione.
- `set` sólo afecta a la consola actual. Para persistir, usa `setx`, pero ten en cuenta que queda en el registro del usuario.
- Cambiar una variable con el programa en marcha no surte efecto: `config` se evalúa al importar.

### 10.6. Varios dispositivos

```python
apis = {
    "caja-1": CashDroAPI(host="192.0.2.10", user=u1, password=p1),
    "caja-2": CashDroAPI(host="192.0.2.51", user=u2, password=p2),
}
```

La clase no tiene estado compartido; cada instancia es independiente. Falta una capa de selección en la CLI y una política de qué hacer si dos terminales atacan el mismo equipo (el firmware probablemente responderá `-1900`).

### 10.7. Registro en archivo

```python
import logging
logging.basicConfig(filename="cashdro.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
```

Registra **eventos**, nunca la URL:

```python
logging.info("cobro iniciado monto=%.2f id=%s", monto, op_id)
logging.info("cobro completado id=%s totalin=%s", op_id, estado.get("totalin"))
```

Si activas logging de `urllib3`, las credenciales acaban en el archivo. No lo hagas.

### 10.8. Interfaz gráfica

La separación actual lo permite: `CashDroAPI` no imprime. Una GUI (Tkinter, PySide) sustituiría `cashdro_cli` y reutilizaría `main.operacion_cobro` si se extrae la parte de presentación. El trabajo real está en el manejo de hilos: `wait_for_completion` bloquea; en una GUI debe correr en un hilo y comunicar el progreso por una cola.

### 10.9. Persistencia de ventas

No implementada. Si se añade:

- Guarda `operationId`, `timestamp`, importe solicitado, `totalin`, `totalout`, `change`, `aliasid`.
- Escribe **después** de `set_operation_imported` (o justo antes, con estado "pendiente").
- Hazlo idempotente por `operationId`: un reintento no debe duplicar.
- SQLite es suficiente; no añadas un ORM para una tabla.

---

## 11. Pruebas y simulación

### 11.1. Lo que se puede probar sin hardware

| Prueba | Cómo |
|---|---|
| Sintaxis e imports | `python -m py_compile *.py`; `python -c "import main"` |
| Conversión de céntimos | Llamar `_cents_to_euro("2000")` |
| Validación de importes | Monkeypatch de `input` o prueba manual |
| Reintentos | Doble de `requests.get` que devuelva secuencias |
| Normalización de JSON | Diccionarios de ejemplo pasados a los métodos |
| Formato de salida | Capturar stdout con `contextlib.redirect_stdout` |

### 11.2. Simular el transporte con `unittest.mock`

No hace falta instalar nada: `unittest.mock` es biblioteca estándar.

```python
from unittest.mock import patch, MagicMock
from cashdro_api import CashDroAPI, CashDroError

def respuesta(code, **extra):
    m = MagicMock()
    m.json.return_value = {"code": code, "response": extra}
    m.raise_for_status.return_value = None
    return m

@patch("cashdro_api.time.sleep", lambda *_: None)
@patch("cashdro_api.requests.get")
def test_busy_luego_ok(get):
    get.side_effect = [respuesta(-1900), respuesta(1, errorMessage="none")]
    api = CashDroAPI(host="127.0.0.1")
    assert api.test_connection()["code"] == 1
    assert get.call_count == 2

@patch("cashdro_api.time.sleep", lambda *_: None)
@patch("cashdro_api.requests.get")
def test_busy_agotado(get):
    get.side_effect = [respuesta(-1900) for _ in range(3)]
    api = CashDroAPI(host="127.0.0.1")
    try:
        api.test_connection()
        assert False, "debería lanzar"
    except CashDroError as e:
        assert e.code == -1900
```

Nota: `requests.get` se importa como `requests.get` dentro del módulo, así que el parcheo correcto es `cashdro_api.requests.get`. Parchear `requests.get` globalmente también funciona, pero es más frágil.

### 11.3. Simular un servidor HTTP local

Para probar el flujo completo sin CashDro, monta un `http.server` que responda JSON según la ruta y apunte `CASHDRO_HOST` a `127.0.0.1`. Requiere ajustar el esquema a `http` o generar un certificado autofirmado; el código fija `https://` en `base_url`, así que la vía más simple es un certificado de prueba y `verify=False`.

### 11.4. Pruebas que faltan

- Integración real con el firmware.
- Contrato de `askLevels`/`askDiagnosis` (claves reales).
- Comportamiento ante HTTP 500 con cuerpo HTML.
- Respuesta JSON malformada.
- Cancelación durante `requests.get`.
- Concurrencia de dos procesos.

---

## 12. Convenciones

| Aspecto | Convención |
|---|---|
| Idioma del código | Identificadores en inglés (`start_operation`), mensajes en español. |
| Tipado | Anotaciones en todas las firmas; `from __future__ import annotations`. |
| Docstrings | Una línea de propósito + Args/Returns/Raises cuando aplica. |
| Nombres privados | Prefijo `_` para helpers (`_call`, `_safe_input`). |
| Constantes | Mayúsculas en `config.py`. |
| Excepciones | No capturar `Exception` salvo en la limpieza de cancelación. |
| Prints | Sólo en `cashdro_cli` y en el banner de `main`. |
| Rutas | Ninguna ruta absoluta en el código. |
| Dependencias | Justificar cualquier añadido; el objetivo es una sola. |

### Estilo de los mensajes

- Sin tildes ni caracteres no ASCII en la salida de consola (compatibilidad con codepages de Windows). Esta es la razón de `Operacion`, `conexion`, `céntimos` aparece sólo en un mensaje… y debería evitarse.
- Formato `OK`/`FAIL`/`ERROR [código]` para que sea fácil de buscar.
- Los mensajes de error dicen **qué hacer**, no sólo qué pasó.

---

## 13. Deuda técnica

| # | Tema | Impacto | Propuesta |
|---|---|---|---|
| 1 | `response.json()` sin proteger | Bajo | Capturar `ValueError` y lanzar `CashDroError(-99, "Respuesta no JSON")`. |
| 2 | `-1900` consume iteraciones de red | Medio | Bucle separado o `while` con presupuesto total. |
| 3 | `AMOUNT_MAX` no se usa en la CLI | Bajo | Importar la constante y eliminar el literal. |
| 4 | `float("nan")` pasa la validación | Bajo | `math.isfinite(monto)`. |
| 5 | Credenciales en el repositorio | Bajo | **Resuelto**: lectura por entorno con placeholders. Riesgo residual: un `.env` local mal protegido. |
| 6 | `verify=False` fijo | Medio | Pinning opcional del certificado. |
| 7 | Sin tests automatizados en el repo | Medio | Añadir `tests/` con `unittest` y mocks. |
| 8 | `requests` reintenta 4xx | Bajo | Detectar `HTTPError` y no reintentar 4xx. |
| 9 | Imports diferidos redundantes | Bajo | Limpiar `crear_api`/`configurar_conexion`. |
| 10 | `cashdro.sh` con valores de ejemplo | Medio | Variables de entorno; no versionar secretos. |
| 11 | Sin logging | Medio | Log de eventos sin URLs. |
| 12 | Un solo CashDro en la CLI | Bajo | Selector de dispositivo. |

Ninguna de estas cuestiones bloquea el uso previsto, pero las tres primeras deberían resolverse antes de un despliegue con dinero real.

---

## 14. Seguridad en el código

### 14.1. Reglas que no se deben romper

1. **Nunca loguear `query_params` ni la URL completa.** Contienen `password`.
2. **Nunca imprimir la contraseña.** El prompt no la ecoa, pero un `print` de depuración sí.
3. **Mantener `verify=False` sólo si el equipo usa certificado autofirmado.** Si se instala una CA, cambiarlo.
4. **No añadir `verify=False` a otras conexiones** (actualizaciones, telemetría): es específico de este equipo.
5. **No ejecutar como administrador** sin necesidad.
6. **No confiar en el contenido del equipo** para construir rutas, comandos o SQL. Hoy sólo se muestra por pantalla.

### 14.2. Superficie de ataque

La aplicación no abre puertos, no acepta conexiones y no ejecuta datos del equipo. Su superficie es:

- La red hacia el CashDro (pasiva: escucha y MITM).
- El archivo `config.py` (por defecto sólo placeholders; las credenciales reales llegan por entorno).
- La sesión del operador, que puede tener las variables exportadas.
- La consola (hombre en el teclado).

### 14.3. Si se añade una GUI o un servicio

- No expongas la API del CashDro a la red de usuarios.
- No pongas el controlador en un servidor con IP pública.
- Si se convierte en servicio, ejecútalo con una cuenta de servicio sin privilegios y con la red restringida al equipo.

---

*Para el uso operativo, consulta `datasheet.md`. Para el contrato del fabricante, `REFERENCES.md`. Para el historial de decisiones, `BITACORA.md`.*
