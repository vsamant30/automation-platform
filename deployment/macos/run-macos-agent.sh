#!/usr/bin/env bash

set -euo pipefail

INSTALL_DIR="/opt/automation-platform"

CONFIG_DIR="/Library/Application Support/AutomationPlatform"
ENV_FILE="${CONFIG_DIR}/macos-agent.env"

PYTHON="${INSTALL_DIR}/.venv/bin/python"


if [[ ! -x "${PYTHON}" ]]; then
    echo "ERROR: macOS Agent Python was not found:"
    echo "${PYTHON}"
    exit 1
fi


if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: macOS Agent environment file was not found:"
    echo "${ENV_FILE}"
    exit 1
fi


set -a

# shellcheck disable=SC1090
source "${ENV_FILE}"

set +a


cd "${INSTALL_DIR}"

exec "${PYTHON}" -m agents.macos_agent.main