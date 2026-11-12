# Datasheet — CashDroController

**Manual del operador y ficha técnica**

Versión 1.0 · Aplicación de consola para Windows · API REST sobre HTTPS

---

## Índice

1. [Presentación y alcance](#1-presentación-y-alcance)
2. [Roles y responsabilidades](#2-roles-y-responsabilidades)
3. [Puesta en marcha diaria](#3-puesta-en-marcha-diaria)
4. [La interfaz de consola](#4-la-interfaz-de-consola)
5. [Procedimientos de operación](#5-procedimientos-de-operación)
6. [Lectura del estado del equipo](#6-lectura-del-estado-del-equipo)
7. [Errores y actuación](#7-errores-y-actuación)
8. [Situaciones especiales](#8-situaciones-especiales)
9. [Mantenimiento y efectivo](#9-mantenimiento-y-efectivo)
10. [Seguridad](#10-seguridad)
11. [Especificaciones técnicas](#11-especificaciones-técnicas)
12. [Preguntas frecuentes](#12-preguntas-frecuentes)
13. [Glosario](#13-glosario)

---

## 1. Presentación y alcance

CashDroController es el programa que permite a un cajero **cobrar con efectivo** a través de un dispositivo CashDro y **consultar su estado**, desde el teclado de un PC Windows.

### Qué hace

- Abre una operación de venta por un importe exacto.
- Espera a que el cliente introduzca billetes y monedas.
- Muestra cuánto se ingresó, cuánto se devolvió y cuál fue el cambio.
- Permite anular una operación antes de contabilizarla.
- Informa de niveles de efectivo, alertas y diagnóstico del equipo.

### Qué no hace

- **No** calcula precios ni gestiona un catálogo: el importe lo teclea el operador.
- **No** guarda un histórico: no hay base de datos ni exportación.
- **No** hace cierres de caja ni arqueos.
- **No** controla la apertura física de cassettes ni la cerradura.
- **No** sustituye al software de gestión del fabricante.

> El CashDro es un periférico de efectivo. La venta "existe" para el negocio cuando el sistema de facturación la registra; este programa sólo mueve el dinero y devuelve el resultado.

### Requisitos para operar

| Elemento | Necesario |
|---|---|
| PC con Windows 10/11 | Sí |
| Python 3.8 o superior y `requests` | Sí (instalado por el técnico) |
| Cable Ethernet al CashDro | Sí |
| Credenciales de la API | Sí (las configura el técnico) |
| Impresora de tickets | No (la venta se cobra en el sistema de caja) |

---

## 2. Roles y responsabilidades

| Rol | Responsabilidad |
|---|---|
| **Operador de caja** | Arranca el programa, cobra, anula y consulta el estado. No cambia configuración. |
| **Responsable de tienda** | Supervisa niveles y alertas, autoriza anulaciones y organiza la carga/retirada de efectivo. |
| **Técnico de sistemas** | Instala Python y dependencias, configura `config.py`, red y firewall; resuelve incidencias de conectividad. |
| **Técnico del CashDro** | Calibra sensores, sustituye cassettes, actualiza firmware y atiende atascos graves. |

Regla práctica: si el problema es **de red o del programa**, lo ve el técnico de sistemas; si es **físico del equipo** (atasco, sensor, cassette), lo ve el técnico del CashDro.

---

## 3. Puesta en marcha diaria

### 3.1. Checklist de apertura

| # | Comprobación | Cómo |
|---|---|---|
| 1 | CashDro encendido y sin alertas en su pantalla | Mirar el display del equipo |
| 2 | Cable Ethernet conectado en ambos extremos | Inspección visual; LED de enlace |
| 3 | PC con IP en la misma subred | `ipconfig` |
| 4 | Respuesta al ping | `ping 192.0.2.10` |
| 5 | Programa arranca y pasa `doTest` | `python main.py` |
| 6 | Niveles suficientes para dar cambio | Opción 3 del menú |
| 7 | Sin alertas activas | Opción 3 del menú |

### 3.2. Arranque

```bat
cd C:\CashDroController
venv\Scripts\activate
python main.py
```

Al iniciar, el programa pide IP, usuario y contraseña. **Enter** mantiene el valor por defecto. Después ejecuta `doTest`:

- Si la conexión es correcta: `OK Conexion establecida correctamente`.
- Si falla: muestra el error y pregunta `¿Desea continuar de todas formas? (s/N)`.

Continuar tiene sentido si el CashDro está arrancando todavía; se puede reintentar desde el menú. Si el error es de credenciales, continuar no sirve: hay que corregirlas.

### 3.3. Cierre

1. Termina cualquier operación en curso (cobrar o anular).
2. Opción **4 — Salir**.
3. No apagues el CashDro si va a seguir en uso; su ciclo de encendido lo decide el responsable del equipo.

---

## 4. La interfaz de consola

### 4.1. Menú

```
=== MENU PRINCIPAL ===
  1. Cobro - Realizar un cobro
  2. Anular transaccion - Cancelar operacion en curso
  3. Consultar estado - Ver niveles, alertas y diagnostico
  5. Configurar conexion - Cambiar IP/usuario/contraseña
  4. Salir - Terminar el programa
```

Se elige escribiendo el número y pulsando Enter. Cualquier otra tecla muestra `Opcion invalida` y vuelve a preguntar.

### 4.2. Convenciones visuales

| Marca | Significado |
|---|---|
| `OK` en verde | Paso completado correctamente. |
| `FAIL` en rojo | Paso fallido. |
| `*` en cian | Acción en progreso. |
| `i` en azul | Información o ayuda. |
| `!` en amarillo | Advertencia o alerta del equipo. |
| `>>` | Solicitud de datos al operador. |
| `X` en rojo | Entrada rechazada. |

Los colores son ANSI. En Windows Terminal, `cmd.exe` y PowerShell modernos se ven correctamente; en consolas muy antiguas pueden aparecer códigos extraños, sin afectar a la operación.

### 4.3. Atajos y palabras clave

| Entrada | Efecto |
|---|---|
| `cancelar`, `salir`, `q`, `quit`, `exit` | Cancela la captura del importe. |
| `SI` (mayúsculas o minúsculas) | Confirma una cancelación. |
| `s` | Responde "sí" a continuar sin conexión. |
| **Ctrl+C** una vez | Solicita cancelar la operación en curso. |
| **Ctrl+C** dos veces | Sale del programa inmediatamente. |

---

## 5. Procedimientos de operación

### 5.1. Cobrar

**Cuándo:** el cliente va a pagar en efectivo un importe conocido.

1. Opción **1**.
2. Teclea el importe: `18,25` o `18.25`. Máximo `9.999,99`.
3. Confirma con Enter.
4. El programa abre la operación y muestra el ID.
5. Indica al cliente que introduzca el dinero en el CashDro.
6. Espera: la pantalla muestra `Esperando que el usuario introduzca el efectivo...`.
7. Al completarse, aparece el resumen: total ingresado, total devuelto y cambio.
8. El programa marca la operación como importada.
9. Registra la venta en el sistema de caja habitual.

**Qué ve el cliente:** el importe pendiente en la pantalla del CashDro. Si introduce de más, el equipo devuelve cambio con sus reservas.

**Si el cliente se arrepiente antes de terminar:** Ctrl+C, confirmar `SI`; se envía la anulación.

**Errores de tecleo:** el programa rechaza texto, cero, negativos y cantidades fuera de rango sin llamar al equipo. Corrige y vuelve a escribir.

### 5.2. Anular

**Cuándo:** una operación quedó abierta porque el cliente se fue, hubo un error de importe o el terminal se bloqueó.

1. Opción **2**.
2. Teclea el `operationId`.
3. El programa consulta el estado.
   - `F`: ya está finalizada; no se anula.
   - Otro estado: pide confirmación.
4. Escribe `SI`.
5. Se envía `finishOperation(type=2)`.

**Si no conoces el ID:** inicia la operación y anótalo de la pantalla; o consulta el estado (opción 3) y revisa el equipo. El ID no se puede "adivinar".

**Consecuencia física:** si ya había efectivo dentro, el CashDro decide si lo devuelve. No fuerces la devolución a mano.

### 5.3. Consultar estado

**Cuándo:** al abrir, al cerrar, ante una alerta o si un cobro no avanza.

Opción **3** y espera tres consultas:

```
Niveles de efectivo:
  <denominacion>: <unidades>
Alertas activas:
  OK Sin alertas activas
Diagnostico:
  <clave>: <valor>
```

Los nombres de las claves los define el firmware. No los traduzcas ni los interpretes como si fueran un formato fijo.

### 5.4. Cambiar la conexión

**Cuándo:** el CashDro cambió de IP, se cambió la contraseña o hay que probar otro equipo.

1. Opción **5**.
2. Teclea los nuevos valores (Enter mantiene el actual).
3. El programa vuelve a ejecutar `doTest`.

Los valores **no se guardan**: al cerrar se vuelve a `config.py`, que toma los datos de las variables de entorno (o de sus marcadores por defecto). Si el cambio debe ser permanente, pide al técnico que edite el archivo.

---

## 6. Lectura del estado del equipo

### 6.1. Niveles de efectivo

Cada entrada es **unidades disponibles de una denominación**, no euros. Ejemplo ilustrativo (las claves reales dependen del firmware):

| Clave (ejemplo) | Unidades | Valor |
|---|---|---|
| `bill_50` | 10 | 500,00 € |
| `bill_20` | 25 | 500,00 € |
| `bill_10` | 40 | 400,00 € |
| `bill_5` | 15 | 75,00 € |
| `coin_2` | 100 | 200,00 € |
| `coin_1` | 80 | 80,00 € |
| `coin_050` | 50 | 25,00 € |

**Cómo usarlo:** si el cambio habitual es de 1–5 €, vigila las denominaciones pequeñas. Un cassette lleno de 50 € no ayuda a devolver 1,75 €.

### 6.2. Alertas

La lista puede venir vacía (`OK Sin alertas activas`) o con códigos y descripciones. Interpretación operativa:

| Tipo de alerta | Significado | Actuación |
|---|---|---|
| Cassette/depósito casi lleno | Queda poco margen | Programar retirada. |
| Cassette/depósito lleno | No admite más unidades | Retirar antes de seguir cobrando. |
| Nivel bajo de cambio | Faltan denominaciones pequeñas | Cargar cambio. |
| Atasco | Papel o moneda bloqueada | Parar, avisar al técnico. |
| Puerta abierta | Acceso físico | Cerrar y verificar. |
| Error de sensor | Lectura inconsistente | Limpieza o servicio técnico. |

Los códigos concretos los define el fabricante; usa la descripción que muestra el equipo como referencia principal.

### 6.3. Diagnóstico

Pares clave/valor sobre el estado interno. Los valores `ok`, `true`, `1` y `yes` se muestran en verde; el resto, en blanco. Un valor distinto de `ok` no siempre es una avería: puede ser un contador o una versión. Ante duda, consulta el manual del CashDro.

---

## 7. Errores y actuación

### 7.1. Errores de la API

| Código | Texto típico | Qué significa para el operador | Qué hacer |
|---|---|---|---|
| `-1` | Authentication Failed | Usuario o contraseña incorrectos. | Avisar al técnico; no reintentar en bucle. |
| `-2` | Operation not found | El ID no existe o caducó. | Verificar el ID; no insistir. |
| `-3` | Wrong amount | Importe o parámetros inválidos. | Revisar el importe y repetir. |
| `-4` | No permission | El usuario no puede hacer eso. | Usar el usuario autorizado. |
| `-99` | Invalid Parameters | Error genérico. | Anotar el mensaje y avisar. |
| `-1900` | System busy | El equipo está ocupado. | El programa reintenta solo (3 × 5 s). |
| `-998` | Can't start operation | El equipo no puede iniciar. | Revisar alertas y estado físico. |
| `-999` | Service not running | Servicio interno caído. | Reiniciar el CashDro; si persiste, soporte. |

### 7.2. Errores del programa

| Mensaje | Causa | Actuación |
|---|---|---|
| `Error de conexión tras N intentos` | Sin red, IP incorrecta, firewall. | Ping, cable, `ipconfig`; avisar al técnico. |
| `La operación no finalizó tras 120 segundos` | El cliente no pagó. | Anular la operación. |
| `Importe invalido` | Texto o formato incorrecto. | Teclear un número. |
| `El importe debe ser mayor que cero` | Cero o negativo. | Corregir. |
| `El importe maximo es 9,999.99` | Fuera de rango. | Dividir la venta o corregir. |
| `No se recibió operationId` | Respuesta inesperada del equipo. | Consultar estado; avisar al técnico. |
| `La operación finalizó con error` | Atasco, devolución incompleta. | **No** contabilizar la venta; revisar el equipo. |

### 7.3. Regla de oro ante un error

1. **No repitas la operación a ciegas.** Puede haber una transacción abierta.
2. Consulta el estado (opción 3).
3. Anula si procede (opción 2).
4. Anota el mensaje exacto y la hora.
5. Si el error se repite, para y avisa.

---

## 8. Situaciones especiales

### 8.1. El cliente se va sin terminar

La operación queda abierta esperando efectivo. Pulsa Ctrl+C, confirma `SI` y anula. Si no lo haces, el equipo queda ocupado y el siguiente cobro puede recibir `-1900`.

### 8.2. Se va la red a mitad de operación

El programa muestra un error de conexión e intenta anular, pero **puede no lograrlo** si no hay red. Cuando vuelva la conexión, consulta el estado y anula manualmente si sigue abierta. El efectivo ya introducido está físicamente en el equipo: no se pierde, pero puede requerir intervención.

### 8.3. No hay cambio suficiente

El cobro puede iniciarse y no completarse porque el equipo no puede devolver la diferencia. Consulta niveles antes de ventas grandes. Si ocurre, anula y cobra por otro medio.

### 8.4. Atasco

1. No fuerces el mecanismo.
2. Anula la operación si el programa lo permite.
3. Avisa al técnico del CashDro; la limpieza interna es su responsabilidad.
4. No abras cassettes sin autorización.

### 8.5. Cierre de caja

Este programa no genera cierre. Para el arqueo:

1. Anula cualquier operación abierta.
2. Registra los niveles (opción 3) o haz una captura.
3. Compara con el sistema de facturación.
4. La retirada de efectivo se hace con el procedimiento del fabricante y la política de la empresa.

### 8.6. Cambio de turno

- Anula operaciones abiertas.
- Comprueba que no hay alertas.
- Deja el programa en el menú principal (no a mitad de un cobro).
- Entrega el `operationId` de cualquier incidencia.

---

## 9. Mantenimiento y efectivo

### 9.1. Rutinas recomendadas

| Frecuencia | Tarea | Responsable |
|---|---|---|
| Cada apertura | Verificar conexión, niveles y alertas. | Operador |
| Semanal | Limpieza externa del equipo según manual. | Personal de tienda |
| Según niveles | Cargar cambio / retirar exceso. | Responsable |
| Mensual | Revisar logs y alertas recurrentes. | Responsable + técnico |
| Anual | Mantenimiento del fabricante. | Servicio técnico |

### 9.2. Qué no hacer

- No introducir billetes rotos, grapados o con cinta: provocan atascos.
- No golpear el equipo ni forzar la boca de entrada.
- No abrir cassettes sin llave y autorización.
- No limpiar sensores con líquidos no homologados.
- No dejar el PC desatendido con la sesión abierta en el menú.

### 9.3. Calibración

**Este programa no calibra nada.** La calibración de sensores, las denominaciones aceptadas y los límites de los cassettes se configuran en el propio CashDro (panel frontal o software del fabricante). El controlador asume un equipo ya calibrado.

Si sospechas un problema de calibración (rechaza billetes buenos, acepta dudosos, cuenta mal), el síntoma aparecerá en el equipo, no en la consola: abre una incidencia con el servicio técnico.

---

## 10. Seguridad

### 10.1. Del efectivo

- El CashDro es una caja fuerte; el programa **no** controla su cerradura.
- Las retiradas se hacen por el procedimiento físico del fabricante, con dos personas cuando la política lo exija.
- No anuncies importes grandes en voz alta ni dejes el cambio a la vista.

### 10.2. De las credenciales

- La contraseña de la API se escribe en la URL de cada petición: viaja cifrada por HTTPS, pero queda en logs y capturas.
- No compartas la contraseña por chat ni la dejes escrita junto al PC.
- No publiques capturas de la consola que incluyan la URL completa con credenciales.
- Si sospechas que se ha filtrado, pide el cambio al técnico.

### 10.3. De la red

- El PC y el CashDro deben estar en una **red aislada**, sin salida a Internet.
- No conectes el CashDro a la red de invitados ni a la Wi-Fi de la tienda.
- No instales el programa en un PC compartido con navegación web y correo.

### 10.4. Del puesto

- Bloquea Windows al ausentarte.
- No ejecutes el programa como administrador si no es necesario.
- No modifiques `config.py` sin autorización.

---

## 11. Especificaciones técnicas

| Parámetro | Valor |
|---|---|
| **Aplicación** | CashDroController 1.0 |
| **Lenguaje** | Python 3.8+ (probado con 3.12) |
| **Plataforma** | Windows 10/11 (x64) |
| **Interfaz** | Consola de texto con colores ANSI |
| **Dependencia** | `requests>=2.25.0` |
| **Protocolo** | HTTPS/1.1, GET con query params |
| **Endpoint** | `/Cashdro3WS/index3.php` |
| **Formato** | JSON |
| **Autenticación** | `name` + `password` por petición |
| **TLS** | Certificado autofirmado, verificación deshabilitada |
| **Timeout HTTP** | 10 s (configurable) |
| **Reintentos de red** | 3 (configurable) |
| **Reintentos de ocupado** | 3 × 5 s (configurable) |
| **Sondeo** | Cada 2 s (configurable) |
| **Timeout de operación** | 120 s (configurable) |
| **Importe máximo** | 9.999,99 € |
| **Precisión monetaria** | Céntimos enteros |
| **Persistencia** | Ninguna (configuración en `config.py` + variables de entorno) |
| **Concurrencia** | Un CashDro por proceso |
| **Idioma** | Español |
| **Licencia** | MIT |

### 11.1. Compatibilidad del dispositivo

| Aspecto | Estado |
|---|---|
| API documentada `v22.01.21.11` | Base del desarrollo. |
| Estructura de respuesta plana | Soportada. |
| Estructura de respuesta anidada | Soportada (normalización). |
| Estados `I`, `Q`, `E`, `F` | Soportados. |
| Estados no documentados | Se tratan como error. |
| SSL autofirmado | Soportado (`verify=False`). |
| Otros tipos de operación | No implementados (sólo `type=4`). |

### 11.2. Mensajes de la API (referencia rápida)

| Operación | Para qué |
|---|---|
| `doTest` | Comprobar conexión y credenciales. |
| `startOperation` | Abrir venta. |
| `acknowledgeOperationId` | Confirmar y ejecutar. |
| `askOperation` | Consultar estado y totales. |
| `finishOperation` | Cerrar (1) o anular (2). |
| `setOperationImported` | Marcar como contabilizada. |
| `askLevels` | Niveles por denominación. |
| `askAlerts` | Alertas. |
| `askDiagnosis` | Diagnóstico. |

### 11.3. Dependencias del software

Las librerías requeridas están declaradas en [`requirements.txt`](../requirements.txt):

| Librería | Versión | Uso |
|---|---|---|
| `requests` | `>=2.25.0` | Cliente HTTP para la API del CashDro. |
| `urllib3` | incluida con `requests` | Conexiones TLS y supresión del aviso de certificado. |

Instalación dentro del entorno virtual del proyecto:

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

En Windows, desde la carpeta del proyecto:

```bat
py -3 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

No se requiere ninguna otra dependencia. `tkinter`, `sqlite3` y el resto de bibliotecas estándar no se usan en esta versión.

---

## 12. Preguntas frecuentes

**¿Puedo cobrar dos clientes a la vez?**
No. El CashDro atiende una operación cada vez. Un segundo intento recibe `-1900`.

**¿Qué pasa si cierro la ventana durante un cobro?**
La operación queda abierta en el equipo. Al volver a entrar, consúltala y anula si procede.

**¿El programa guarda las ventas?**
No. Sólo muestra el resultado. El registro debe hacerse en el sistema de caja.

**¿Puedo cambiar la IP sin reiniciar?**
Sí, con la opción 5. Pero no se guarda: al reiniciar vuelve a `config.py`.

**¿Por qué la contraseña se ve en la URL?**
Porque la API del fabricante la recibe así. HTTPS la cifra en tránsito, pero no evita que quede en registros. Por eso la red debe estar aislada.

**¿Funciona con varios CashDro?**
La clase interna admite varias instancias, pero la interfaz actual sólo maneja una conexión por ejecución.

**¿Qué hago si el importe es superior a 9.999,99 €?**
El límite es de la interfaz. Divide la operación o consulta al técnico; no está pensado para importes altos.

**¿Puedo usarlo en Linux o macOS?**
El código es Python estándar y debería funcionar, pero el objetivo y las pruebas son Windows. Los colores ANSI y las rutas de `venv` cambian.

**¿Necesito Internet?**
No. Sólo red local hacia el CashDro. De hecho, se recomienda que no haya Internet en ese tramo.

**¿Es seguro dejar el programa abierto toda la noche?**
Es preferible cerrarlo. Si se queda abierto, asegúrate de que no hay operaciones pendientes.

---

## 13. Glosario

| Término | Definición |
|---|---|
| **CashDro** | Dispositivo de gestión de efectivo con aceptación y reciclaje. |
| **CDM** | *Cash Deposit Module*: módulo de depósito de efectivo. |
| **Reciclador** | Equipo que reutiliza el efectivo ingresado para dar cambio. |
| **Cassette** | Depósito extraíble de billetes, normalmente por denominación. |
| **Tolva** | Depósito de monedas. |
| **Escrow** | Bolsa temporal donde se retiene un billete hasta confirmar la operación. |
| **CIS** | *Contact Image Sensor*: sensor óptico de línea. |
| **UV / IR** | Ultravioleta / infrarrojo: bandas usadas para validar seguridad. |
| **OperationId** | Identificador único de una transacción en el CashDro. |
| **Polling** | Consulta periódica del estado de una operación. |
| **Acknowledge** | Confirmación que pone la operación en ejecución. |
| **System busy** | Estado del equipo cuando ya está ocupado (`-1900`). |
| **TLS autofirmado** | Certificado generado por el propio equipo, sin CA pública. |
| **MITM** | *Man in the Middle*: interceptación de la comunicación. |
| **Céntimos** | Unidad entera usada por la API (1 € = 100). |
| **Alias ID** | Nombre lógico del terminal que abre la operación. |

---

*Documento para operadores. Para detalles de implementación, consulta `developer.md`. Para el contrato exacto de la API, el manual de integración del fabricante citado en `REFERENCES.md`.*
