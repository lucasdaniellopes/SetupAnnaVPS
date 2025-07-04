#!/bin/bash
# Script automatizado para instalação do Docker, configuração do Swarm,
# criação das redes e volumes, e deploy das stacks com sistema melhorado

##############################
# Configurações globais
##############################
CONFIG_DIR="/root/.docker_installer"
CONFIG_FILE="$CONFIG_DIR/config.env"
DNS_CONFIG_FILE=""
DOMINIO_BASE=""
declare -A PREFIXOS
declare -A STACK_INFO
declare -A DEPENDENCIAS
declare -A PASSWORDS

# Definir informações das stacks
init_stack_info() {
    # Infraestrutura
    STACK_INFO[traefik]="Reverse proxy com SSL automático|infraestrutura|traefik"
    STACK_INFO[portainer]="Interface web para gerenciar Docker|infraestrutura|portainer"
    
    # Bancos de dados
    STACK_INFO[postgres]="Banco de dados PostgreSQL|banco_dados|pgadmin"
    STACK_INFO[pgvector]="PostgreSQL com extensão pgvector|banco_dados|pgvector"
    STACK_INFO[pgbouncer]="Pool de conexões PostgreSQL|banco_dados|pgbouncer"
    STACK_INFO[redis]="Cache em memória|banco_dados|redis"
    
    # Aplicações
    STACK_INFO[evolution]="API do WhatsApp|aplicacao|evolution"
    STACK_INFO[chatwoot]="Plataforma de atendimento ao cliente|aplicacao|chatwoot"
    STACK_INFO[directus]="CMS Headless|aplicacao|directus"
    STACK_INFO[minio]="Armazenamento de objetos S3|aplicacao|minio"
    STACK_INFO[rabbitmq]="Message broker|aplicacao|rabbitmq"
    STACK_INFO[stirlingpdf]="Ferramenta de manipulação de PDF|aplicacao|pdf"
    
    # Monitoramento
    STACK_INFO[prometheus]="Sistema de monitoramento|monitoramento|prometheus"
    STACK_INFO[grafana]="Dashboard de métricas|monitoramento|grafana"
    STACK_INFO[dozzle]="Visualizador de logs Docker|monitoramento|logs"
    
    # Definir dependências
    DEPENDENCIAS[pgbouncer]="postgres"
    DEPENDENCIAS[evolution]="postgres redis"
    DEPENDENCIAS[chatwoot]="postgres redis"
    DEPENDENCIAS[directus]="postgres redis"
    DEPENDENCIAS[grafana]="prometheus"
}

# Perfis de instalação
declare -A PERFIS
PERFIS[minimo]="traefik portainer"
PERFIS[basico]="traefik portainer postgres redis"
PERFIS[completo]="traefik portainer postgres pgvector pgbouncer redis evolution chatwoot directus minio rabbitmq stirlingpdf prometheus grafana dozzle"

##############################
# Funções utilitárias
##############################

# Verificar se está rodando como root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Este script precisa ser executado como root ou com sudo"
        exit 1
    fi
}

# Instalar dependências necessárias
install_dependencies() {
    echo "[+] Instalando dependências..."
    apt-get update -qq
    apt-get install -y dialog curl wget openssl jq > /dev/null 2>&1
}

# Criar diretório de configuração
create_config_dir() {
    [ ! -d "$CONFIG_DIR" ] && mkdir -p "$CONFIG_DIR"
}

# Salvar configuração
save_config() {
    local key=$1
    local value=$2
    echo "export $key=\"$value\"" >> "$CONFIG_FILE"
}

# Carregar configuração
load_config() {
    [ -f "$CONFIG_FILE" ] && source "$CONFIG_FILE"
}

# Função para gerar senha aleatória
gerar_senha() {
    local length=${1:-16}
    openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c "$length"
}

# Função para exibir mensagens de erro
exibir_erro() {
    dialog --title "ERRO" --msgbox "$1" 8 60
    clear
}

# Função para verificar resultado do comando
verificar_comando() {
    if [ $? -ne 0 ]; then
        exibir_erro "Erro ao executar: $1"
        return 1
    fi
    return 0
}

# Obter IP do servidor
get_server_ip() {
    hostname -I | awk '{print $1}'
}

##############################
# Funções de verificação
##############################

# Verificar se Docker está instalado
check_docker() {
    command -v docker >/dev/null 2>&1
}

# Verificar se Swarm está inicializado
check_swarm() {
    docker info 2>/dev/null | grep -q "Swarm: active"
}

# Verificar se stack está instalada
check_stack() {
    local stack=$1
    docker stack ls 2>/dev/null | grep -q "^$stack"
}

##############################
# Funções de instalação básica
##############################

# Instalar Docker
install_docker() {
    dialog --title "Instalação do Docker" --infobox "Instalando Docker..." 3 40
    
    curl -fsSL https://get.docker.com | sh > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker > /dev/null 2>&1
    
    if check_docker; then
        dialog --title "Sucesso" --msgbox "Docker instalado com sucesso!" 6 40
    else
        exibir_erro "Falha ao instalar Docker"
        return 1
    fi
}

# Inicializar Swarm
init_swarm() {
    local server_ip=$(get_server_ip)
    dialog --title "Inicialização do Swarm" --infobox "Inicializando Docker Swarm..." 3 40
    
    docker swarm init --advertise-addr "$server_ip" > /dev/null 2>&1
    
    if check_swarm; then
        dialog --title "Sucesso" --msgbox "Swarm inicializado com sucesso!\nIP: $server_ip" 7 50
        save_config "SERVER_IP" "$server_ip"
    else
        exibir_erro "Falha ao inicializar Swarm"
        return 1
    fi
}

##############################
# Funções de recursos Docker
##############################

# Criar network se não existir
create_network() {
    local network=$1
    if ! docker network ls --format "{{.Name}}" | grep -q "^$network$"; then
        docker network create --driver overlay "$network" > /dev/null 2>&1
        echo "[+] Network '$network' criada"
    else
        echo "[i] Network '$network' já existe"
    fi
}

# Criar volume se não existir
create_volume() {
    local volume=$1
    if ! docker volume ls --format "{{.Name}}" | grep -q "^$volume$"; then
        docker volume create "$volume" > /dev/null 2>&1
        echo "[+] Volume '$volume' criado"
    else
        echo "[i] Volume '$volume' já existe"
    fi
}

# Criar config se não existir
create_docker_config() {
    local config_name=$1
    local config_file=$2
    if ! docker config ls --format "{{.Name}}" | grep -q "^$config_name$"; then
        docker config create "$config_name" "$config_file" > /dev/null 2>&1
        echo "[+] Config '$config_name' criada"
    else
        echo "[i] Config '$config_name' já existe"
    fi
}

##############################
# Sistema de dependências
##############################

# Resolver todas as dependências de uma stack
resolve_dependencies() {
    local stack=$1
    local resolved=()
    
    _resolve_deps_recursive() {
        local s=$1
        local deps="${DEPENDENCIAS[$s]}"
        
        if [ -n "$deps" ]; then
            for dep in $deps; do
                if [[ ! " ${resolved[@]} " =~ " $dep " ]]; then
                    _resolve_deps_recursive "$dep"
                fi
            done
        fi
        
        if [[ ! " ${resolved[@]} " =~ " $s " ]]; then
            resolved+=("$s")
        fi
    }
    
    _resolve_deps_recursive "$stack"
    echo "${resolved[@]}"
}

# Resolver dependências para lista de stacks
resolve_all_dependencies() {
    local stacks=($@)
    local all_resolved=()
    
    for stack in "${stacks[@]}"; do
        local deps=($(resolve_dependencies "$stack"))
        for dep in "${deps[@]}"; do
            if [[ ! " ${all_resolved[@]} " =~ " $dep " ]]; then
                all_resolved+=("$dep")
            fi
        done
    done
    
    echo "${all_resolved[@]}"
}

##############################
# Sistema de prefixos de domínio
##############################

# Inicializar prefixos padrão
init_default_prefixes() {
    local stacks=($@)
    for stack in "${stacks[@]}"; do
        local info="${STACK_INFO[$stack]}"
        local prefix=$(echo "$info" | cut -d'|' -f3)
        PREFIXOS[$stack]="$prefix"
    done
    
    # Prefixos especiais
    PREFIXOS[minio_console]="console.minio"
}

# Customizar prefixos
customize_prefixes() {
    local stacks=($@)
    local customize
    
    dialog --title "Personalizar Prefixos" --yesno "Deseja personalizar os prefixos de domínio?" 6 50
    customize=$?
    
    if [ $customize -eq 0 ]; then
        for stack in "${stacks[@]}"; do
            local current="${PREFIXOS[$stack]}"
            local new_prefix=$(dialog --stdout --title "Prefixo para $stack" \
                --inputbox "Prefixo atual: $current.$DOMINIO_BASE\nNovo prefixo (ou Enter para manter):" 9 60)
            
            if [ -n "$new_prefix" ]; then
                PREFIXOS[$stack]="$new_prefix"
            fi
            
            # MinIO tem console adicional
            if [ "$stack" = "minio" ]; then
                current="${PREFIXOS[minio_console]}"
                new_prefix=$(dialog --stdout --title "Prefixo para MinIO Console" \
                    --inputbox "Prefixo atual: $current.$DOMINIO_BASE\nNovo prefixo (ou Enter para manter):" 9 60)
                
                if [ -n "$new_prefix" ]; then
                    PREFIXOS[minio_console]="$new_prefix"
                fi
            fi
        done
    fi
}

##############################
# Geração de configuração DNS
##############################

generate_dns_config() {
    local stacks=($@)
    local timestamp=$(date +"%d/%m/%Y %H:%M")
    
    DNS_CONFIG_FILE="dns_config_${DOMINIO_BASE//./_}_$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$DNS_CONFIG_FILE" << EOF
============================================================
CONFIGURAÇÃO DNS - CLOUDFLARE
============================================================
Domínio Base: $DOMINIO_BASE
Data: $timestamp

REGISTROS DNS NECESSÁRIOS:
----------------------------------------
1. Registro A:
   Nome: @
   Conteúdo: [IP_DO_SEU_SERVIDOR]
   Proxy: Desativado (DNS only)

2. Registros CNAME:
EOF

    for stack in "${stacks[@]}"; do
        local prefix="${PREFIXOS[$stack]}"
        cat >> "$DNS_CONFIG_FILE" << EOF
   - Nome: $prefix
     Conteúdo: @
     Proxy: Desativado (DNS only)
EOF
        
        # MinIO console adicional
        if [ "$stack" = "minio" ]; then
            local console_prefix="${PREFIXOS[minio_console]}"
            cat >> "$DNS_CONFIG_FILE" << EOF
   - Nome: $console_prefix
     Conteúdo: @
     Proxy: Desativado (DNS only)
EOF
        fi
    done
    
    cat >> "$DNS_CONFIG_FILE" << EOF

----------------------------------------
URLS DE ACESSO APÓS INSTALAÇÃO:
----------------------------------------
EOF

    for stack in "${stacks[@]}"; do
        local info="${STACK_INFO[$stack]}"
        local desc=$(echo "$info" | cut -d'|' -f1)
        local prefix="${PREFIXOS[$stack]}"
        echo "- $desc: https://$prefix.$DOMINIO_BASE" >> "$DNS_CONFIG_FILE"
        
        if [ "$stack" = "minio" ]; then
            local console_prefix="${PREFIXOS[minio_console]}"
            echo "  Console: https://$console_prefix.$DOMINIO_BASE" >> "$DNS_CONFIG_FILE"
        fi
    done
    
    cat >> "$DNS_CONFIG_FILE" << EOF

============================================================
IMPORTANTE:
- Aguarde a propagação DNS (até 48h)
- Certificados SSL serão gerados automaticamente
- Mantenha o Proxy do Cloudflare desativado inicialmente
============================================================

CREDENCIAIS DOS SERVIÇOS:
----------------------------------------
EOF

    # Adicionar credenciais ao arquivo
    for key in "${!PASSWORDS[@]}"; do
        echo "$key: ${PASSWORDS[$key]}" >> "$DNS_CONFIG_FILE"
    done
    
    cat >> "$DNS_CONFIG_FILE" << EOF
============================================================
EOF
}

##############################
# Geração de YAMLs das stacks
##############################

# Gerar YAML do Traefik
generate_traefik_yaml() {
    local le_email="${LE_EMAIL:-admin@$DOMINIO_BASE}"
    local cf_email="${CF_EMAIL:-}"
    local cf_api_key="${CF_API_KEY:-}"
    local prefix="${PREFIXOS[traefik]}"
    
    cat > traefik.yaml << EOF
version: "3.8"

services:
  traefik:
    image: traefik:v3.0
    command:
      - --providers.docker=true
      - --providers.docker.swarmMode=true
      - --providers.docker.network=externa
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.le.acme.email=$le_email
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.le.acme.tlschallenge=true
      - --certificatesresolvers.le.acme.httpchallenge.entrypoint=web
EOF

    if [ -n "$cf_email" ] && [ -n "$cf_api_key" ]; then
        cat >> traefik.yaml << EOF
      - --certificatesresolvers.le.acme.dnschallenge=true
      - --certificatesresolvers.le.acme.dnschallenge.provider=cloudflare
EOF
    fi

    cat >> traefik.yaml << EOF
      - --api.dashboard=true
      - --log.level=INFO
    ports:
      - target: 80
        published: 80
        mode: host
      - target: 443
        published: 443
        mode: host
    environment:
      CF_API_EMAIL: "$cf_email"
      CF_API_KEY: "$cf_api_key"
    volumes:
      - traefik_certificates:/letsencrypt
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - externa
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.traefik.rule=Host(\`$prefix.$DOMINIO_BASE\`)
        - traefik.http.routers.traefik.entrypoints=websecure
        - traefik.http.routers.traefik.tls.certresolver=le
        - traefik.http.routers.traefik.service=api@internal
        - traefik.http.services.traefik.loadbalancer.server.port=8080

volumes:
  traefik_certificates:
    external: true

networks:
  externa:
    external: true
EOF
}

# Gerar YAML do Portainer
generate_portainer_yaml() {
    local prefix="${PREFIXOS[portainer]}"
    
    cat > portainer.yaml << EOF
version: "3.8"

services:
  agent:
    image: portainer/agent:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
    networks:
      - agent_network
    deploy:
      mode: global
      placement:
        constraints: [node.platform.os == linux]

  portainer:
    image: portainer/portainer-ce:latest
    command: -H tcp://tasks.agent:9001 --tlsskipverify
    volumes:
      - portainer_data:/data
    networks:
      - agent_network
      - externa
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints: [node.role == manager]
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.portainer.rule=Host(\`$prefix.$DOMINIO_BASE\`)
        - traefik.http.routers.portainer.entrypoints=websecure
        - traefik.http.routers.portainer.tls.certresolver=le
        - traefik.http.services.portainer.loadbalancer.server.port=9000

volumes:
  portainer_data:
    external: true

networks:
  externa:
    external: true
  agent_network:
    external: true
EOF
}

# Gerar YAML do PostgreSQL
generate_postgres_yaml() {
    local password="${PASSWORDS[postgres]}"
    local prefix="${PREFIXOS[postgres]}"
    
    cat > postgres.yaml << EOF
version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: $password
      POSTGRES_DB: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - postgres_config:/docker-entrypoint-initdb.d
    configs:
      - source: entrypoint_postgres
        target: /docker-entrypoint-initdb.d/init.sql
        mode: 0444
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager

  pgadmin:
    image: dpage/pgadmin4:latest
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@$DOMINIO_BASE
      PGADMIN_DEFAULT_PASSWORD: $password
      PGADMIN_CONFIG_SERVER_MODE: "False"
    volumes:
      - postgres_pgadmin:/var/lib/pgadmin
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.pgadmin.rule=Host(\`$prefix.$DOMINIO_BASE\`)
        - traefik.http.routers.pgadmin.entrypoints=websecure
        - traefik.http.routers.pgadmin.tls.certresolver=le
        - traefik.http.services.pgadmin.loadbalancer.server.port=80

volumes:
  postgres_data:
    external: true
  postgres_config:
    external: true
  postgres_pgadmin:

configs:
  entrypoint_postgres:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
EOF
}

# Implementar geradores para outras stacks...
# Por brevidade, vou adicionar apenas mais alguns exemplos

# Gerar YAML do Redis
generate_redis_yaml() {
    local password="${PASSWORDS[redis]}"
    local prefix="${PREFIXOS[redis]}"
    
    cat > redis.yaml << EOF
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass $password --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager

  redis-commander:
    image: rediscommander/redis-commander:latest
    environment:
      REDIS_HOSTS: local:redis:6379:0:$password
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.redis-commander.rule=Host(\`$prefix.$DOMINIO_BASE\`)
        - traefik.http.routers.redis-commander.entrypoints=websecure
        - traefik.http.routers.redis-commander.tls.certresolver=le
        - traefik.http.services.redis-commander.loadbalancer.server.port=8081

volumes:
  redis_data:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
EOF
}

##############################
# Funções de deploy
##############################

# Criar recursos necessários para uma stack
create_stack_resources() {
    local stack=$1
    
    case $stack in
        traefik)
            create_network "externa"
            create_volume "traefik_certificates"
            ;;
        portainer)
            create_network "externa"
            create_network "agent_network"
            create_volume "portainer_data"
            ;;
        postgres)
            create_network "interna"
            create_volume "postgres_data"
            create_volume "postgres_config"
            if [ -f "stacks/configs/entrypoint_postgres" ]; then
                create_docker_config "entrypoint_postgres" "stacks/configs/entrypoint_postgres"
            fi
            ;;
        redis)
            create_network "interna"
            create_volume "redis_data"
            ;;
        # Adicionar outros recursos conforme necessário...
    esac
}

# Deploy de uma stack
deploy_stack() {
    local stack=$1
    
    echo "[+] Criando recursos para $stack..."
    create_stack_resources "$stack"
    
    echo "[+] Gerando configuração para $stack..."
    case $stack in
        traefik) generate_traefik_yaml ;;
        portainer) generate_portainer_yaml ;;
        postgres) generate_postgres_yaml ;;
        redis) generate_redis_yaml ;;
        # Adicionar outros geradores...
        *) 
            echo "[!] Gerador não implementado para $stack"
            return 1
            ;;
    esac
    
    echo "[+] Realizando deploy de $stack..."
    docker stack deploy -c "$stack.yaml" "$stack"
    
    if [ $? -eq 0 ]; then
        echo "[OK] Stack $stack deployada com sucesso!"
        return 0
    else
        echo "[ERRO] Falha ao deployar $stack"
        return 1
    fi
}

##############################
# Menus interativos
##############################

# Menu de seleção de perfil
select_installation_profile() {
    local choice=$(dialog --stdout --title "Perfil de Instalação" --menu "Escolha um perfil:" 15 60 4 \
        "minimo" "Infraestrutura básica (Traefik + Portainer)" \
        "basico" "Mínimo + Bancos de dados" \
        "completo" "Todas as stacks disponíveis" \
        "custom" "Seleção personalizada")
    
    case $choice in
        minimo|basico|completo)
            echo "${PERFIS[$choice]}"
            ;;
        custom)
            select_custom_stacks
            ;;
        *)
            return 1
            ;;
    esac
}

# Seleção personalizada de stacks
select_custom_stacks() {
    local categories=("infraestrutura" "banco_dados" "aplicacao" "monitoramento")
    local selected_stacks=()
    
    for category in "${categories[@]}"; do
        local options=()
        
        # Construir opções para a categoria
        for stack in "${!STACK_INFO[@]}"; do
            local info="${STACK_INFO[$stack]}"
            local cat=$(echo "$info" | cut -d'|' -f2)
            local desc=$(echo "$info" | cut -d'|' -f1)
            
            if [ "$cat" = "$category" ]; then
                options+=("$stack" "$desc" "off")
            fi
        done
        
        if [ ${#options[@]} -gt 0 ]; then
            local category_title=$(echo "$category" | tr '_' ' ' | tr '[:lower:]' '[:upper:]')
            local choices=$(dialog --stdout --title "$category_title" \
                --checklist "Selecione as stacks de $category:" 20 70 10 \
                "${options[@]}")
            
            if [ -n "$choices" ]; then
                selected_stacks+=($choices)
            fi
        fi
    done
    
    echo "${selected_stacks[@]}"
}

# Coletar informações necessárias
collect_installation_info() {
    # Domínio base
    DOMINIO_BASE=$(dialog --stdout --title "Domínio Base" \
        --inputbox "Digite o domínio base (ex: exemplo.com.br):" 8 60)
    
    if [ -z "$DOMINIO_BASE" ]; then
        exibir_erro "Domínio base é obrigatório!"
        return 1
    fi
    
    # Email Let's Encrypt
    LE_EMAIL=$(dialog --stdout --title "Let's Encrypt" \
        --inputbox "E-mail para Let's Encrypt:" 8 60)
    
    # Cloudflare (opcional)
    dialog --title "Cloudflare DNS" --yesno "Deseja configurar Cloudflare DNS Challenge?" 6 50
    if [ $? -eq 0 ]; then
        CF_EMAIL=$(dialog --stdout --title "Cloudflare" \
            --inputbox "E-mail do Cloudflare:" 8 60)
        CF_API_KEY=$(dialog --stdout --title "Cloudflare" \
            --passwordbox "API Key do Cloudflare:" 8 60)
    fi
    
    # Salvar configurações
    save_config "DOMINIO_BASE" "$DOMINIO_BASE"
    save_config "LE_EMAIL" "$LE_EMAIL"
    save_config "CF_EMAIL" "$CF_EMAIL"
    save_config "CF_API_KEY" "$CF_API_KEY"
    
    return 0
}

# Gerar senhas necessárias
generate_passwords() {
    local stacks=($@)
    
    for stack in "${stacks[@]}"; do
        case $stack in
            postgres)
                PASSWORDS[postgres]=$(gerar_senha)
                PASSWORDS[postgres_desc]="PostgreSQL (usuário: postgres)"
                ;;
            redis)
                PASSWORDS[redis]=$(gerar_senha)
                PASSWORDS[redis_desc]="Redis"
                ;;
            pgvector)
                PASSWORDS[pgvector]=$(gerar_senha)
                PASSWORDS[pgvector_desc]="PGVector (usuário: postgres)"
                ;;
            rabbitmq)
                PASSWORDS[rabbitmq]=$(gerar_senha)
                PASSWORDS[rabbitmq_desc]="RabbitMQ (usuário: admin)"
                ;;
            minio)
                PASSWORDS[minio]=$(gerar_senha)
                PASSWORDS[minio_desc]="MinIO (usuário: minioadmin)"
                ;;
            grafana)
                PASSWORDS[grafana]=$(gerar_senha)
                PASSWORDS[grafana_desc]="Grafana (usuário: admin)"
                ;;
            dozzle)
                PASSWORDS[dozzle]=$(gerar_senha)
                PASSWORDS[dozzle_desc]="Dozzle (usuário: admin)"
                ;;
            portainer)
                if [ -z "$PORTAINER_USERNAME" ]; then
                    PORTAINER_USERNAME=$(dialog --stdout --title "Portainer" \
                        --inputbox "Usuário admin do Portainer:" 8 60)
                fi
                PASSWORDS[portainer]=$(gerar_senha)
                PASSWORDS[portainer_desc]="Portainer (usuário: $PORTAINER_USERNAME)"
                save_config "PORTAINER_USERNAME" "$PORTAINER_USERNAME"
                save_config "PORTAINER_PASSWORD" "${PASSWORDS[portainer]}"
                ;;
        esac
    done
}

# Executar instalação
execute_installation() {
    local stacks=($@)
    local total=${#stacks[@]}
    local current=0
    
    for stack in "${stacks[@]}"; do
        current=$((current + 1))
        local percent=$((current * 100 / total))
        
        echo "$percent" | dialog --gauge "Instalando $stack..." 7 70
        
        if deploy_stack "$stack" >> install.log 2>&1; then
            echo "[OK] $stack instalada" >> install.log
        else
            echo "[ERRO] Falha ao instalar $stack" >> install.log
            dialog --title "Erro" --msgbox "Falha ao instalar $stack. Verifique install.log" 6 50
        fi
    done
    
    dialog --title "Instalação Concluída" --msgbox "Instalação finalizada!\n\nArquivo DNS: $DNS_CONFIG_FILE\nLog: install.log" 10 60
}

##############################
# Fluxo principal
##############################

main() {
    clear
    check_root
    install_dependencies
    create_config_dir
    load_config
    init_stack_info
    
    # Menu principal
    while true; do
        choice=$(dialog --stdout --title "Instalador VPS Melhorado" --menu "Escolha uma opção:" 20 70 10 \
            "1" "Instalar Docker" \
            "2" "Inicializar Swarm" \
            "3" "Instalação Rápida (Perfis)" \
            "4" "Instalação Personalizada" \
            "5" "Gerenciar Stacks" \
            "6" "Configurações" \
            "7" "Sair")
        
        case $choice in
            1)
                if ! check_docker; then
                    install_docker
                else
                    dialog --title "Info" --msgbox "Docker já está instalado!" 6 40
                fi
                ;;
            2)
                if ! check_swarm; then
                    init_swarm
                else
                    dialog --title "Info" --msgbox "Swarm já está inicializado!" 6 40
                fi
                ;;
            3)
                # Verificar pré-requisitos
                if ! check_docker || ! check_swarm; then
                    exibir_erro "Docker e Swarm devem estar instalados primeiro!"
                    continue
                fi
                
                # Selecionar perfil
                stacks=$(select_installation_profile)
                if [ -z "$stacks" ]; then
                    continue
                fi
                
                # Resolver dependências
                stacks=($(resolve_all_dependencies $stacks))
                
                # Coletar informações
                if ! collect_installation_info; then
                    continue
                fi
                
                # Inicializar prefixos
                init_default_prefixes "${stacks[@]}"
                
                # Customizar prefixos
                customize_prefixes "${stacks[@]}"
                
                # Gerar senhas
                generate_passwords "${stacks[@]}"
                
                # Gerar configuração DNS
                generate_dns_config "${stacks[@]}"
                
                # Mostrar configuração DNS
                dialog --title "Configuração DNS" --textbox "$DNS_CONFIG_FILE" 30 80
                
                dialog --title "Continuar?" --yesno "Configure o DNS no Cloudflare antes de continuar.\n\nDeseja prosseguir com a instalação?" 8 60
                if [ $? -eq 0 ]; then
                    execute_installation "${stacks[@]}"
                fi
                ;;
            4)
                # Similar ao 3, mas com seleção personalizada
                if ! check_docker || ! check_swarm; then
                    exibir_erro "Docker e Swarm devem estar instalados primeiro!"
                    continue
                fi
                
                # Instalação personalizada segue o mesmo fluxo
                # mas usa select_custom_stacks diretamente
                ;;
            5)
                # Gerenciar stacks
                manage_stacks_menu
                ;;
            6)
                # Menu de configurações
                settings_menu
                ;;
            7)
                clear
                exit 0
                ;;
        esac
    done
}

# Menu de gerenciamento de stacks
manage_stacks_menu() {
    local stacks=$(docker stack ls --format "{{.Name}}")
    
    if [ -z "$stacks" ]; then
        dialog --title "Info" --msgbox "Nenhuma stack instalada" 6 40
        return
    fi
    
    local choice=$(dialog --stdout --title "Gerenciar Stacks" --menu "Escolha uma ação:" 15 60 5 \
        "1" "Listar stacks" \
        "2" "Remover stack" \
        "3" "Ver logs" \
        "4" "Ver serviços" \
        "5" "Voltar")
    
    case $choice in
        1)
            docker stack ls | dialog --title "Stacks Instaladas" --programbox 20 80
            ;;
        2)
            local stack=$(dialog --stdout --title "Remover Stack" \
                --menu "Selecione a stack:" 15 50 10 \
                $(for s in $stacks; do echo "$s" "$s"; done))
            
            if [ -n "$stack" ]; then
                dialog --title "Confirmar" --yesno "Remover stack $stack?" 6 40
                if [ $? -eq 0 ]; then
                    docker stack rm "$stack"
                    dialog --title "Info" --msgbox "Stack $stack removida" 6 40
                fi
            fi
            ;;
        3)
            local stack=$(dialog --stdout --title "Ver Logs" \
                --menu "Selecione a stack:" 15 50 10 \
                $(for s in $stacks; do echo "$s" "$s"; done))
            
            if [ -n "$stack" ]; then
                local services=$(docker stack services "$stack" --format "{{.Name}}")
                local service=$(dialog --stdout --title "Selecionar Serviço" \
                    --menu "Escolha o serviço:" 15 60 10 \
                    $(for s in $services; do echo "$s" "$s"; done))
                
                if [ -n "$service" ]; then
                    docker service logs "$service" --tail 100 | dialog --title "Logs de $service" --programbox 30 100
                fi
            fi
            ;;
        4)
            local stack=$(dialog --stdout --title "Ver Serviços" \
                --menu "Selecione a stack:" 15 50 10 \
                $(for s in $stacks; do echo "$s" "$s"; done))
            
            if [ -n "$stack" ]; then
                docker stack services "$stack" | dialog --title "Serviços de $stack" --programbox 20 100
            fi
            ;;
    esac
}

# Menu de configurações
settings_menu() {
    local choice=$(dialog --stdout --title "Configurações" --menu "Escolha uma opção:" 15 60 5 \
        "1" "Configurar Cloudflare" \
        "2" "Backup de configuração" \
        "3" "Restaurar configuração" \
        "4" "Ver configuração atual" \
        "5" "Voltar")
    
    case $choice in
        1)
            CF_EMAIL=$(dialog --stdout --title "Cloudflare" \
                --inputbox "E-mail do Cloudflare:" 8 60 "$CF_EMAIL")
            CF_API_KEY=$(dialog --stdout --title "Cloudflare" \
                --passwordbox "API Key do Cloudflare:" 8 60)
            
            save_config "CF_EMAIL" "$CF_EMAIL"
            save_config "CF_API_KEY" "$CF_API_KEY"
            
            dialog --title "Sucesso" --msgbox "Configuração do Cloudflare salva" 6 40
            ;;
        2)
            local backup_file="vps_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
            tar -czf "$backup_file" "$CONFIG_DIR" 2>/dev/null
            dialog --title "Backup" --msgbox "Backup salvo em: $backup_file" 6 50
            ;;
        3)
            local backup_file=$(dialog --stdout --title "Restaurar" \
                --inputbox "Caminho do arquivo de backup:" 8 60)
            
            if [ -f "$backup_file" ]; then
                tar -xzf "$backup_file" -C / 2>/dev/null
                load_config
                dialog --title "Sucesso" --msgbox "Configuração restaurada" 6 40
            else
                exibir_erro "Arquivo não encontrado"
            fi
            ;;
        4)
            if [ -f "$CONFIG_FILE" ]; then
                dialog --title "Configuração Atual" --textbox "$CONFIG_FILE" 20 70
            else
                dialog --title "Info" --msgbox "Nenhuma configuração salva" 6 40
            fi
            ;;
    esac
}

# Executar o programa principal
main