#!/bin/bash
# Bootstrap script para instalação facilitada do VPS Installer
# Uso: curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/bootstrap.sh | sudo bash

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir com cor
print_color() {
    echo -e "${2}${1}${NC}"
}

# Banner
clear
echo "=============================================="
echo "   INSTALADOR VPS - SETUP AUTOMÁTICO v2.0"
echo "=============================================="
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    print_color "Este script precisa ser executado como root!" "$RED"
    exit 1
fi

print_color "[1/4] Detectando sistema operacional..." "$YELLOW"

# Detectar OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    print_color "Sistema operacional não suportado!" "$RED"
    exit 1
fi

# Instalar dependências baseado no OS
case $OS in
    ubuntu|debian)
        print_color "Sistema detectado: $OS $VERSION" "$GREEN"
        print_color "[2/4] Instalando dependências..." "$YELLOW"
        apt-get update -qq >/dev/null 2>&1
        apt-get install -y python3 python3-pip curl wget git dialog >/dev/null 2>&1
        pip3 install requests >/dev/null 2>&1
        ;;
    centos|rhel|fedora)
        print_color "Sistema detectado: $OS $VERSION" "$GREEN"
        print_color "[2/4] Instalando dependências..." "$YELLOW"
        yum install -y python3 python3-pip curl wget git >/dev/null 2>&1
        pip3 install requests >/dev/null 2>&1
        ;;
    *)
        print_color "Sistema operacional $OS não suportado!" "$RED"
        exit 1
        ;;
esac

print_color "Dependências instaladas com sucesso!" "$GREEN"

# Criar diretório de trabalho
INSTALL_DIR="/opt/vps-installer"
print_color "[3/4] Criando diretório de instalação em $INSTALL_DIR..." "$YELLOW"

# Limpar instalação anterior se existir
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# URL base do repositório (ajuste conforme seu repo)
REPO_URL="https://raw.githubusercontent.com/lucasdaniellopes/Instalador/main"

print_color "[4/4] Baixando arquivos do instalador..." "$YELLOW"

# Função para baixar arquivo com verificação
download_file() {
    local file=$1
    local target_dir=$2
    
    if [ -n "$target_dir" ]; then
        mkdir -p "$target_dir"
        wget -q "$REPO_URL/$target_dir/$file" -O "$target_dir/$file" || {
            print_color "Erro ao baixar $target_dir/$file" "$RED"
            return 1
        }
    else
        wget -q "$REPO_URL/$file" -O "$file" || {
            print_color "Erro ao baixar $file" "$RED"
            return 1
        }
    fi
}

# Baixar arquivos principais
print_color "  - Baixando instalador principal..." "$YELLOW"
download_file "instalador_vps.py" ""

print_color "  - Baixando implementações das stacks..." "$YELLOW"
download_file "stack_implementations.py" ""

print_color "  - Baixando script bash alternativo..." "$YELLOW"
download_file "deploy_stacks_v2.sh" ""
chmod +x deploy_stacks_v2.sh

# Criar estrutura de diretórios
mkdir -p stacks/configs

# Baixar arquivos YAML das stacks
print_color "  - Baixando configurações das stacks..." "$YELLOW"
stacks=(
    "traefik.yaml"
    "portainer.yaml"
    "postgres.yaml"
    "pgvector.yaml"
    "pgbouncer.yaml"
    "redis.yaml"
    "evolution.yaml"
    "chatwoot.yaml"
    "directus.yaml"
    "minio.yaml"
    "rabbitmq.yaml"
    "stirlingpdf.yaml"
    "prometheus.yaml"
    "grafana.yaml"
    "dozzle.yaml"
)

for stack in "${stacks[@]}"; do
    download_file "$stack" "stacks" || print_color "  ! Stack $stack não encontrada (opcional)" "$YELLOW"
done

# Baixar configurações
print_color "  - Baixando arquivos de configuração..." "$YELLOW"
configs=(
    "entrypoint_postgres"
    "config_prometheus"
    "config_dozzle"
)

for config in "${configs[@]}"; do
    download_file "$config" "stacks/configs" || print_color "  ! Config $config não encontrada (opcional)" "$YELLOW"
done

print_color "\n✓ Download concluído com sucesso!" "$GREEN"

# Criar script de atalho
cat > /usr/local/bin/vps-installer << 'EOF'
#!/bin/bash
cd /opt/vps-installer
python3 instalador_vps.py
EOF

chmod +x /usr/local/bin/vps-installer

# Mensagem final
echo ""
echo "=============================================="
print_color "INSTALAÇÃO CONCLUÍDA!" "$GREEN"
echo "=============================================="
echo ""
echo "O instalador foi configurado com sucesso!"
echo ""
echo "Para executar o instalador, use um dos comandos:"
echo ""
print_color "  Opção 1 (Recomendado):" "$GREEN"
echo "  vps-installer"
echo ""
print_color "  Opção 2:" "$GREEN"
echo "  cd $INSTALL_DIR && python3 instalador_vps.py"
echo ""
print_color "  Opção 3 (Script Bash):" "$GREEN"
echo "  cd $INSTALL_DIR && ./deploy_stacks_v2.sh"
echo ""
echo "=============================================="
echo ""

# Perguntar se quer executar agora
read -p "Deseja executar o instalador agora? (s/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    cd "$INSTALL_DIR"
    python3 instalador_vps.py
fi