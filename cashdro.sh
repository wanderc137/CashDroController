#!/bin/bash
# Requiere las variables CASHDRO_SSH_HOST, CASHDRO_SSH_USER y CASHDRO_SSH_PASS.
set -euo pipefail
: "${CASHDRO_SSH_HOST:?Define CASHDRO_SSH_HOST}"
: "${CASHDRO_SSH_USER:?Define CASHDRO_SSH_USER}"
: "${CASHDRO_SSH_PASS:?Define CASHDRO_SSH_PASS}"
sshpass -p "$CASHDRO_SSH_PASS" ssh -t -o StrictHostKeyChecking=no \
  "$CASHDRO_SSH_USER@$CASHDRO_SSH_HOST" \
  'C:\\Users\\sshuser\\python-3.12.5\\python.exe C:\\Users\\sshuser\\CashDroController\\main.py'
