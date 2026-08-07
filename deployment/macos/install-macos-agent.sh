#!/usr/bin/env bash

set -euo pipefail

SERVICE_USER="automation-agent"
SERVICE_GROUP="automation-agent"

INSTALL_DIR="/opt/automation-platform"
AGENTS_DIR="${INSTALL_DIR}/agents"
MACOS_AGENT_DIR="${AGENTS_DIR}/macos_agent"
DOWNLOAD_DIR="${MACOS_AGENT_DIR}/downloads"

CONFIG_DIR="/Library/Application Support/AutomationPlatform"
ENV_FILE="${CONFIG_DIR}/macos-agent.env"

LAUNCHD_NAME="com.automationplatform.macos-agent.plist"
LAUNCHD_DIR="/Library/LaunchDaemons"

SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

PROJECT_ROOT="$(
    cd "${SCRIPT_DIR}/../.."
    pwd
)"

MACOS_AGENT_SOURCE="${PROJECT_ROOT}/agents/macos_agent"

ENV_TEMPLATE="${PROJECT_ROOT}/deployment/macos/macos-agent.env.example"

RUNNER_SOURCE="${PROJECT_ROOT}/deployment/macos/run-macos-agent.sh"

LAUNCHD_SOURCE="${PROJECT_ROOT}/deployment/launchd/${LAUNCHD_NAME}"


require_root() {
    if [[ "${EUID}" -ne 0 ]]; then
        echo "ERROR: This installer must be run as root."
        exit 1
    fi
}


validate_platform() {
    if [[ "$(uname -s)" != "Darwin" ]]; then
        echo "ERROR: This installer must be run on macOS."
        exit 1
    fi
}


validate_sources() {
    if [[ ! -d "${MACOS_AGENT_SOURCE}" ]]; then
        echo "ERROR: macOS Agent source directory was not found:"
        echo "${MACOS_AGENT_SOURCE}"
        exit 1
    fi

    for file in \
        config.py \
        executor.py \
        main.py \
        platform_client.py
    do
        if [[ ! -f "${MACOS_AGENT_SOURCE}/${file}" ]]; then
            echo "ERROR: macOS Agent file was not found:"
            echo "${MACOS_AGENT_SOURCE}/${file}"
            exit 1
        fi
    done

    if [[ ! -f "${ENV_TEMPLATE}" ]]; then
        echo "ERROR: environment template was not found:"
        echo "${ENV_TEMPLATE}"
        exit 1
    fi

    if [[ ! -f "${RUNNER_SOURCE}" ]]; then
        echo "ERROR: macOS Agent launcher was not found:"
        echo "${RUNNER_SOURCE}"
        exit 1
    fi

    if [[ ! -f "${LAUNCHD_SOURCE}" ]]; then
        echo "ERROR: launchd plist was not found:"
        echo "${LAUNCHD_SOURCE}"
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
        exit 1
    fi
}


create_service_account() {
    if ! dscl . -read "/Groups/${SERVICE_GROUP}" >/dev/null 2>&1; then
        echo "ERROR: macOS service account provisioning"
        echo "is not automated yet."
        echo
        echo "Create the following local account first:"
        echo "User: ${SERVICE_USER}"
        echo "Group: ${SERVICE_GROUP}"
        exit 1
    fi

    if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
        echo "ERROR: macOS service user does not exist:"
        echo "${SERVICE_USER}"
        exit 1
    fi
}


create_directories() {
    install \
        -d \
        -o root \
        -g wheel \
        -m 0755 \
        "${INSTALL_DIR}"

    install \
        -d \
        -o root \
        -g wheel \
        -m 0755 \
        "${AGENTS_DIR}"

    install \
        -d \
        -o root \
        -g wheel \
        -m 0755 \
        "${MACOS_AGENT_DIR}"

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

    install \
        -d \
        -o root \
        -g wheel \
        -m 0755 \
        "${INSTALL_DIR}/deployment/macos"
}


install_agent_files() {
    for source_file in \
        "${MACOS_AGENT_SOURCE}/config.py" \
        "${MACOS_AGENT_SOURCE}/executor.py" \
        "${MACOS_AGENT_SOURCE}/main.py" \
        "${MACOS_AGENT_SOURCE}/platform_client.py"
    do
        install \
            -o root \
            -g wheel \
            -m 0644 \
            "${source_file}" \
            "${MACOS_AGENT_DIR}/$(basename "${source_file}")"
    done
}


install_runner() {
    install \
        -o root \
        -g wheel \
        -m 0755 \
        "${RUNNER_SOURCE}" \
        "${INSTALL_DIR}/deployment/macos/run-macos-agent.sh"
}


create_virtual_environment() {
    if [[ ! -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
        python3 -m venv "${INSTALL_DIR}/.venv"
    fi

    if [[ ! -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
        echo "ERROR: macOS Agent virtual environment was not created."
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
        echo "and platform settings before loading the service."
    else
        echo "Existing environment file preserved:"
        echo "${ENV_FILE}"
    fi
}


install_launchd_service() {
    install \
        -o root \
        -g wheel \
        -m 0644 \
        "${LAUNCHD_SOURCE}" \
        "${LAUNCHD_DIR}/${LAUNCHD_NAME}"

    echo
    echo "launchd plist installed:"
    echo "${LAUNCHD_DIR}/${LAUNCHD_NAME}"
    echo
    echo "Service has NOT been loaded or started."
}


main() {
    require_root
    validate_platform
    validate_sources
    validate_python

    create_service_account
    create_directories

    install_agent_files
    install_runner
    create_virtual_environment

    install_environment_file
    install_launchd_service

    echo
    echo "macOS Agent installation prepared successfully."
    echo
    echo "Installed Agent:"
    echo "${MACOS_AGENT_DIR}"
    echo
    echo "Python:"
    echo "${INSTALL_DIR}/.venv/bin/python"
    echo
    echo "Configure:"
    echo "${ENV_FILE}"
    echo
    echo "Then validate and load the launchd service."
}


main "$@"