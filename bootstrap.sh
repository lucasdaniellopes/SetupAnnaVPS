#!/bin/bash
# Script de bootstrap para instalador VPS híbrido
# 1. Detecta SO, instala Python3 e dependências mínimas
# 2. Baixa e executa o instalador principal em Python

set -e

# Detecta se é root
if [ "$(id -u)" -ne 0 ]; then
    echo "Este script precisa ser executado como root ou com sudo."
    exit 1
fi

# Detecta SO
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Não foi possível detectar o sistema operacional."
    exit 1
fi

# Instala Python3 e curl, se necessário
if ! command -v python3 >/dev/null 2>&1; then
    if [[ "$OS" == "ubuntu" || "$OS" == "debian" ]]; then
        apt-get update && apt-get install -y python3 python3-pip curl
    elif [[ "$OS" == "centos" || "$OS" == "rhel" ]]; then
        yum install -y python3 python3-pip curl
    else
        echo "Distribuição não suportada automaticamente. Instale Python3 manualmente."
        exit 1
    fi
fi

# Baixa o instalador principal em Python (ajuste o caminho conforme necessário)
INSTALLER_URL="https://raw.githubusercontent.com/lucasdaniellopes/InstaladorVPS/main/instalador_vps.py"
INSTALLER_FILE="/tmp/instalador_vps.py"
curl -fsSL "$INSTALLER_URL" -o "$INSTALLER_FILE"
chmod +x "$INSTALLER_FILE"

# Executa o instalador principal
python3 "$INSTALLER_FILE"
