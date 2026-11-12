"""
main.py — Punto de entrada de CashDroController.

Flujo principal:
  1. Mostrar banner
  2. Verificar conexión con CashDro (doTest)
  3. Menú principal con opciones: Cobro, Anular, Estado, Salir
"""

from __future__ import annotations

import os
import signal
import sys
import time
from typing import Optional

import requests
import urllib3

# Asegurar que el directorio del proyecto está en sys.path (Python embeddable)
_proj_dir = os.path.dirname(os.path.abspath(__file__))
if _proj_dir not in sys.path:
    sys.path.insert(0, _proj_dir)

from cashdro_api import CashDroAPI, CashDroError
from cashdro_cli import (
    _color,
    _safe_input,
    RED,
    GREEN,
    YELLOW,
    BLUE,
    CYAN,
    MAGENTA,
    DIM,
    BOLD,
    RESET,
    mostrar_banner,
    menu_principal,
    solicitar_conexion,
    solicitar_monto,
    mostrar_progreso,
    mostrar_paso_ok,
    mostrar_paso_error,
    mostrar_resultado,
    mostrar_estado_cashdro,
    mostrar_error,
    mostrar_info,
    confirmar_cancelacion,
)

# ─── Gestión de interrupción (Ctrl+C) ──────────────────────────────

_cancel_requested: bool = False


def _signal_handler(sig: int, frame) -> None:
    """Manejador de señal SIGINT para permitir Ctrl+C limpio.

    Primer Ctrl+C: establece flag de cancelación para operaciones en curso.
    Segundo Ctrl+C: sale del programa inmediatamente.
    """
    global _cancel_requested
    if not _cancel_requested:
        print()
        mostrar_info("Presione Ctrl+C nuevamente para salir, o espere a que la operación se cancele.")
        _cancel_requested = True
    else:
        # Segundo Ctrl+C → salir inmediatamente
        print()
        mostrar_info("Saliendo del programa...")
        sys.exit(0)


def _check_cancel() -> bool:
    """Retorna True si el usuario solicitó cancelación."""
    return _cancel_requested


def _reset_cancel() -> None:
    """Reinicia el flag de cancelación."""
    global _cancel_requested
    _cancel_requested = False


# ─── Operaciones del menú ──────────────────────────────────────────

def operacion_cobro(api: CashDroAPI) -> None:
    """
    Flujo completo de cobro (venta).

    Pasos:
      1. Solicitar monto
      2. startOperation → obtener operationId
      3. acknowledgeOperationId
      4. Polling hasta state='F'
      5. Mostrar resultado
      6. setOperationImported
    """
    global _cancel_requested
    _reset_cancel()
    operation_id: str = ""  # Inicializada antes del try (I-001)

    # ── Paso 0: Solicitar monto ──
    monto = solicitar_monto()
    if monto is None:
        return

    print()
    mostrar_progreso("Iniciando transaccion de cobro...", f"{monto:.2f}")
    mostrar_info(f"Monto en céntimos: {int(round(monto * 100))}")
    print()

    try:
        # ── Paso 1: startOperation ──
        mostrar_progreso("Paso 1/5", "Enviando startOperation...")
        operation_id = api.start_operation(op_type=4, amount=monto)
        mostrar_paso_ok(f"Operación iniciada — ID: {operation_id}")
        print()

        # ── Paso 2: acknowledgeOperationId ──
        mostrar_progreso("Paso 2/5", "Confirmando operación (acknowledge)...")
        api.acknowledge_operation(operation_id)
        mostrar_paso_ok("Operación confirmada")
        print()

        # ── Paso 3: Polling ──
        mostrar_progreso("Paso 3/5", "Esperando que el usuario introduzca el efectivo...")
        mostrar_info("Polling cada 2 segundos (timeout: 120s). Ctrl+C para cancelar.")
        print()

        state_data = api.wait_for_completion(
            operation_id,
            cancel_event=_check_cancel,
        )
        mostrar_paso_ok("Operación finalizada por el CashDro")
        print()

        # ── Paso 4: Mostrar resultado ──
        mostrar_progreso("Paso 4/5", "Mostrando resultado...")
        mostrar_resultado(state_data)
        print()

        # ── Paso 5: setOperationImported ──
        mostrar_progreso("Paso 5/5", "Marcando operación como importada...")
        api.set_operation_imported(operation_id)
        mostrar_paso_ok("Operación marcada como importada correctamente")

        print()
        mostrar_paso_ok("✅  Cobro completado exitosamente")

    except KeyboardInterrupt:
        print()
        mostrar_info("Cancelación solicitada por el usuario.")
        if operation_id:
            _finalizar_o_cancelar(api, operation_id)
    except CashDroError as e:
        mostrar_error(e)
        # Si la operación ya se inició pero falló, intentar cancelar
        if operation_id:
            try:
                api.finish_operation(operation_id, end_type=2)
                mostrar_info("Transacción cancelada por error.")
            except Exception:
                pass
    except requests.exceptions.RequestException as e:
        mostrar_error(e)
        if operation_id:
            try:
                api.finish_operation(operation_id, end_type=2)
                mostrar_info("Transacción cancelada por error de conexión.")
            except Exception:
                pass
    except TimeoutError as e:
        mostrar_error(e)
        if operation_id:
            try:
                api.finish_operation(operation_id, end_type=2)
                mostrar_info("Transacción cancelada por timeout.")
            except Exception:
                pass


def _finalizar_o_cancelar(api: CashDroAPI, operation_id: str) -> None:
    """
    Intenta cancelar una operación en curso, con confirmación del usuario.

    Args:
        api: Instancia de CashDroAPI.
        operation_id: ID de la operación a cancelar.
    """
    print()
    if confirmar_cancelacion():
        mostrar_progreso("Cancelando operación...")
        try:
            api.finish_operation(operation_id, end_type=2)
            mostrar_paso_ok("Operación cancelada exitosamente")
        except Exception as e:
            mostrar_error(e)
    else:
        mostrar_info("Cancelación abortada por el usuario.")


def operacion_anular(api: CashDroAPI) -> None:
    """
    Anula una transacción en curso.

    Consulta el estado actual y permite finalizarla con type=2.
    """
    _reset_cancel()
    print()
    mostrar_info("Para anular una transacción, primero se consultará el estado actual.")
    print()

    try:
        # No tenemos un operationId fijo; pedimos al usuario que ingrese el ID
        print(f"  {_color('Ingrese el ID de la operación a anular:', BOLD)}")
        print(f"  {_color('(Si no conoce el ID, consulte el estado en la opción 3 del menú)', DIM)}")
        op_id = _safe_input(f"  {_color('➤', YELLOW)} Operation ID: ")

        if not op_id:
            mostrar_error(ValueError("No se ingresó un ID de operación"))
            return

        # Verificar estado actual
        mostrar_progreso("Consultando estado de la operación...")
        estado = api.ask_operation(op_id)
        state = estado.get("state", "unknown")
        mostrar_info(f"Estado actual: {state}")

        if state == "F":
            mostrar_info("La operación ya está finalizada. No es necesario anularla.")
            return

        if confirmar_cancelacion():
            mostrar_progreso("Anulando transacción...")
            api.finish_operation(op_id, end_type=2)
            mostrar_paso_ok("Transacción anulada correctamente")
        else:
            mostrar_info("Anulación cancelada por el usuario.")

    except CashDroError as e:
        mostrar_error(e, e.code)
    except requests.exceptions.RequestException as e:
        mostrar_error(e)


def operacion_estado(api: CashDroAPI) -> None:
    """
    Consulta y muestra el estado completo del CashDro:
    niveles de efectivo, alertas y diagnóstico.
    """
    _reset_cancel()
    print()
    mostrar_progreso("Consultando estado del CashDro...")
    print()

    levels: dict = {}
    alerts: list = []
    diagnosis: dict = {}

    try:
        mostrar_progreso("Obteniendo niveles de efectivo...")
        levels = api.ask_levels()
        mostrar_paso_ok("Niveles obtenidos")

        mostrar_progreso("Obteniendo alertas activas...")
        alerts = api.ask_alerts()
        mostrar_paso_ok("Alertas obtenidas")

        mostrar_progreso("Obteniendo diagnóstico...")
        diagnosis = api.ask_diagnosis()
        mostrar_paso_ok("Diagnóstico obtenido")

        print()
        mostrar_estado_cashdro(levels, alerts, diagnosis)

    except CashDroError as e:
        mostrar_error(e, e.code)
    except requests.exceptions.RequestException as e:
        mostrar_error(e)


# ─── Verificación inicial ──────────────────────────────────────────

def verificar_conexion(api: CashDroAPI) -> bool:
    """
    Verifica la conexión con el CashDro mediante doTest.

    Args:
        api: Instancia de CashDroAPI.

    Returns:
        True si la conexión es exitosa, False en caso contrario.
    """
    mostrar_progreso("Verificando conexión con CashDro...")
    print(f"  {_color(f'Host: {api.base_url}', DIM)}")
    print(f"  {_color('SSL Verification: Deshabilitada (certificado autofirmado)', DIM)}")
    print()

    try:
        result = api.test_connection()
        response = result.get("response", {})
        error_msg = response.get("errorMessage", "none")
        if error_msg.lower() == "none":
            mostrar_paso_ok("Conexion establecida correctamente")
            return True
        else:
            mostrar_paso_error(f"Error en conexión: {error_msg}")
            return False
    except CashDroError as e:
        mostrar_error(e, e.code)
        return False
    except requests.exceptions.RequestException as e:
        mostrar_error(e)
        return False


# ─── Programa principal ────────────────────────────────────────────

def crear_api(host: str = "", user: str = "", password: str = "") -> CashDroAPI:
    """Crea una instancia de CashDroAPI con los parámetros dados (o los de config)."""
    from config import CASHDRO_HOST, CASHDRO_USER, CASHDRO_PASSWORD
    return CashDroAPI(
        host=host or CASHDRO_HOST,
        user=user or CASHDRO_USER,
        password=password or CASHDRO_PASSWORD,
    )


def configurar_conexion() -> tuple[str, str, str]:
    """Pide los datos de conexión y retorna (host, user, password)."""
    from config import CASHDRO_HOST, CASHDRO_USER, CASHDRO_PASSWORD
    return solicitar_conexion(CASHDRO_HOST, CASHDRO_USER, CASHDRO_PASSWORD)


def main() -> None:
    """Punto de entrada principal del programa."""
    # Configurar manejador de señal para Ctrl+C
    signal.signal(signal.SIGINT, _signal_handler)

    # Deshabilitar warnings de SSL (certificado autofirmado)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Mostrar banner
    mostrar_banner()
    print(f"  {_color('CashDroController v1.0', DIM)}")
    print(f"  {_color('Sistema de control de efectivo automatizado', DIM)}")
    print()

    # Configurar conexión al inicio
    host_usuario, user_usuario, pass_usuario = configurar_conexion()
    api = crear_api(host_usuario, user_usuario, pass_usuario)

    # Verificar conexión
    if not verificar_conexion(api):
        print()
        mostrar_info("No se pudo establecer conexion con el CashDro.")
        mostrar_info("Verifique que el dispositivo este encendido y accesible en la red.")
        print()
        respuesta = _safe_input(f"  {_color('>>', YELLOW)} Desea continuar de todas formas? (s/N): ")
        if respuesta.lower() != "s":
            print()
            mostrar_info("Saliendo del programa...")
            sys.exit(0)

    # Bucle principal del menú
    while True:
        try:
            _reset_cancel()
            opcion = menu_principal()

            if opcion == "1":
                operacion_cobro(api)
            elif opcion == "2":
                operacion_anular(api)
            elif opcion == "3":
                operacion_estado(api)
            elif opcion == "5":
                host_usuario, user_usuario, pass_usuario = configurar_conexion()
                api = crear_api(host_usuario, user_usuario, pass_usuario)
                verificar_conexion(api)
            elif opcion == "4":
                print()
                mostrar_info("Saliendo del programa...")
                print(f"\n{_color('Hasta luego!', CYAN, True)}")
                sys.exit(0)

            # Pausa antes de volver al menú
            print()
            _safe_input(f"  {_color('Presione Enter para continuar...', DIM)}")

        except KeyboardInterrupt:
            print()
            mostrar_info("Ctrl+C recibido. Saliendo del programa...")
            sys.exit(0)
        except Exception as e:
            mostrar_error(e)
            print()
            _safe_input(f"  {_color('Presione Enter para continuar...', DIM)}")


if __name__ == "__main__":
    main()
