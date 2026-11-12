"""
config.py — Constantes de configuración para CashDroController.

Los datos de conexión se leen de variables de entorno. No versionar
credenciales reales: usar .env o el entorno del sistema.
"""

import os

# ─── Conexión CashDro ────────────────────────────────────────────────
CASHDRO_HOST: str = os.getenv("CASHDRO_HOST", "192.0.2.10")
CASHDRO_USER: str = os.getenv("CASHDRO_USER", "USUARIO_CASHDRO")
CASHDRO_PASSWORD: str = os.getenv("CASHDRO_PASSWORD", "CLAVE_CASHDRO")
API_BASE_PATH: str = "/Cashdro3WS/index3.php"

# ─── Timeouts ────────────────────────────────────────────────────────
REQUEST_TIMEOUT: int = 10       # segundos — timeout por llamada HTTP
MAX_RETRIES: int = 3            # reintentos ante fallo de conexión
MAX_RETRIES_SYSTEM_BUSY: int = 3   # reintentos extra para código -1900 (System busy)
RETRY_DELAY_SYSTEM_BUSY: int = 5   # segundos de espera entre reintentos por System busy
POLL_INTERVAL: int = 2          # segundos entre consultas de estado
POLL_TIMEOUT: int = 120         # timeout total de polling (2 minutos)

# ─── Códigos de error CashDro ───────────────────────────────────────
ERROR_CODES: dict[int, str] = {
    -1:    "Authentication Failed — usuario o contraseña incorrectos",
    -2:    "Operation not queued / not found",
    -3:    "Wrong amount / Invalid parameters — monto inválido",
    -4:    "User does not have permission — usuario sin permisos",
    -99:   "Invalid Parameters",
    -1900: "System busy — sistema ocupado, reintente más tarde",
    -998:  "Can't start operation. Check system status",
    -999:  "CashDro service is not running",
}

# ─── Valores por defecto para transacciones ─────────────────────────
POS_ID: str = "1"
POS_USER: str = os.getenv("POS_USER", "USUARIO_CASHDRO")
ALIAS_ID: str = os.getenv("ALIAS_ID", "CAJA-01")
AMOUNT_MAX: float = 9999.99
