#!/usr/bin/env bash

set -euo pipefail


SERVICE_USER="automation-agent"
SERVICE_GROUP="automation-agent"

INSTALL_DIR="/opt/automation-platform"
AGENTS_DIR="${INSTALL_DIR}/agents"
LINUX_AGENT_DIR="${AGENTS_DIR}/linux_agent"
DOWNLOAD_DIR="${LINUX_AGENT_DIR}/downloads"

CONFIG_DIR="/etc/automation-platform"
ENV_FILE="${CONFIG_DIR}/linux-agent.env"

SERVICE_NAME="automation-platform-linux-agent.service"
SYSTEMD_DIR="/etc/systemd/system"

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

PROJECT_ROOT="$(
    cd "${SCRIPT_DIR}/../.."
    pwd
)"

LINUX_AGENT_SOURCE="${PROJECT_ROOT}/agents/linux_agent"

SERVICE_SOURCE="${PROJECT_ROOT}/deployment/systemd/${SERVICE_NAME}"

ENV_TEMPLATE="${PROJECT_ROOT}/deployment/linux/linux-agent.env.example"


require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "ERROR: This installer must be run as root."
        exit 1
    fi
}


validate_sources() {
    if [[ ! -d "${LINUX_AGENT_SOURCE}" ]]; then
        echo "ERROR: Linux Agent source directory was not found:"
        echo "${LINUX_AGENT_SOURCE}"
        exit 1
    fi

    if [[ ! -f "${LINUX_AGENT_SOURCE}/main.py" ]]; then
        echo "ERROR: Linux Agent main.py was not found."
        exit 1
    fi

    if [[ ! -f "${LINUX_AGENT_SOURCE}/config.py" ]]; then
        echo "ERROR: Linux Agent config.py was not found."
        exit 1
    fi

    if [[ ! -f "${LINUX_AGENT_SOURCE}/executor.py" ]]; then
        echo "ERROR: Linux Agent executor.py was not found."
        exit 1
    fi

    if [[ ! -f "${LINUX_AGENT_SOURCE}/platform_client.py" ]]; then
        echo "ERROR: Linux Agent platform_client.py was not found."
        exit 1
    fi

    if [[ ! -f "${SERVICE_SOURCE}" ]]; then
        echo "ERROR: systemd service file was not found:"
        echo "${SERVICE_SOURCE}"
        exit 1
    fi

    if [[ ! -f "${ENV_TEMPLATE}" ]]; then
        echo "ERROR: environment template was not found:"
        echo "${ENV_TEMPLATE}"
        exit 1
    fi
}


validate_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "ERROR: python3 was not found."
        exit 1
    fi

    if ! python3 -m venv --help >/dev/null 2>&1; then
        echo "ERROR: Python venv support is not available."
        echo "Install the Python venv package for this Linux distribution."
        exit 1
    fi
}


create_service_account() {
    if ! getent group "${SERVICE_GROUP}" >/dev/null 2>&1; then
        groupadd --system "${SERVICE_GROUP}"
    fi

    if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
        useradd \
            --system \
            --gid "${SERVICE_GROUP}" \
            --home-dir "${INSTALL_DIR}" \
            --shell /usr/sbin/nologin \
            "${SERVICE_USER}"
    fi
}


create_directories() {
    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        "${INSTALL_DIR}"

    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        "${AGENTS_DIR}"

    install \
        -d \
        -o root \
        -g root \
        -m 0755 \
        "${LINUX_AGENT_DIR}"

    install \
        -d \
        -o "${SERVICE_USER}" \
        -g "${SERVICE_GROUP}" \
        -m 0750 \
        "${DOWNLOAD_DIR}"

    install \
        -d \
        -o root \
        -g "${SERVICE_GROUP}" \
        -m 0750 \
        "${CONFIG_DIR}"
}


install_agent_files() {
    for source_file in \
        "${LINUX_AGENT_SOURCE}/config.py" \
        "${LINUX_AGENT_SOURCE}/executor.py" \
        "${LINUX_AGENT_SOURCE}/main.py" \
        "${LINUX_AGENT_SOURCE}/platform_client.py"
    do
        install \
            -o root \
            -g root \
            -m 0644 \
            "${source_file}" \
            "${LINUX_AGENT_DIR}/$(basename "${source_file}")"
    done
}


create_virtual_environment() {
    if [[ ! -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
        python3 -m venv "${INSTALL_DIR}/.venv"
    fi

    if [[ ! -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
        echo "ERROR: Linux Agent virtual environment was not created."
        exit 1
    fi
}


install_environment_file() {
    if [[ ! -f "${ENV_FILE}" ]]; then
        install \
            -o root \
            -g "${SERVICE_GROUP}" \
            -m 0640 \
            "${ENV_TEMPLATE}" \
            "${ENV_FILE}"

        echo
        echo "Created:"
        echo "${ENV_FILE}"
        echo
        echo "Configure the real Agent API key"
        echo "and platform settings before starting the service."
    else
        echo "Existing environment file preserved:"
        echo "${ENV_FILE}"
    fi
}


install_systemd_service() {
    install \
        -o root \
        -g root \
        -m 0644 \
        "${SERVICE_SOURCE}" \
        "${SYSTEMD_DIR}/${SERVICE_NAME}"

    systemctl daemon-reload

    systemctl enable "${SERVICE_NAME}"
}


main() {
    require_root
    validate_sources
    validate_python

    create_service_account
    create_directories

    install_agent_files
    create_virtual_environment

    install_environment_file
    install_systemd_service

    echo
    echo "Linux Agent installation prepared successfully."
    echo
    echo "Installed Agent:"
    echo "${LINUX_AGENT_DIR}"
    echo
    echo "Python:"
    echo "${INSTALL_DIR}/.venv/bin/python"
    echo
    echo "Service has NOT been started."
    echo
    echo "Configure:"
    echo "${ENV_FILE}"
    echo
    echo "Then validate and start the service."
}


main "$@"