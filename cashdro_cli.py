"""
cashdro_cli.py — Interfaz de consola para CashDroController.

Proporciona funciones para mostrar menús, solicitar datos al usuario
y presentar resultados con formato y colores.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

# Asegurar que el directorio del proyecto está en sys.path (Python embeddable)
_proj_dir = os.path.dirname(os.path.abspath(__file__))
if _proj_dir not in sys.path:
    sys.path.insert(0, _proj_dir)

# ─── Códigos de color ANSI ──────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"


# ─── Funciones de utilidad ──────────────────────────────────────────

def _color(text: str, color_code: str, bold: bool = False) -> str:
    """Aplica color ANSI a un texto."""
    prefix = BOLD if bold else ""
    return f"{prefix}{color_code}{text}{RESET}"


def _safe_input(prompt: str = "") -> str:
    """
    Lee una línea de stdin manejando EOFError y KeyboardInterrupt.
    """
    try:
        return input(prompt).strip()
    except EOFError:
        print()
        return ""
    except KeyboardInterrupt:
        print()
        return ""


# ─── Funciones de la interfaz ───────────────────────────────────────

def mostrar_banner() -> None:
    """Muestra el banner / título de la aplicación."""
    banner = f"""
{_color("+" + "=" * 50 + "+", CYAN, True)}
{_color("|", CYAN, True)}          {_color("CASH DRO CONTROLLER", WHITE, True)}          {_color("|", CYAN, True)}
{_color("|", CYAN, True)}      {_color("Control de efectivo automatizado", CYAN)}      {_color("|", CYAN, True)}
{_color("+" + "=" * 50 + "+", CYAN, True)}
"""
    print(banner)


def menu_principal() -> str:
    """
    Muestra el menú principal y retorna la opción seleccionada.

    Returns:
        Opción como string ('1'..'5').
    """
    print(f"\n{_color('=== MENU PRINCIPAL ===', BOLD)}")
    print(f"  {_color('1.', GREEN)} {_color('Cobro', BOLD)} - Realizar un cobro")
    print(f"  {_color('2.', YELLOW)} {_color('Anular transaccion', BOLD)} - Cancelar operacion en curso")
    print(f"  {_color('3.', BLUE)} {_color('Consultar estado', BOLD)} - Ver niveles, alertas y diagnostico")
    print(f"  {_color('5.', MAGENTA)} {_color('Configurar conexion', BOLD)} - Cambiar IP/usuario/contraseña")
    print(f"  {_color('4.', RED)} {_color('Salir', BOLD)} - Terminar el programa")
    print(f"{_color('-' * 54, DIM)}")

    while True:
        opcion = _safe_input(f"{_color('>>', CYAN)} Seleccione una opcion [1-5]: ")
        if opcion in ("1", "2", "3", "4", "5"):
            return opcion
        print(f"  {_color('X Opcion invalida. Intente de nuevo.', RED)}")


def solicitar_conexion(host_actual: str = "", user_actual: str = "", pass_actual: str = "") -> tuple[str, str, str]:
    """
    Solicita al usuario la IP, usuario y contraseña del CashDro.

    Args:
        host_actual: IP actual (se muestra como default).
        user_actual: Usuario actual (se muestra como default).
        pass_actual: Contraseña actual (se muestra como default).

    Returns:
        Tupla (host, user, password).
    """
    print(f"\n{_color('=== CONFIGURACION DE CONEXION ===', BOLD)}")
    print(f"  {_color('(Presione Enter para mantener el valor actual)', DIM)}")
    print()

    default_host = host_actual or os.getenv("CASHDRO_HOST", "192.0.2.90")
    default_user = user_actual or os.getenv("CASHDRO_USER", "USUARIO_CASHDRO")
    default_pass = pass_actual or os.getenv("CASHDRO_PASSWORD", "CLAVE_CASHDRO")

    entrada = _safe_input(f"  {_color('>>', CYAN)} IP del CashDro [{default_host}]: ")
    host = entrada.strip() or default_host

    entrada = _safe_input(f"  {_color('>>', CYAN)} Usuario [{default_user}]: ")
    user = entrada.strip() or default_user

    entrada = _safe_input(f"  {_color('>>', CYAN)} Contrasena [{default_pass}]: ")
    password = entrada.strip() or default_pass

    print()
    return host, user, password


def solicitar_monto() -> Optional[float]:
    """
    Solicita un importe al usuario, lo valida y retorna como float.

    Returns:
        Monto como float (positivo, <= 9999.99), o None si el usuario cancela.

    La función maneja Ctrl+C y la palabra 'cancelar' para interrumpir.
    """
    print(f"\n{_color('=== COBRO - Ingrese el importe ===', BOLD)}")
    print(f"  {_color('(Escriba \"cancelar\" o presione Ctrl+C para salir)', DIM)}")
    print(f"  {_color('Monto maximo: 9,999.99', DIM)}")

    while True:
        entrada = _safe_input(f"\n{_color('>>', GREEN)} Importe a cobrar: ")

        if entrada.lower() in ("cancelar", "salir", "q", "quit", "exit"):
            print(f"  {_color('Operacion cancelada por el usuario.', YELLOW)}")
            return None

        # Reemplazar coma por punto (formato español)
        entrada = entrada.replace(",", ".")

        try:
            monto = float(entrada)
        except (ValueError, TypeError):
            print(f"  {_color('X Importe invalido. Debe ser un numero (ej: 18.25 o 18,25).', RED)}")
            continue

        if monto <= 0:
            print(f"  {_color('X El importe debe ser mayor que cero.', RED)}")
            continue

        if monto > 9999.99:
            print(f"  {_color('X El importe maximo es 9,999.99.', RED)}")
            continue

        return monto


def mostrar_progreso(mensaje: str, detalle: str = "") -> None:
    """
    Muestra un mensaje de progreso con formato.

    Args:
        mensaje: Texto principal del paso.
        detalle: Información adicional (opcional).
    """
    linea = f"  {_color('*', CYAN)} {mensaje}"
    if detalle:
        linea += f" {_color(f'({detalle})', DIM)}"
    print(linea)


def mostrar_paso_ok(mensaje: str) -> None:
    """Muestra un paso completado con éxito."""
    print(f"  {_color('OK', GREEN)} {_color(mensaje, GREEN)}")


def mostrar_paso_error(mensaje: str) -> None:
    """Muestra un paso fallido."""
    print(f"  {_color('FAIL', RED)} {_color(mensaje, RED)}")


def mostrar_resultado(data: dict) -> None:
    """
    Muestra el resultado detallado de una transacción.

    Args:
        data: Diccionario con los datos de la operación finalizada.
    """
    print(f"\n{_color('=' * 50, GREEN, True)}")
    print(f"{_color('         TRANSACCION COMPLETADA', GREEN, True)}")
    print(f"{_color('=' * 50, GREEN, True)}")
    print(f"  {_color('Estado:', BOLD)} {_color('Finalizada (F)', GREEN)}")

    # Montos vienen en céntimos, convertir a euros
    total_in = _cents_to_euro(data.get("totalin", "0"))
    total_out = _cents_to_euro(data.get("totalout", "0"))
    cambio = _cents_to_euro(data.get("change", "0"))

    print(f"  {_color('Total ingresado:', BOLD)} {total_in}")
    print(f"  {_color('Total devuelto:', BOLD)} {total_out}")
    if float(cambio) > 0:
        print(f"  {_color('Cambio:', YELLOW)} {cambio}")
    print(f"{_color('-' * 46, DIM)}")

    # Mostrar todos los campos adicionales si existen
    campos_interes = ["operationId", "date", "type", "posid", "aliasid"]
    for campo in campos_interes:
        valor = data.get(campo)
        if valor is not None and str(valor).strip():
            print(f"  {campo}: {valor}")

    print(f"{_color('=' * 50, GREEN, True)}")


def mostrar_estado_cashdro(
    levels: dict,
    alerts: list,
    diagnosis: dict,
) -> None:
    """
    Muestra el estado completo del CashDro.

    Args:
        levels: Diccionario con niveles de efectivo.
        alerts: Lista de alertas activas.
        diagnosis: Diccionario con diagnóstico.
    """
    print(f"\n{_color('=' * 50, BLUE, True)}")
    print(f"{_color('        ESTADO DEL CASH DRO', BLUE, True)}")
    print(f"{_color('=' * 50, BLUE, True)}")

    # ── Niveles de efectivo ──
    print(f"\n{_color('Niveles de efectivo:', BOLD)}")
    if levels:
        for key, value in levels.items():
            print(f"  {_color(f'{key}:', DIM)} {_color(str(value), BOLD)}")
    else:
        print(f"  {_color('(sin datos)', DIM)}")

    # ── Alertas ──
    print(f"\n{_color('Alertas activas:', BOLD)}")
    if alerts:
        for alerta in alerts:
            if isinstance(alerta, dict):
                desc = alerta.get("description", alerta.get("alert", str(alerta)))
                cod = alerta.get("code", "")
                if cod:
                    print(f"  {_color(f'! [{cod}]', YELLOW)} {desc}")
                else:
                    print(f"  {_color(f'! {desc}', YELLOW)}")
            else:
                print(f"  {_color(f'! {alerta}', YELLOW)}")
    else:
        print(f"  {_color('OK Sin alertas activas', GREEN)}")

    # ── Diagnóstico ──
    print(f"\n{_color('Diagnostico:', BOLD)}")
    if diagnosis:
        for key, value in diagnosis.items():
            color = GREEN if str(value).lower() in ("ok", "true", "1", "yes") else WHITE
            print(f"  {_color(f'{key}:', DIM)} {_color(str(value), color)}")
    else:
        print(f"  {_color('(sin datos)', DIM)}")

    print(f"{_color('-' * 46, DIM)}")


def mostrar_error(error: Exception, codigo: Optional[int] = None) -> None:
    """
    Muestra un mensaje de error formateado.

    Si el error es un CashDroError, se extrae el mensaje limpio para
    evitar duplicar el código de error en la salida.

    Args:
        error: Excepción o mensaje de error.
        codigo: Código de error numérico (opcional). Si no se pasa,
                se intenta extraer de CashDroError.code.
    """
    # Si es CashDroError, extraer mensaje limpio para evitar duplicación
    from cashdro_api import CashDroError
    if isinstance(error, CashDroError):
        codigo_real = error.code if codigo is None else codigo
        mensaje_limpio = error.message
        print(f"\n{_color(f'ERROR [{codigo_real}]:', RED, True)} {mensaje_limpio}")
    elif codigo is not None:
        texto = str(error)
        print(f"\n{_color(f'ERROR [{codigo}]:', RED, True)} {texto}")
    else:
        print(f"\n{_color(f'ERROR:', RED, True)} {str(error)}")
    print(f"  {_color('Consulte el manual de integracion para mas detalles.', DIM)}")


def mostrar_info(mensaje: str) -> None:
    """Muestra un mensaje informativo."""
    print(f"  {_color('i', BLUE)} {mensaje}")


def confirmar_cancelacion() -> bool:
    """
    Pide confirmación al usuario para cancelar la operación en curso.

    Returns:
        True si el usuario confirma la cancelación, False en caso contrario.
    """
    print(f"\n{_color('ATENCION: Esta seguro de que desea cancelar la operacion en curso?', YELLOW, True)}")
    respuesta = _safe_input(f"  {_color('>>', YELLOW)} Escriba 'SI' para confirmar: ")
    return respuesta.upper() == "SI"


# ─── Funciones auxiliares ───────────────────────────────────────────

def _cents_to_euro(valor: str) -> str:
    """Convierte un valor en céntimos (string) a formato euro."""
    try:
        centimos = int(valor)
        euros = centimos / 100.0
        return f"{euros:.2f}"
    except (ValueError, TypeError):
        return valor
