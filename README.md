<div align="center">

# CashDroController

**Control de caja para un reciclador de efectivo CashDro, desde la consola de Windows.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Plataforma](https://img.shields.io/badge/Plataforma-Windows%2010%20%2F%2011-0078D4?logo=windows&logoColor=white)](#requisitos)
[![Dependencias](https://img.shields.io/badge/Dependencias-requests%20%C3%BAnica-2E7D32)](requirements.txt)
[![Licencia](https://img.shields.io/badge/Licencia-MIT-yellow)](LICENSE)
[![Hardware](https://img.shields.io/badge/Hardware-no%20verificado%20en%20banco-orange)](#pruebas-realizadas-y-simuladas)
[![Estado](https://img.shields.io/badge/Estado-portfolio%20%C2%B7%20v1.0-blueviolet)](#)

</div>

---

## Tabla de contenidos

- [Qué es este proyecto](#qué-es-este-proyecto)
- [Qué es un CashDro](#qué-es-un-cashdro)
- [Arquitectura PC ↔ CashDro](#arquitectura-pc--cashdro)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración de red](#configuración-de-red)
- [Configuración de la aplicación](#configuración-de-la-aplicación)
- [Uso de la CLI](#uso-de-la-cli)
- [Endpoints y operaciones de la API](#endpoints-y-operaciones-de-la-api)
- [Flujo completo de una venta](#flujo-completo-de-una-venta)
- [Manejo de errores](#manejo-de-errores)
- [Seguridad](#seguridad)
- [Pruebas realizadas y simuladas](#pruebas-realizadas-y-simuladas)
- [Solución de problemas](#solución-de-problemas)
- [Limitaciones conocidas](#limitaciones-conocidas)
- [Cómo se construyó este proyecto](#cómo-se-construyó-este-proyecto)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Documentación adicional](#documentación-adicional)
- [Referencias](#referencias)
- [Licencia](#licencia)

---

## Qué es este proyecto

**CashDroController** es una aplicación de consola en Python que actúa como **terminal de control** de un dispositivo **CashDro**: una máquina de gestión de efectivo que acepta billetes y monedas, los valida, los almacena y devuelve cambio con el mismo efectivo reciclado.

Corre en un PC Windows conectado por **Ethernet** al CashDro y habla con él mediante su **API REST sobre HTTPS** (`/Cashdro3WS/index3.php`). No hay drivers, SDK propietario ni puerto serie: sólo HTTP.

| Capacidad | Qué hace |
|---|---|
| **Cobrar** | Fija un importe, abre una operación de venta, espera a que el cliente introduzca efectivo y muestra ingresado/devuelto/cambio. |
| **Anular** | Cancela una operación en curso con su `operationId`, antes de que el efectivo se contabilice. |
| **Consultar estado** | Lee niveles por denominación, alertas activas y diagnóstico. |
| **Reconfigurar** | Cambia IP, usuario y contraseña en caliente, sin editar archivos. |

El flujo se traza paso a paso (`Paso 1/5`, `Paso 2/5`…), con colores ANSI y mensajes de error legibles.

> **Nota de honestidad.** Se desarrolló contra el manual de integración (`v22.01.21.11`) y se validó de forma estática y con simulaciones de la capa HTTP. **No se dispone del hardware físico**, así que no hay pruebas end-to-end. Los detalles marcados como *no verificados* deben confirmarse en banco antes de operar con dinero real. Ver [Pruebas realizadas y simuladas](#pruebas-realizadas-y-simuladas).

---

## Qué es un CashDro

Un **CashDro** es un dispositivo de **gestión y reciclaje de efectivo** (*cash deposit module* / *cash recycler*). Se instala en estaciones de servicio, tiendas 24 h, cajas de parking, peajes y mostradores donde se quiere automatizar la entrada y salida de metálico.

No vende: no conoce catálogo ni precios. Es un **periférico de efectivo**. El sistema de ventas le dice *"cobra 18,25 €"*, el cliente introduce dinero y el equipo responde *"recibido 20,00 €, devuelto 1,75 €"*. La contabilidad vive fuera.

```
┌──────────────────────────── CASH DRO ────────────────────────────┐
│  ┌───────────┐   ┌───────────┐   ┌────────────────────────────┐  │
│  │ Aceptador │   │ Aceptador │   │ Reciclador (cassettes y    │  │
│  │ billetes  │   │ monedas   │   │ tolvas de cambio)          │  │
│  └─────┬─────┘   └─────┬─────┘   └─────────────┬──────────────┘  │
│        └───────────────┴───────────────────────┘                 │
│                        │                                         │
│                 ┌──────▼────────┐                                │
│                 │  Controlador  │  ← API REST HTTPS (RJ45)       │
│                 │  + pantalla   │                                │
│                 └───────────────┘                                │
└──────────────────────────────────────────────────────────────────┘
```

### Principio físico de funcionamiento

El CashDro no "escanea" un billete como un escáner de escritorio: lo **transporta** a velocidad controlada por una ruta de rodillos y lo somete a varios sensores en línea. La validación es una **decisión combinada**, no una medida única.

```
Billete insertado
      │
      ▼
 [1] Entrada ──► ¿dimensiones plausibles? ──no──► devolver
      │ sí
      ▼
 [2] Transporte por rodillos (encoder)
      ├──► [3] CIS visible (reflectancia RGB)
      ├──► [4] Infrarrojo (hilo y tintas IR)
      ├──► [5] UV (fluorescencia del papel)
      ├──► [6] Magnético (tintas e hilo)
      └──► [7] Espesor / doble detección
      │
      ▼
 [8] Correlación con el patrón de la denominación
      ├── coincide ──► escrow ──► cassette ──► acreditado
      └── no coincide ──► rechazo y devolución
```

#### Validación de billetes

| Sensor | Qué mide | Para qué sirve |
|---|---|---|
| **CIS / visible** | Reflectancia por píxel en RGB | Imagen: dimensiones, márgenes, retrato, número de serie. |
| **Infrarrojo** | Absorción/transmisión IR | Hilo de seguridad y tintas IR, difíciles de falsificar. |
| **Ultravioleta** | Fluorescencia del papel | El papel de seguridad no fluoresce como el común. |
| **Magnético** | Tintas ferromagnéticas | Hilo magnético y tintas de determinadas denominaciones. |
| **Espesor** | Distancia entre rodillos o ultrasonidos | Evita aceptar dos billetes pegados como uno. |
| **Dimensiones** | Temporización de sensores | Descarta recortes, otra divisa o fotocopias a escala. |

El firmware compara el **vector de medidas** con la plantilla de cada denominación y calcula una confianza. Si supera el umbral, el billete pasa a *escrow* (bolsa temporal); si el cliente cancela, se devuelve sin entrar en caja.

#### Validación de monedas

Las monedas caen por una rampa y atraviesan una **bobina de inducción**:

1. **Diámetro** — por el tiempo que interrumpen un haz óptico o por el perfil de señal.
2. **Espesor y material** — la bobina mide **conductividad y permeabilidad**, que dependen de la aleación (acero niquelado, cuproníquel, latón, bimetálicas).
3. **Peso** — en validadores de gama alta, ayuda a discriminar.
4. **Clasificación** — la firma electromagnética se compara con la tabla de la divisa; lo no reconocido va a la bandeja de rechazo.

#### Reciclaje y devolución de cambio

La diferencia entre **aceptador** y **reciclador** es la reutilización:

- Un aceptador sólo acumula; para dar cambio necesita otra tolva cargada a mano.
- Un reciclador **guarda los billetes en cassettes por denominación** y las monedas en tolvas, y **devuelve cambio con esas mismas reservas**.

Ventajas: menos retiradas y menos carga manual. Contrapartida: hay que **planificar la mezcla**; si se llena de billetes de 50 € y no tiene de 5 €, no podrá devolver cambio fino.

En la API esto se ve en `askLevels`: unidades disponibles por denominación. Un nivel bajo es una alerta operativa, no un error de software.

---

## Arquitectura PC ↔ CashDro

```
┌─────────────────────────────┐            ┌──────────────────────────────┐
│  PC del operador (Windows)  │            │        CashDro               │
│                             │            │                              │
│  ┌───────────────────────┐  │  Ethernet  │  ┌────────────────────────┐  │
│  │ main.py  (menú/flujo) │  │  RJ45      │  │ Servidor web embebido  │  │
│  ├───────────────────────┤  │            │  │ Cashdro3WS/index3.php  │  │
│  │ cashdro_api.py        │──┼───────────►│  └───────────┬────────────┘  │
│  │ GET + JSON + reintentos│ │  HTTPS/TLS │              │               │
│  ├───────────────────────┤◄─┼───────────│  ┌───────────▼────────────┐  │
│  │ cashdro_cli.py (ANSI) │  │  cert.     │  │ Controlador de hardware│  │
│  ├───────────────────────┤  │  autofirm. │  │ rodillos, sensores,    │  │
│  │ config.py             │  │            │  │ cassettes, pantalla    │  │
│  └───────────────────────┘  │            │  └────────────────────────┘  │
└─────────────────────────────┘            └──────────────────────────────┘
```

Diagramas: [`architecture.svg`](docs/assets/architecture.svg) · [`network.svg`](docs/assets/network.svg) · [`cash-flow.svg`](docs/assets/cash-flow.svg)

- **Iniciativa única del PC.** El CashDro nunca llama al PC: no hay webhooks ni callbacks.
- **Estado en el equipo.** Vive en el `operationId` + `askOperation`. Si el PC se reinicia, la operación sigue allí y puede consultarse o anularse.
- **Autenticación por petición.** Cada URL lleva `name` y `password`; no hay cookies ni tokens.
- **Latencia baja.** En una LAN conmutada cada llamada tarda milisegundos; el cuello de botella es el cliente insertando dinero.

### Conexionado (pinout)

El CashDro no expone pines: no hay GPIO, RS-232 ni USB en esta integración. Todo va por Ethernet, así que el "pinout" es el cableado de red.

| Tramo | Conector | Cable | Notas |
|---|---|---|---|
| CashDro → switch | RJ45 hembra | Cat 5e/6, directo | Autonegociación 10/100; sin PoE. |
| Switch → PC | RJ45 | Cat 5e/6, directo | Misma subred que el CashDro. |
| PC → CashDro (directo) | RJ45 en ambos | Cat 5e/6, directo | Auto-MDI/X: no hace falta cable cruzado. |

**Calibración:** no se realiza desde este programa; sensores, denominaciones y límites se ajustan en el propio CashDro.

---

## Requisitos

| Componente | Mínimo | Recomendado | Notas |
|---|---|---|---|
| **Sistema operativo** | Windows 10 | Windows 10/11 x64 | Desarrollado en un PC Windows 10. |
| **Python** | 3.8 | 3.11 / 3.12 | Probado con CPython 3.12; usa `from __future__ import annotations`. |
| **Dependencia** | `requests>=2.25.0` | última 2.x | Única dependencia externa. `urllib3` llega con ella. |
| **Red** | Ethernet RJ45 | Switch dedicado | El CashDro debe ser alcanzable por IP; sin Wi-Fi en ese tramo. |
| **Consola** | 80×24 | 120×40 | Los marcos asumen ~60 columnas. |
| **Permisos** | Usuario normal | — | No requiere administrador. |

No hace falta Node.js, Java, .NET, driver USB/serie ni instalar el certificado del equipo.

---

## Instalación

### 1. Obtener el código

```bash
git clone https://github.com/wanderc137/CashDroController.git
cd CashDroController
```

### 2. Entorno virtual y dependencias

Las dependencias están en [`requirements.txt`](requirements.txt). Se recomienda un entorno virtual:

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

Secuencia completa en Windows:

```bat
cd C:\CashDroController
py -3 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -c "import requests; print(requests.__version__)"
```

Contenido de `requirements.txt`:

```
requests>=2.25.0
```

### 3. Comprobar sintaxis y arrancar

Define antes las variables de conexión (ver [Configuración](#configuración-de-la-aplicación)) y ejecuta:

```bat
python -m py_compile main.py cashdro_api.py cashdro_cli.py config.py
python main.py
```

### 4. (Opcional) Lanzador de escritorio

`CashDroController.bat`:

```bat
@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python main.py
if errorlevel 1 pause
```

`%~dp0` hace que funcione desde cualquier ubicación y `pause` evita que la ventana se cierre antes de leer un error.

> **Lanzador remoto.** `cashdro.sh` es un atajo para lanzar el programa en un PC Windows por SSH desde Linux. Contiene valores de ejemplo y **no debe llevar credenciales reales**. Ver [Seguridad](#seguridad).

---

## Configuración de red

### Direccionamiento IP

El CashDro sale de fábrica con IP privada fija, habitualmente en `192.0.2.0/24`. El PC debe estar en la misma subred. Placeholders usados en este documento:

| Equipo | IP de ejemplo | Máscara | Gateway | DNS |
|---|---|---|---|---|
| CashDro | `192.0.2.10` | `255.255.255.0` | *(vacío)* | *(vacío)* |
| PC de control | `192.0.2.20` | `255.255.255.0` | *(vacío)* | *(vacío)* |

En Windows: `Panel de control` → `Centro de redes` → `Cambiar configuración del adaptador` → clic derecho en Ethernet → `Propiedades` → `TCP/IPv4` → `Propiedades` → `Usar la siguiente dirección IP`.

> Si esa tarjeta también se usa para Internet, estás creando una red aislada y perderás la salida por ella. Lo correcto es dedicar un puerto al CashDro (o un switch aislado) y dejar la conectividad general por otra interfaz. Ver [`network.svg`](docs/assets/network.svg).

### Verificación

```bat
ping 192.0.2.10
ipconfig
curl.exe -k "https://192.0.2.10/Cashdro3WS/index3.php?operation=doTest&name=%CASHDRO_USER%&password=%CASHDRO_PASSWORD%"
```

Respuesta esperada:

```json
{"code":1,"response":{"errorMessage":"none"}}
```

`-k` desactiva la validación del certificado, igual que la aplicación. Un error `SSL certificate problem` es lo esperado con un certificado autofirmado y por eso se usa `-k`.

### Firewall de Windows

La aplicación **inicia** conexiones salientes al puerto 443; no escucha en ningún puerto. Si el firewall bloquea:

```powershell
New-NetFirewallRule -DisplayName "CashDroController" `
  -Direction Outbound -Program "C:\CashDroController\venv\Scripts\python.exe" `
  -RemoteAddress 192.0.2.10 -Action Allow
```

Ajusta ruta e IP. Para diagnosticar, prueba temporalmente sin firewall y vuelve a activarlo.

---

## Configuración de la aplicación

La configuración vive en `config.py`, un módulo con constantes tipadas. Los datos de conexión se leen de **variables de entorno**, con marcadores seguros por defecto.

| Constante | Variable de entorno | Por defecto |
|---|---|---|
| `CASHDRO_HOST` | `CASHDRO_HOST` | `192.0.2.10` (TEST-NET) |
| `CASHDRO_USER` | `CASHDRO_USER` | `USUARIO_CASHDRO` |
| `CASHDRO_PASSWORD` | `CASHDRO_PASSWORD` | `CLAVE_CASHDRO` |
| `POS_USER` | `POS_USER` | `USUARIO_CASHDRO` |
| `ALIAS_ID` | `ALIAS_ID` | `CAJA-01` |

| Constante | Por defecto | Significado |
|---|---|---|
| `API_BASE_PATH` | `"/Cashdro3WS/index3.php"` | Ruta del endpoint. |
| `REQUEST_TIMEOUT` | `10` | Segundos por llamada HTTP. |
| `MAX_RETRIES` | `3` | Reintentos ante error de conexión. |
| `MAX_RETRIES_SYSTEM_BUSY` | `3` | Reintentos para `-1900` (equipo ocupado). |
| `RETRY_DELAY_SYSTEM_BUSY` | `5` | Espera entre reintentos de `-1900`, en segundos. |
| `POLL_INTERVAL` | `2` | Intervalo de sondeo de `askOperation`. |
| `POLL_TIMEOUT` | `120` | Tiempo máximo de espera de una operación. |
| `POS_ID` | `"1"` | Identificador del punto de venta. |
| `AMOUNT_MAX` | `9999.99` | Tope de importe de la interfaz. |

**Antes de operar**, define `CASHDRO_HOST`, `CASHDRO_USER` y `CASHDRO_PASSWORD` en el entorno. Precedencia: variable de entorno > valor por defecto. No se carga ningún `.env` automáticamente; si lo usas, expórtalo antes de arrancar.

`ALIAS_ID` identifica al **terminal que envía la operación**, no al CashDro: úsalo para trazar qué caja abrió cada transacción.

Se relee `config.py` al arrancar; no hace falta tocar la lógica. Para redes lentas sube `REQUEST_TIMEOUT` y `MAX_RETRIES`; para clientes lentos, `POLL_TIMEOUT`; si varias cajas comparten un CashDro, sube `MAX_RETRIES_SYSTEM_BUSY` y baja `RETRY_DELAY_SYSTEM_BUSY`.

---

## Uso de la CLI

### Menú principal

Al arrancar, pide los datos de conexión (Enter mantiene el valor actual), ejecuta `doTest` y muestra:

```
+==================================================+
|          CASH DRO CONTROLLER                     |
|      Control de efectivo automatizado            |
+==================================================+

=== MENU PRINCIPAL ===
  1. Cobro - Realizar un cobro
  2. Anular transaccion - Cancelar operacion en curso
  3. Consultar estado - Ver niveles, alertas y diagnostico
  5. Configurar conexion - Cambiar IP/usuario/contraseña
  4. Salir - Terminar el programa
------------------------------------------------------
>> Seleccione una opcion [1-5]:
```

El orden visual (`5` antes de `4`) es deliberado: la reconfiguración es puesta a punto y no debe quedar pegada a las operaciones de caja, pero sigue accesible sin reiniciar.

Si la verificación inicial falla, el programa **no aborta**: avisa y ofrece continuar (`s/N`). Así se puede arrancar antes de que el CashDro esté listo y reintentar desde el menú.

### Opción 1 — Cobro

1. Pide el importe. Acepta `18.25` y `18,25`; rechaza texto, cero, negativos y valores sobre `9.999,99`.
2. Convierte a céntimos (`18.25 → 1825`) y llama a `startOperation` con `type=4`.
3. Recibe el `operationId` y llama a `acknowledgeOperationId`.
4. Sondea `askOperation` cada 2 s hasta `state="F"` o timeout de 120 s.
5. Muestra ingresado, devuelto y cambio, en euros.
6. Marca la operación como importada con `setOperationImported`.

```
>> Importe a cobrar: 18,25
  * Paso 1/5 Enviando startOperation...
  OK Operación iniciada - ID: OP-00000000-0000-0000-0000-000000000000
  * Paso 2/5 Confirmando operación (acknowledge)...
  OK Operación confirmada
  * Paso 3/5 Esperando que el usuario introduzca el efectivo...
  i Polling cada 2 segundos (timeout: 120s). Ctrl+C para cancelar.
  OK Operación finalizada por el CashDro
==================================================
         TRANSACCION COMPLETADA
  Total ingresado: 20.00
  Total devuelto: 1.75
  Cambio: 1.75
==================================================
  * Paso 5/5 Marcando operación como importada...
  OK Cobro completado exitosamente
```

### Opción 2 — Anular

Pide el `operationId`, consulta el estado y sólo cancela si no está finalizada:

```
>> Operation ID: OP-...
  i Estado actual: E
ATENCION: Esta seguro de que desea cancelar la operacion en curso?
>> Escriba 'SI' para confirmar: SI
  OK Transacción anulada correctamente
```

La confirmación es literal (`SI`) para evitar cancelaciones por un Enter de más. Si el cliente ya introdujo efectivo, la devolución física la decide el CashDro; el controlador sólo envía `finishOperation(type=2)`.

### Opción 3 — Consultar estado

Hace tres consultas y las presenta juntas:

- **Niveles** (`askLevels`): el diccionario del equipo, tal cual. Las claves dependen del firmware y de las denominaciones configuradas; no se reinterpretan para no inventar datos.
- **Alertas** (`askAlerts`): lista; si está vacía muestra `OK Sin alertas activas`.
- **Diagnóstico** (`askDiagnosis`): pares clave/valor; `ok`, `true`, `1` y `yes` se resaltan en verde.

Los nombres exactos (`bill_*`, `coin_*` o los de tu firmware) se muestran sin transformar. Ver [Limitaciones](#limitaciones-conocidas).

### Opción 5 — Configurar conexión

Cambia IP, usuario y contraseña sin editar `config.py` y vuelve a ejecutar `doTest`. Los valores **viven sólo en memoria**: al cerrar se pierden y se vuelve a `config.py`. Es intencional, para que una prueba puntual no deje una configuración equivocada persistente.

### Ctrl+C: cancelación en dos pasos

| Pulsación | Efecto |
|---|---|
| **Primera** | Marca `_cancel_requested`; el polling lo detecta y pide confirmación para cancelar la operación. |
| **Segunda** | Sale inmediatamente (`sys.exit(0)`). |

Así un Ctrl+C reflejo no deja una transacción abierta. Si se confirma, se envía `finishOperation(type=2)`; si el operador se arrepiente, la operación continúa.

---

## Endpoints y operaciones de la API

Base: `https://<host>/Cashdro3WS/index3.php`. Todas las llamadas son **GET** con parámetros en la query string. Comunes: `operation`, `name`, `password`. Los valores compuestos (`parameters`) viajan como **JSON serializado y URL-encoded**.

| Operación | Parámetros propios | Devuelve | Uso |
|---|---|---|---|
| `doTest` | — | `{"code":1,"response":{"errorMessage":"none"}}` | Verificar conectividad y credenciales. |
| `startOperation` | `type=4`, `parameters={"amount":"<céntimos>"}`, `posid`, `posuser`, `aliasid` | `response.operation.operationId` | Abrir una venta. |
| `acknowledgeOperationId` | `operationId` | `code=1` | Confirmar y poner en ejecución. |
| `askOperation` | `operationId` | `state`, `totalin`, `totalout`, `change`, `withError` | Sondeo del estado. |
| `finishOperation` | `operationId`, `type=1\|2` | `code=1` | Cerrar (1) o anular (2). |
| `setOperationImported` | `operationId` | `code=1` | Marcar como contabilizada. |
| `askLevels` | — | `response.levels` | Niveles por denominación. |
| `askAlerts` | — | `response.alerts` | Alertas activas. |
| `askDiagnosis` | — | `response.diagnosis` | Diagnóstico del equipo. |

### Ejemplos con curl

```bash
export CASHDRO_HOST=192.0.2.10
export CASHDRO_USER=USUARIO_CASHDRO
export CASHDRO_PASSWORD=CLAVE_CASHDRO
BASE="https://$CASHDRO_HOST/Cashdro3WS/index3.php"

# 1. Test de conexión
curl -sk "$BASE?operation=doTest&name=$CASHDRO_USER&password=$CASHDRO_PASSWORD"

# 2. Abrir venta de 10,00 EUR (1000 céntimos)
curl -sk -G "$BASE" \
  --data-urlencode "operation=startOperation" \
  --data-urlencode "name=$CASHDRO_USER" \
  --data-urlencode "password=$CASHDRO_PASSWORD" \
  --data-urlencode "type=4" \
  --data-urlencode 'parameters={"amount":"1000"}' \
  --data-urlencode "posid=1" \
  --data-urlencode "posuser=$CASHDRO_USER" \
  --data-urlencode "aliasid=CAJA-01"

# 3. Confirmar y consultar
curl -sk -G "$BASE" --data-urlencode "operation=acknowledgeOperationId" \
  --data-urlencode "name=$CASHDRO_USER" --data-urlencode "password=$CASHDRO_PASSWORD" \
  --data-urlencode "operationId=OP-..."
curl -sk -G "$BASE" --data-urlencode "operation=askOperation" \
  --data-urlencode "name=$CASHDRO_USER" --data-urlencode "password=$CASHDRO_PASSWORD" \
  --data-urlencode "operationId=OP-..."

# 4. Niveles, alertas y diagnóstico
curl -sk "$BASE?operation=askLevels&name=$CASHDRO_USER&password=$CASHDRO_PASSWORD"
curl -sk "$BASE?operation=askAlerts&name=$CASHDRO_USER&password=$CASHDRO_PASSWORD"
curl -sk "$BASE?operation=askDiagnosis&name=$CASHDRO_USER&password=$CASHDRO_PASSWORD"
```

`--data-urlencode` evita escapar a mano las llaves del JSON. Es la forma recomendada de probar `startOperation`; concatenar el JSON en la URL funciona pero es frágil.

### Formato de respuesta

```json
{"code":1,"response":{"errorMessage":"none","operation":{"operationId":"..."}}}
{"code":-1,"response":{"errorMessage":"Authentication Failed"}}
```

Detalle importante: según firmware, `operation` puede venir **anidado dos veces** (`response.operation.operation.operationId`). `start_operation`, `ask_operation`, `ask_levels`, `ask_alerts` y `ask_diagnosis` desenvuelven ese nivel extra cuando existe, de modo que el resto del programa siempre ve la estructura plana.

---

## Flujo completo de una venta

```
Operador ──importe 18,25──► main.py ──startOperation──► CashDroAPI ──GET──► CashDro
                              │                            │                  │
                              │◄───── operationId ─────────┤◄─────────────────┤
                              ├──────acknowledge──────────►├─────────────────►│
                              │        (espera efectivo)   │   state=I/Q/E    │
                              │◄─────── state=F ───────────┤◄─────────────────┤
                              │   totalin=2000, out=175    │                  │
                              ├──set_operation_imported───►├─────────────────►│
```

### Máquina de estados

| Estado | Significado | Qué hace el controlador |
|---|---|---|
| `I` | Inicial, pendiente de `acknowledge` | Sigue esperando (transitorio). |
| `Q` | En cola | Sigue esperando. |
| `E` | Ejecutándose: espera efectivo | Sigue esperando. |
| `F` | Finalizada | Comprueba `withError`; si es `true`, la trata como fallida. |
| *(otro)* | No documentado | Aborta con `CashDroError(-99)` y el mensaje del equipo. |
| *(vacío)* | Sin dato todavía | Se tolera y se reintenta al siguiente ciclo. |

### Conversión de importes

La API trabaja en **céntimos enteros** para evitar errores de coma flotante:

```
Entrada : "18,25" → 18.25 (float)
Envío   : int(round(18.25 * 100)) = 1825 → "1825"
Recibe  : "2000" / "175"
Muestra : 2000 / 100 = "20.00", 175 / 100 = "1.75"
```

`int(round(...))` es importante: `18.25 * 100` puede dar `1824.9999...` en binario y un `int()` truncado cobraría un céntimo de menos.

`startOperation` + `acknowledge` tardan menos de un segundo en LAN; la espera de efectivo la domina el cliente; la detección de `F` añade hasta 2 s de retraso. El **timeout duro es de 120 s**: si el cliente no completa el pago, se lanza `TimeoutError` y se intenta `finishOperation(type=2)`. En entornos lentos conviene subir `POLL_TIMEOUT`.

---

## Manejo de errores

### Códigos del CashDro

| Código | Mensaje | Interpretación | Acción |
|---|---|---|---|
| `-1` | Authentication Failed | Usuario/contraseña incorrectos. | Revisar credenciales y `doTest`. |
| `-2` | Operation not queued / not found | ID inexistente, expirado o ya cerrado. | Verificar el ID. |
| `-3` | Wrong amount / Invalid parameters | Importe inválido o parámetros mal formados. | Comprobar céntimos y JSON. |
| `-4` | User does not have permission | El usuario no puede ejecutar eso. | Usar un rol con permisos. |
| `-99` | Invalid Parameters | Error genérico o estado inesperado. | Revisar petición y equipo. |
| `-1900` | System busy | Equipo ocupado con otra operación. | Reintento automático (3 × 5 s). |
| `-998` | Can't start operation | Estado físico impide iniciar. | Revisar atascos, sensores, cassette. |
| `-999` | Service is not running | Servicio interno caído. | Reiniciar; si persiste, soporte. |

### Excepciones de la aplicación

| Excepción | Origen | Tratamiento |
|---|---|---|
| `CashDroError(code, message)` | `code != 1`, estado inesperado o falta de `operationId`. | Se muestra con código y texto; si había operación abierta, se intenta anular. |
| `ConnectionError` | Host inalcanzable, cable, IP, firewall. | 3 intentos con 1 s; luego mensaje de conexión. |
| `Timeout` | El equipo no responde en `REQUEST_TIMEOUT`. | Igual que el anterior. |
| `TimeoutError` | El sondeo supera `POLL_TIMEOUT`. | Se intenta `finishOperation(type=2)`. |
| `KeyboardInterrupt` | Ctrl+C o `cancel_event`. | Pide confirmación y cancela. |
| `ValueError` | Importe no numérico. | Se rechaza al validar, sin llamar a la API. |

### Política de reintentos

Hay **dos contadores independientes** en `_call()`:

```
Para cada intento (1..MAX_RETRIES):
    GET → respuesta
    ├── code == 1            → devolver
    ├── code == -1900        → si quedan reintentos de busy:
    │                           esperar 5 s, decrementar, continuar
    │                          si no: CashDroError(-1900)
    ├── otro code != 1       → CashDroError(code)
    └── ConnectionError/Timeout → esperar 1 s, siguiente intento
Al agotar: RequestException("Error de conexión tras N intentos")
```

Un `-1900` **no consume** el contador de red, y un error de conexión **no consume** el de *busy*. Mezclarlos hacía que un equipo momentáneamente ocupado agotase los reintentos de red y viceversa. Se corrigió tras la auditoría y se cubrió con simulaciones. Si todos los intentos fueron `-1900`, se lanza `CashDroError(-1900)` con mensaje claro en lugar de una `RequestException` con `None`.

### Estrategia de cancelación

`operacion_cobro()` inicializa `operation_id = ""` **antes** del `try`. Si algo falla después de `startOperation`, el `except` sabe si hay una operación abierta y envía `finishOperation(type=2)`. Sin esa inicialización, un fallo temprano producía `UnboundLocalError` y dejaba la transacción huérfana.

---

## Seguridad

El diseño de la API impone debilidades que el cliente no puede eliminar. Documentarlas es parte del trabajo.

### Credenciales en la URL

Cada petición lleva `name` y `password` como parámetros GET:

```
https://192.0.2.10/Cashdro3WS/index3.php?operation=doTest&name=...&password=...
```

- La contraseña viaja **en claro dentro de la URL**, cifrada sólo por TLS.
- Queda en logs de proxies, capturas de red e historial de `curl`.
- `requests` no registra URLs por defecto, pero **activar logging de depuración las expondría**.
- No es corregible desde el cliente: es el contrato del fabricante.

Mitigaciones aplicadas:

1. **No se registran URLs**; la aplicación no habilita logging de `urllib3`/`requests`.
2. **No se muestran credenciales** en pantalla.
3. **Red aislada**: el tramo PC–CashDro sin salida a Internet.
4. **Credenciales fuera del repositorio**: marcadores en `config.py` y gestor de secretos si aplica.

### TLS con certificado autofirmado

| Propiedad | Estado |
|---|---|
| Confidencialidad (cifrado) | ✅ Sí |
| Integridad | ✅ Sí (sin MITM) |
| Autenticación del servidor | ❌ No verificada |
| Resistencia a MITM con acceso a la red | ❌ Baja |

No se debe "arreglar" con `verify=True` sin más: rompería la conexión. Si se exige, el camino es **fijar el certificado** (pinning) o instalar ese certificado como CA de confianza en el PC. Queda fuera del alcance de esta versión.

### Modelo de amenazas

| Amenaza | Impacto | Mitigación |
|---|---|---|
| Sniffer en la LAN (credenciales en GET) | Alto | Red dedicada, VLAN, puerto aislado. |
| MITM por TLS sin validación | Alto | Aislar el segmento; pinning (futuro). |
| Otro software usando el equipo (`-1900`) | Medio | Un cliente por equipo. |
| Robo del PC con `config.py` | Alto | Cifrado de disco, secretos fuera del repo. |

### Recomendaciones de despliegue

- **Switch dedicado** o VLAN entre PC y CashDro, sin gateway ni reenvío de puertos.
- Usuario de API con **permisos mínimos**, contraseñas rotadas y auditoría de operaciones contra los cierres de caja.
- **No** commitear `config.py` real ni scripts con contraseñas.

---

## Pruebas realizadas y simuladas

**No se dispone de un CashDro físico en el entorno de desarrollo.** Cualquier afirmación de "probado" debe leerse con ese contexto.

### Matriz de verificación

| Prueba | Método | Resultado | Confianza |
|---|---|---|---|
| Sintaxis de los 4 módulos | `python -m py_compile` | ✅ Sin errores | Alta |
| Importación y arranque | Import en intérprete, sin flujo | ✅ Sin errores | Alta |
| Auditoría estática | Integridad, seguridad, estabilidad | ✅ 8 incidencias corregidas | Alta |
| Reintentos `-1900` | 6 escenarios con HTTP falso | ✅ 6/6 | Media-alta |
| JSON anidado | Casos con y sin doble anidación | ✅ | Media |
| Euros ↔ céntimos | `18.25`, `0.01`, `9999.99` | ✅ | Alta |
| Validación de importes | Texto, cero, negativo, coma | ✅ | Alta |
| Conexión real | — | ❌ No ejecutada | — |
| Handshake TLS real | — | ❌ No ejecutado | — |
| Forma del JSON del firmware | Inferida del manual | ⚠️ | Baja-media |
| Venta completa con efectivo | — | ❌ No ejecutada | — |
| Consola Windows real | Revisada por diseño | ⚠️ | Media |

### Qué falta para "validado en producción"

1. **Banco con hardware**: `doTest`, venta, anulación y estado contra un equipo real.
2. **Confirmar el JSON**: campos `totalin`, `totalout`, `change`, `withError`, `state` y claves de `askLevels`.
3. **Prueba de certificado**: capturarlo y decidir entre pinning o CA interna.
4. **Consola Windows y concurrencia**: codepage/ANSI, dos cajas contra un CashDro y desconexión del cable a mitad de operación.

Es deuda técnica abierta, no un hecho consumado.

---

## Solución de problemas

### No conecta

```bat
ping 192.0.2.10
ipconfig
curl.exe -k "https://192.0.2.10/Cashdro3WS/index3.php?operation=doTest&name=USUARIO&password=CLAVE"
```

| Comprobación | Esperado |
|---|---|
| `ping` responde | Conectividad L3 correcta. |
| `ipconfig` en la misma subred | `192.0.2.20/24`. |
| `curl` devuelve `code:1` | API y credenciales correctas. |
| `curl` con timeout | Cable, switch, IP o firewall. |
| `curl` con error SSL | Normal: usa `-k`. |

Si `curl` funciona y la aplicación no, revisa `config.py` o el firewall para `python.exe`.

### `Authentication Failed` (-1)

Contraseña mal escrita, usuario inexistente o bloqueo por intentos fallidos. El equipo distingue mayúsculas en la contraseña. Espera y reintenta.

### `System busy` (-1900) persistente

Otra aplicación usa el CashDro (TPV, otra caja, software del fabricante), o hay una operación anterior sin cerrar. El firmware suele admitir un cliente a la vez.

### Timeout de sondeo a los 120 s

El cliente no introdujo efectivo, el importe no se alcanza con las denominaciones disponibles, o hay atasco/sensor sucio. Consulta alertas y diagnóstico; sube `POLL_TIMEOUT` si el flujo es lento.

### `No se recibió operationId en la respuesta`

El equipo devolvió una estructura distinta a la esperada, o hay una operación previa abierta. Comprueba la respuesta cruda con `curl` y compárala con el manual de tu firmware.

### La operación finaliza con error

`state="F"` y `withError="true"`: billete atascado, devolución incompleta o cassette lleno. El controlador lo trata como fallo (`CashDroError(-99)`); **no** debe contabilizarse como venta.

### La consola se ve mal

Usa Windows Terminal, `cmd.exe` o PowerShell modernos; una fuente con bloques (Consolas, Cascadia Mono); buffer 120×40 en `Propiedades → Diseño`; y `chcp 65001` si los acentos salen corruptos.

### Se cierra al hacer doble clic

Arranca desde consola para ver el error:

```bat
cd C:\CashDroController
venv\Scripts\activate
python main.py
pip list
```

### No se puede instalar `requests`

Sin Internet: descarga el `.whl` en otro equipo y usa `pip install --no-index --find-links . requests`. En Python "embeddable", el código ya inserta su directorio en `sys.path` para funcionar en esa modalidad.

---

## Limitaciones conocidas

1. **Sin validación con hardware real.** El comportamiento del dispositivo está inferido del manual; es la limitación principal.
2. **Credenciales en texto plano.** En `config.py` y en la URL; sin Credential Manager ni vault.
3. **TLS sin autenticación.** `verify=False` es funcional pero no seguro frente a MITM.
4. **Un solo CashDro por proceso.** La clase admite varias instancias, pero la interfaz no permite elegir.
5. **Sin persistencia local.** Ni base de datos, ni log en archivo, ni exportación: el histórico vive en el CashDro.
6. **Sin contabilidad.** No hay cierres de caja, arqueos ni conciliación; es un mando, no un ERP.
7. **Denominaciones sin normalizar.** `askLevels` se muestra tal cual.
8. **Un único tipo de operación.** Sólo `type=4` (venta).
9. **Interfaz monolingüe de consola.** Sin GUI ni internacionalización.
10. **`cashdro.sh` con valores de ejemplo.** Atajo de desarrollo, no mecanismo de despliegue seguro.

---

## Cómo se construyó este proyecto

Pipeline de agentes especializados en cuatro etapas:

1. **Análisis** — Se tradujo el requisito a una especificación: flujo de venta, anulación, consultas, códigos de error, timeouts y casos borde, con la API mapeada operación por operación.
2. **Implementación** — Cuatro módulos con responsabilidades separadas: `config.py` (parámetros), `cashdro_api.py` (transporte y contrato), `cashdro_cli.py` (presentación) y `main.py` (orquestación). Regla: la capa de API no imprime y la de consola no hace HTTP.
3. **Auditoría** — Revisión estática de integridad, seguridad y estabilidad. Se detectaron y corrigieron **ocho incidencias**, entre ellas: `operation_id` usado antes de asignarse, el `-1900` cayendo en una excepción genérica, Ctrl+C que cerraba sin cancelar y duplicación del código de error en los mensajes.
4. **Documentación** — README, manual de operador, guía de desarrollador, referencias, bitácora y diagramas.

### Decisiones de diseño

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| GET con query params | POST con body JSON | Es lo que impone la API. |
| `requests` | `urllib` estándar | Menos código, timeouts y SSL más claros; una sola dependencia. |
| Céntimos enteros | `float`/`Decimal` | La API usa enteros; evita redondeos. |
| Sondeo cada 2 s | WebSocket / long-polling | El firmware no ofrece push. |
| `verify=False` | `verify=True` | El certificado es autofirmado; con `True` no hay conexión. |
| Colores ANSI | `colorama` | Cero dependencias extra; Windows 10 los soporta. |
| Consola | GUI (Tkinter/Qt) | El requisito era consola; menos superficie y más fácil de auditar. |
| Config en módulo Python | `.ini` / `.env` | Menos piezas; se relee al arrancar. |
| Reintentos separados | Un solo contador | `-1900` y caída de red son fallos distintos. |

### Lecciones

- **Normalizar la respuesta pronto.** El JSON cambia entre versiones; aislar esa variabilidad en cinco métodos evita que se filtre a toda la aplicación.
- **Los timeouts son parte del contrato.** Sin `POLL_TIMEOUT`, una venta abandonada bloquea la caja.
- **El estado no es del cliente.** Reiniciar el PC no cancela nada; hay que consultar y anular explícitamente.
- **La seguridad del transporte no se negocia.** Si la API exige credenciales en GET, la defensa real es segmentar la red.
- **Documentar lo no probado es parte del trabajo.** Un README que dice "funciona" sin hardware es una promesa; uno que separa lo verificado de lo inferido es una herramienta.

---

## Estructura del repositorio

```
CashDroController/
├── main.py                  # Punto de entrada, menú y flujo
├── cashdro_api.py           # Cliente REST (CashDroAPI, CashDroError)
├── cashdro_cli.py           # Presentación en consola
├── config.py                # Constantes de configuración
├── requirements.txt         # requests>=2.25.0
├── cashdro.sh               # Lanzador remoto (sin secretos reales)
├── LICENSE                  # MIT
├── README.md                # Este documento
└── docs/
    ├── datasheet.md         # Manual del operador
    ├── developer.md         # Guía de desarrollo y API interna
    ├── REFERENCES.md        # Fuentes y lecturas
    ├── BITACORA.md          # Decisiones, problemas y lecciones
    └── assets/
        ├── architecture.svg # PC ↔ CashDro: capas y módulos
        ├── cash-flow.svg    # Recorrido físico del efectivo
        └── network.svg      # Topología de red aislada
```

---

## Documentación adicional

| Documento | Para quién | Contenido |
|---|---|---|
| [`docs/datasheet.md`](docs/datasheet.md) | Operadores y responsables de tienda | Puesta en marcha, procedimientos, lectura de estados, errores, mantenimiento. |
| [`docs/developer.md`](docs/developer.md) | Desarrolladores | Arquitectura, API de clases y funciones, configuración, extensión. |
| [`docs/REFERENCES.md`](docs/REFERENCES.md) | Todos | Manual del fabricante, Python/requests/TLS, lecturas de efectivo. |
| [`docs/BITACORA.md`](docs/BITACORA.md) | Mantenedores | Incidencias, enfoques descartados, decisiones y lecciones. |

---

## Referencias

- **Manual de integración CashDro v22.01.21.11** — contrato de la API (`index3.php`), operaciones, códigos de error y formatos. Documento del fabricante distribuido con el equipo.
- Python: <https://docs.python.org/3/>
- `requests`: <https://requests.readthedocs.io/>
- `urllib3` y TLS: <https://urllib3.readthedocs.io/>
- RFC 9110 (HTTP) y RFC 8446 (TLS 1.3).
- OWASP: *Transport Layer Security* y *Secrets Management Cheat Sheets*.

Lista ampliada con notas de uso: [`docs/REFERENCES.md`](docs/REFERENCES.md).

---

## Licencia

**MIT**. Consulta [`LICENSE`](LICENSE).

```
MIT License

Copyright (c) 2026 wanderc137
```

El software se proporciona "tal cual", sin garantía de ningún tipo. **No está certificado para operar con dinero real sin validación previa en banco con el hardware objetivo.** La configuración, el cumplimiento fiscal y la seguridad de la red son responsabilidad del integrador.
