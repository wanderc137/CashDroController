# Referencias — CashDroController

Fuentes consultadas y lecturas recomendadas, con una nota sobre **qué se usó de cada una** y **qué no debe darse por verificado**.

---

## 1. Fuente primaria del proyecto

### 1.1. Manual de integración CashDro v22.01.21.11

Es el contrato que define todo lo que hace este programa:

- Endpoint `Cashdro3WS/index3.php`.
- Autenticación por `name` y `password` en la query string.
- Operaciones: `doTest`, `startOperation`, `acknowledgeOperationId`, `askOperation`, `finishOperation`, `setOperationImported`, `askLevels`, `askAlerts`, `askDiagnosis`.
- Formato de parámetros (`type`, `parameters` como JSON, `posid`, `posuser`, `aliasid`).
- Códigos de error (`-1`, `-2`, `-3`, `-4`, `-99`, `-1900`, `-998`, `-999`).
- Montos en céntimos.

**Cómo obtenerlo:** se distribuye con el equipo o lo proporciona el integrador/distribuidor del CashDro. No se reproduce aquí por ser documentación del fabricante.

**Advertencia:** el manual describe la API, no el firmware exacto de cada unidad. Las diferencias de anidación en las respuestas (`operation.operation`) son un ejemplo de variación observada en la práctica; el código las tolera, pero la forma exacta debe confirmarse contra el equipo concreto.

### 1.2. Documentación del dispositivo

Para el principio físico (sensores, validación, reciclaje) se usaron las descripciones genéricas de la familia de productos y literatura de manejo de efectivo. Los detalles concretos de sensores y capacidades **varían por modelo** y no se afirman aquí como especificación de un equipo concreto.

---

## 2. Python y biblioteca estándar

| Recurso | Uso en el proyecto |
|---|---|
| [Python 3 — documentación oficial](https://docs.python.org/3/) | Lenguaje, tipado, `sys.path`, `signal`, `time.monotonic`. |
| [`sys`](https://docs.python.org/3/library/sys.html) | Inserción del directorio del proyecto en `sys.path` (Python embeddable). |
| [`signal`](https://docs.python.org/3/library/signal.html) | Manejo de `SIGINT` para la cancelación en dos pasos. |
| [`time`](https://docs.python.org/3/library/time.html) | `sleep` en reintentos y `monotonic` para el timeout de sondeo. |
| [`json`](https://docs.python.org/3/library/json.html) | Serialización del parámetro `parameters`. |
| [`typing`](https://docs.python.org/3/library/typing.html) | Anotaciones (`Optional`, `Any`, `Callable`). |
| [PEP 563 — Postponed Evaluation of Annotations](https://peps.python.org/pep-0563/) | Razón de `from __future__ import annotations` y compatibilidad con 3.8. |
| [PEP 8 — Style Guide](https://peps.python.org/pep-0008/) | Convenciones de estilo. |

### `sys.path` y el Python embeddable

El Python "embeddable" de Windows no añade el directorio del script a `sys.path` como hace el intérprete normal. Por eso los módulos hacen:

```python
_proj_dir = os.path.dirname(os.path.abspath(__file__))
if _proj_dir not in sys.path:
    sys.path.insert(0, _proj_dir)
```

Referencia: [Python on Windows — embeddable package](https://docs.python.org/3/using/windows.html#embedded-distribution).

---

## 3. `requests` y `urllib3`

| Recurso | Uso |
|---|---|
| [Requests — documentación](https://requests.readthedocs.io/) | Cliente HTTP, `params`, `timeout`, `verify`. |
| [Requests — Advanced usage: SSL certificate verification](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification) | Fundamento de `verify=False`. |
| [Requests — Timeouts](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts) | Diferencia entre timeout de conexión y de lectura. |
| [urllib3 — documentación](https://urllib3.readthedocs.io/) | `disable_warnings(InsecureRequestWarning)`. |
| [urllib3 — Advanced usage: certificates](https://urllib3.readthedocs.io/en/stable/advanced-usage.html#ssl-warnings) | Por qué aparece el warning al desactivar la verificación. |

### Versión

`requirements.txt` fija `requests>=2.25.0`. No se fija una versión exacta para no bloquear parches de seguridad; en un despliegue controlado conviene fijar una versión probada (`requests==2.x.y`) y generar un `requirements.lock`.

### `requests.get` vs `requests.Session`

El proyecto usa `requests.get` por llamada. Una `Session` reutilizaría la conexión TCP/TLS y ahorraría el handshake en cada sondeo (cada 2 s). No se implementó por simplicidad; es una optimización razonable si el volumen crece. Contra: una sesión persistente puede quedar en mal estado tras un fallo de red y hay que recrearla.

---

## 4. HTTP y TLS

| Recurso | Relevancia |
|---|---|
| [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110.html) | Métodos, semántica de GET, códigos de estado. |
| [RFC 9112 — HTTP/1.1](https://www.rfc-editor.org/rfc/rfc9112.html) | Formato de la petición y query string. |
| [RFC 8446 — TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446.html) | Cifrado en tránsito. |
| [RFC 5280 — X.509](https://www.rfc-editor.org/rfc/rfc5280.html) | Certificados y cadenas de confianza. |
| [OWASP — Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html) | Por qué `verify=False` es una excepción y no una norma. |
| [OWASP — Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html) | Manejo de credenciales fuera del código. |

### Sobre el certificado autofirmado

Un certificado autofirmado cifra la conexión pero no prueba la identidad del servidor. Las opciones reales son:

1. **Aceptar el riesgo** en una red aislada (lo que hace este proyecto).
2. **Instalar el certificado del equipo como CA de confianza** en el PC. Requiere extraerlo y distribuirlo; a partir de ahí se puede usar `verify=True` con la ruta al PEM.
3. **Pinning**: comparar el certificado esperado (huella SHA-256) con el presentado. `requests` no lo trae de fábrica; se implementa con un adaptador TLS o verificación posterior.

Ninguna está implementada. La 1 es la actual; la 2 es la más limpia si se puede tocar el PC; la 3 es la más robusta frente a MITM.

---

## 5. Manejo de efectivo y validación

Lecturas de contexto para entender qué hay al otro lado del cable. **No son documentación del modelo concreto** y no deben citarse como especificación.

| Tema | Referencia |
|---|---|
| Características de seguridad del euro | [Banco Central Europeo — seguridad del euro](https://www.ecb.europa.eu/euro/banknotes/security/html/index.es.html) |
| Billetes y monedas en circulación | [Banco de España — billetes y monedas](https://www.bde.es/bde/es/areas/billetes-monedas/) |
| Códigos de divisa | [ISO 4217](https://www.iso.org/iso-4217-currency-codes.html) |
| Validación de monedas por corrientes inducidas | Literatura de sensores electromagnéticos y validadores de moneda (principio de *eddy current*). |
| Transporte y doble detección | Literatura de manipuladores de billetes (*banknote handling*), sensores ultrasónicos y de espesor. |

### Qué se puede afirmar con seguridad

- Un billete se valida con **varias señales correlacionadas**, no con una sola.
- Los sensores UV e IR detectan propiedades del papel y las tintas que no reproduce una impresora doméstica.
- Un reciclador **reutiliza** el efectivo ingresado; un aceptador **no**.
- La capacidad y las denominaciones dependen del modelo y de la configuración.

### Qué no se puede afirmar sin el equipo

- Número exacto de sensores y sus longitudes de onda.
- Capacidad de cada cassette.
- Velocidad de procesamiento.
- Denominaciones aceptadas por defecto.
- Comportamiento exacto ante un billete dudoso.

El README y el datasheet evitan estos datos; si se añaden en el futuro, deben proceder de la ficha del modelo concreto.

---

## 6. Herramientas de verificación

| Herramienta | Uso |
|---|---|
| `python -m py_compile` | Comprobación de sintaxis. |
| `python -c "import ..."` | Comprobación de imports y `sys.path`. |
| `curl -k` | Prueba manual de la API sin la aplicación. |
| `ping`, `ipconfig` | Diagnóstico de red en Windows. |
| `unittest.mock` | Simulación de respuestas HTTP sin hardware. |
| [Wireshark](https://www.wireshark.org/) | Análisis de tráfico (¡contiene credenciales en claro dentro de TLS!). |
| [OpenSSL](https://www.openssl.org/) | Inspección del certificado del equipo (`s_client`). |

### Extraer el certificado del CashDro

```bash
openssl s_client -connect 192.0.2.10:443 -showcerts </dev/null 2>/dev/null \
  | openssl x509 -outform PEM > cashdro.pem
openssl x509 -in cashdro.pem -noout -subject -issuer -fingerprint -sha256
```

Sirve para decidir entre CA interna y pinning. No se ha ejecutado contra el equipo real.

---

## 7. Referencias descartadas o no utilizadas

| Recurso | Por qué no se usó |
|---|---|
| SDK del fabricante | No disponible; la API REST es suficiente. |
| `colorama` | Windows 10+ soporta ANSI; se evita una dependencia. |
| `python-dotenv` | La configuración es un módulo Python; añadir `.env` no aportaba. |
| `click` / `argparse` | La interfaz es un menú interactivo, no una CLI de comandos. |
| `requests.Session` | Optimización pendiente, no necesaria para el volumen actual. |
| Frameworks web | El controlador no expone servicios. |
| Bibliotecas de logging estructurado | El proyecto no registra en archivo; pendiente de diseño. |

---

## 8. Cómo citar este proyecto

```bibtex
@software{cashdrocontroller2026,
  title  = {CashDroController: control de un reciclador de efectivo CashDro
            mediante su API REST},
  author = {wanderc137},
  year   = {2026},
  note   = {Aplicación de consola en Python para Windows},
  url    = {https://github.com/wanderc137/CashDroController}
}
```

Si se cita el comportamiento del dispositivo, cita también el **manual de integración v22.01.21.11** y el modelo exacto del equipo; este repositorio no los sustituye.

---

## 9. Estado de las fuentes

| Fuente | Estado |
|---|---|
| Manual de integración v22.01.21.11 | Citado; no incluido en el repositorio. |
| Documentación de Python/requests/urllib3 | Pública y verificable. |
| RFCs y OWASP | Públicos y estables. |
| Fichas de producto del CashDro | No consultadas directamente para este repositorio. |
| Pruebas contra hardware | **No realizadas.** |

Si vas a desplegar esto, la fuente que falta es la única que importa: **el equipo real y su manual para tu número de serie**.
