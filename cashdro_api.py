"""
cashdro_api.py — Cliente API REST para dispositivo CashDro.

Proporciona la clase CashDroAPI que encapsula todas las operaciones
definidas en el manual de integración CashDro v22.01.21.11.
"""

from __future__ import annotations

import os
import sys

# Asegurar que el directorio del proyecto está en sys.path (Python embeddable)
_proj_dir = os.path.dirname(os.path.abspath(__file__))
if _proj_dir not in sys.path:
    sys.path.insert(0, _proj_dir)

from collections.abc import Callable
import json
import time
from typing import Any, Optional

import requests

from config import (
    CASHDRO_HOST,
    CASHDRO_PASSWORD,
    CASHDRO_USER,
    API_BASE_PATH,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    MAX_RETRIES_SYSTEM_BUSY,
    RETRY_DELAY_SYSTEM_BUSY,
    POLL_INTERVAL,
    POLL_TIMEOUT,
    ERROR_CODES,
    POS_ID,
    POS_USER,
    ALIAS_ID,
)


class CashDroError(Exception):
    """Excepción lanzada cuando el CashDro responde con un código de error."""

    def __init__(self, code: int, message: str = "") -> None:
        self.code = code
        self.message = message or ERROR_CODES.get(code, f"Error desconocido ({code})")
        super().__init__(f"[{code}] {self.message}")


class CashDroAPI:
    """
    Cliente para la API REST del CashDro.

    Todas las llamadas se realizan vía GET con parámetros en la URL,
    con verificación SSL deshabilitada (certificado autofirmado).

    NOTA DE SEGURIDAD: Las credenciales (usuario y contraseña) se envían
    como parámetros GET en la URL, visibles en texto plano. Esto es un
    requisito del diseño de la API CashDro. NO habilitar logging de
    depuración de requests en producción para evitar exponer credenciales.
    """

    def __init__(
        self,
        host: str = CASHDRO_HOST,
        user: str = CASHDRO_USER,
        password: str = CASHDRO_PASSWORD,
        timeout: int = REQUEST_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        """
        Inicializa el cliente API.

        Args:
            host: Dirección IP del CashDro.
            user: Usuario de autenticación.
            password: Contraseña de autenticación.
            timeout: Timeout en segundos por llamada HTTP.
            max_retries: Número máximo de reintentos ante fallo de conexión.
        """
        self.base_url = f"https://{host}{API_BASE_PATH}"
        self.user = user
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries

    # ────────────────────────────────────────────────────────────────
    #   Método interno de llamada HTTP
    # ────────────────────────────────────────────────────────────────

    def _call(self, operation: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Ejecuta una llamada HTTP GET al CashDro.

        Args:
            operation: Nombre de la operación (doTest, startOperation, ...).
            params: Diccionario adicional de parámetros query.

        Returns:
            Diccionario con la respuesta JSON del servidor.

        Raises:
            CashDroError: Si el código de respuesta no es 1.
            requests.exceptions.RequestException: Si falla la conexión.
        """
        query_params: dict[str, Any] = {
            "operation": operation,
            "name": self.user,
            "password": self.password,
        }
        if params:
            # Los valores que sean dict o list se serializan a JSON
            for key, value in params.items():
                if isinstance(value, (dict, list)):
                    query_params[key] = json.dumps(value)
                else:
                    query_params[key] = value

        last_exception: Optional[Exception] = None
        last_cashdro_error: Optional[CashDroError] = None
        system_busy_retries_left = MAX_RETRIES_SYSTEM_BUSY

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    self.base_url,
                    params=query_params,
                    timeout=self.timeout,
                    verify=False,  # SSL autofirmado → deshabilitamos verificación
                )
                response.raise_for_status()
                data: dict[str, Any] = response.json()

                # Verificar código de respuesta
                code = data.get("code", -99)
                if code != 1:
                    error_msg = ""
                    if "response" in data and isinstance(data["response"], dict):
                        error_msg = data["response"].get("errorMessage", "")
                    # Código -1900: System busy → reintentar automáticamente
                    if code == -1900 and system_busy_retries_left > 0:
                        system_busy_retries_left -= 1
                        time.sleep(RETRY_DELAY_SYSTEM_BUSY)
                        continue
                    raise CashDroError(code, error_msg)

                return data

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries:
                    time.sleep(1)
                continue
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries:
                    time.sleep(1)
                continue
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < self.max_retries:
                    time.sleep(1)
                continue

        # Si llegamos aquí es porque se agotaron los reintentos
        if system_busy_retries_left <= 0 and last_exception is None:
            # Todos los reintentos dieron -1900 (System busy persistente)
            raise CashDroError(-1900, "System busy - el CashDro esta ocupado despues de multiples intentos")
        raise requests.exceptions.RequestException(
            f"Error de conexión tras {self.max_retries} intentos: {last_exception}"
        ) from last_exception

    # ────────────────────────────────────────────────────────────────
    #   Operaciones de la API
    # ────────────────────────────────────────────────────────────────

    def test_connection(self) -> dict[str, Any]:
        """
        doTest — Verifica la conexión con el CashDro.

        Returns:
            Respuesta completa del servidor.

        Raises:
            CashDroError: Si la autenticación falla u otro error.
        """
        return self._call("doTest")

    def start_operation(
        self,
        op_type: int = 4,
        amount: Optional[float] = None,
        posid: str = POS_ID,
        posuser: str = POS_USER,
        aliasid: str = ALIAS_ID,
    ) -> str:
        """
        startOperation — Inicia una transacción en el CashDro.

        Args:
            op_type: Tipo de operación (4 = venta/cobro).
            amount: Monto en euros (ej: 18.25). Se multiplica por 100 internamente.
            posid: Identificador del punto de venta.
            posuser: Usuario del punto de venta.
            aliasid: Identificador del equipo.

        Returns:
            operationId (string) de la transacción iniciada.

        Raises:
            CashDroError: Si el CashDro rechaza la operación.
        """
        params: dict[str, Any] = {
            "type": str(op_type),
            "posid": posid,
            "posuser": posuser,
            "aliasid": aliasid,
        }

        if amount is not None:
            # El monto se envía multiplicado por 100, sin decimales
            amount_cents = int(round(amount * 100))
            params["parameters"] = {"amount": str(amount_cents)}

        data = self._call("startOperation", params)
        response = data.get("response", {})
        operation = response.get("operation", {})

        # La estructura puede variar: a veces viene anidado "operation" dentro de "operation"
        if "operation" in operation:
            operation = operation["operation"]

        operation_id: str = operation.get("operationId", "")
        if not operation_id:
            raise CashDroError(-99, "No se recibió operationId en la respuesta")
        return operation_id

    def acknowledge_operation(self, operation_id: str) -> dict[str, Any]:
        """
        acknowledgeOperationId — Confirma una transacción para su ejecución.

        Args:
            operation_id: ID de la operación a confirmar.

        Returns:
            Respuesta del servidor.
        """
        return self._call("acknowledgeOperationId", {"operationId": operation_id})

    def ask_operation(self, operation_id: str) -> dict[str, Any]:
        """
        askOperation — Consulta el estado de una operación.

        Args:
            operation_id: ID de la operación.

        Returns:
            Diccionario con el estado de la operación.
            Ejemplo: {"state": "F", "totalin": "2500", "totalout": "0", ...}
        """
        data = self._call("askOperation", {"operationId": operation_id})
        response = data.get("response", {})
        operation = response.get("operation", {})

        # Normalizar estructura anidada
        if "operation" in operation:
            operation = operation["operation"]

        return operation

    def finish_operation(self, operation_id: str, end_type: int = 1) -> dict[str, Any]:
        """
        finishOperation — Finaliza o cancela una transacción.

        Args:
            operation_id: ID de la operación.
            end_type: 1 = finalizar normalmente, 2 = anular/cancelar.

        Returns:
            Respuesta del servidor.
        """
        return self._call("finishOperation", {"operationId": operation_id, "type": str(end_type)})

    def set_operation_imported(self, operation_id: str) -> dict[str, Any]:
        """
        setOperationImported — Marca una operación como importada (confirmada).

        Args:
            operation_id: ID de la operación.

        Returns:
            Respuesta del servidor.
        """
        return self._call("setOperationImported", {"operationId": operation_id})

    def ask_levels(self) -> dict[str, Any]:
        """
        askLevels — Consulta los niveles de efectivo del CashDro.

        Returns:
            Diccionario con los niveles de efectivo.
        """
        data = self._call("askLevels")
        response = data.get("response", {})
        levels = response.get("levels", {})
        if "levels" in levels:
            levels = levels["levels"]
        return levels

    def ask_alerts(self) -> list[dict[str, Any]]:
        """
        askAlerts — Consulta las alertas activas del CashDro.

        Returns:
            Lista de alertas activas.
        """
        data = self._call("askAlerts")
        response = data.get("response", {})
        alerts = response.get("alerts", [])
        if isinstance(alerts, dict) and "alerts" in alerts:
            alerts = alerts["alerts"]
        return alerts if isinstance(alerts, list) else []

    def ask_diagnosis(self) -> dict[str, Any]:
        """
        askDiagnosis — Obtiene el diagnóstico del equipo.

        Returns:
            Diccionario con información de diagnóstico.
        """
        data = self._call("askDiagnosis")
        response = data.get("response", {})
        diagnosis = response.get("diagnosis", {})
        if "diagnosis" in diagnosis:
            diagnosis = diagnosis["diagnosis"]
        return diagnosis

    # ────────────────────────────────────────────────────────────────
    #   Utilidad: esperar finalización con polling
    # ────────────────────────────────────────────────────────────────

    def wait_for_completion(
        self,
        operation_id: str,
        poll_interval: int = POLL_INTERVAL,
        poll_timeout: int = POLL_TIMEOUT,
        cancel_event: Optional[Callable[[], bool]] = None,
    ) -> dict[str, Any]:
        """
        Realiza polling de askOperation hasta que la operación finalice (state='F')
        o se alcance el timeout.

        Args:
            operation_id: ID de la operación a monitorear.
            poll_interval: Segundos entre cada consulta.
            poll_timeout: Timeout total en segundos.
            cancel_event: Función que retorna True si se debe cancelar la espera.

        Returns:
            Diccionario con el estado final de la operación.

        Raises:
            TimeoutError: Si se agota el tiempo de polling.
        """
        start_time = time.monotonic()

        while True:
            # Verificar cancelación externa (Ctrl+C)
            if cancel_event is not None and cancel_event():
                raise KeyboardInterrupt("Operación cancelada por el usuario")

            # Verificar timeout
            elapsed = time.monotonic() - start_time
            if elapsed >= poll_timeout:
                raise TimeoutError(
                    f"La operación no finalizó tras {poll_timeout} segundos de espera"
                )

            # Consultar estado
            state_data = self.ask_operation(operation_id)
            state = state_data.get("state", "")

            if state == "F":
                # Verificar si hubo error durante la operación
                with_error = str(state_data.get("withError", "false")).lower()
                if with_error == "true":
                    raise CashDroError(-99, "La operación finalizó con error (billete atascado, etc.)")
                # Operación finalizada exitosamente
                return state_data

            # Estados válidos durante la ejecución:
            #   I = pendiente de acknowledge (inicial)
            #   Q = en cola
            #   E = ejecutándose (en progreso)
            # Cualquier otro estado no reconocido es un error
            if state not in ("I", "Q", "E", ""):
                error_msg = state_data.get("errorMessage", "Error durante la operación")
                raise CashDroError(-99, f"Estado inesperado '{state}': {error_msg}")

            # Esperar antes del siguiente polling
            time.sleep(poll_interval)

