#!/bin/bash
# Script automatizado para instalação do Docker, configuração do Swarm,
# criação das redes e volumes, e deploy das stacks do Traefik, Portainer e outras aplicações

##############################
# Verificação de privilégios e dependências
##############################
if [ "$(id -u)" -ne 0 ]; then
    echo "Este script precisa ser executado como root ou com sudo"
    exit 1
fi

# Instalar dialog para interface interativa
apt-get update
apt-get install -y dialog

# Função para exibir mensagens de erro
function exibir_erro() {
    dialog --title "ERRO" --msgbox "$1" 8 60
    clear
}

# Função para verificar resultado do comando
function verificar_comando() {
    if [ $? -ne 0 ]; then
        exibir_erro "Erro ao executar: $1"
        return 1
    fi
    return 0
}

# Função para gerar senha aleatória
function gerar_senha() {
    openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 12
}

# Função para verificar se Traefik está instalado
function verificar_traefik() {
    if docker stack ls | grep -q "traefik"; then
        return 0
    else
        return 1
    fi
}

# Função para verificar se Portainer está instalado
function verificar_portainer() {
    if docker stack ls | grep -q "portainer"; then
        return 0
    else
        return 1
    fi
}

# Função para verificar se a infraestrutura básica está instalada
function verificar_infra_basica() {
    if verificar_traefik && verificar_portainer; then
        return 0
    else
        return 1
    fi
}

# Função para verificar se existem credenciais do Portainer salvas
function verificar_credenciais_portainer() {
    if [ -f "/root/.docker_installer/config.env" ] && grep -q "PORTAINER_USERNAME" "/root/.docker_installer/config.env"; then
        return 0
    else
        return 1
    fi
}

# Função para obter credenciais do Portainer salvas
function obter_credenciais_portainer() {
    if verificar_credenciais_portainer; then
        source /root/.docker_installer/config.env
        return 0
    else
        return 1
    fi
}

# Função para solicitar credenciais do Portainer ao usuário
function solicitar_credenciais_portainer() {
    PORTAINER_USERNAME=$(dialog --stdout --title "Credenciais do Portainer" --inputbox "Informe o nome de usuário que deseja para o Portainer:" 8 60)
    if [ -z "$PORTAINER_USERNAME" ]; then
        exibir_erro "Nome de usuário do Portainer não pode ser vazio!"
        return 1
    fi
    
    # Gerar senha automaticamente
    PORTAINER_PASSWORD=$(gerar_senha)
    
    return 0
}

##############################
# 0. Menu principal e atualização da VPS
##############################
dialog --title "Instalador Docker Swarm + Stacks" \
       --yesno "Este instalador irá configurar Docker Swarm e as stacks escolhidas na sua VPS.\n\nDeseja continuar?" 10 60

if [ $? -ne 0 ]; then
    clear
    echo "Instalação cancelada pelo usuário."
    exit 0
fi

dialog --title "Atualização da VPS" --infobox "Atualizando a VPS. Aguarde..." 5 60
apt-get update && apt-get upgrade -y
verificar_comando "atualização da VPS"

##############################
# 1. Coleta de informações gerais do usuário
##############################
# Coleta do domínio principal
MAIN_DOMAIN=$(dialog --stdout --title "Configuração" --inputbox "Informe o domínio principal (ex: seudominio.com):" 8 60)
if [ -z "$MAIN_DOMAIN" ]; then
    exibir_erro "Domínio não pode ser vazio!"
    exit 1
fi

##############################
# 2. Instalação do Docker e inicialização do Swarm
##############################
# Verificar se o Docker já está instalado
if ! command -v docker &> /dev/null; then
    dialog --title "Instalação Docker" --infobox "Instalando o Docker. Aguarde..." 5 60
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    verificar_comando "instalação do Docker"
else
    dialog --title "Docker" --infobox "Docker já está instalado. Continuando..." 5 60
    sleep 2
fi

# Verificar se o Swarm já está inicializado
if ! docker info | grep -q "Swarm: active"; then
    # Inicializa o Docker Swarm
    SERVER_IP=$(hostname -I | awk '{ print $1 }')
    export SERVER_IP
    dialog --title "Docker Swarm" --infobox "Iniciando o Docker Swarm com o IP: ${SERVER_IP}" 5 60
    docker swarm init --advertise-addr ${SERVER_IP}
    verificar_comando "inicialização do Docker Swarm"
else
    dialog --title "Docker Swarm" --infobox "Docker Swarm já está ativo. Continuando..." 5 60
    SERVER_IP=$(hostname -I | awk '{ print $1 }')
    export SERVER_IP
    sleep 2
fi

##############################
# 3. Criação de redes overlay e volumes externos
##############################
dialog --title "Redes e Volumes" --infobox "Criando redes overlay e volumes necessários..." 5 60
docker network create --driver=overlay agent_network 2>/dev/null || true
docker network create --driver=overlay externa 2>/dev/null || true
docker network create --driver=overlay interna 2>/dev/null || true

docker volume create traefik_certificates 2>/dev/null || true
docker volume create portainer_data 2>/dev/null || true
docker volume create postgres_data 2>/dev/null || true
sleep 2

##############################
# 4. Menu de seleção de stacks para instalação
##############################
while true; do
    dialog --title "Seleção de Stacks para Instalação" \
          --checklist "Selecione as stacks que deseja instalar:" 15 70 5 \
          "1" "Traefik + Portainer (Infraestrutura básica)" $(verificar_infra_basica && echo "on" || echo "off") \
          "2" "PostgreSQL (Banco de dados)" "off" \
          "3" "Nginx Proxy Manager" "off" \
          "4" "WordPress" "off" \
          "0" "Iniciar Instalação" "on" 2> /tmp/stacks_escolhidas.txt

    STACKS_ESCOLHIDAS=$(cat /tmp/stacks_escolhidas.txt)
    rm -f /tmp/stacks_escolhidas.txt
    
    if [[ "$STACKS_ESCOLHIDAS" == *"0"* ]]; then
        break
    fi
done

# Verificar se a infraestrutura básica precisa ser instalada para outras stacks
if [[ "$STACKS_ESCOLHIDAS" == *"2"* || "$STACKS_ESCOLHIDAS" == *"3"* || "$STACKS_ESCOLHIDAS" == *"4"* ]]; then
    if ! verificar_infra_basica; then
        dialog --title "Dependência" --yesno "As stacks selecionadas requerem Traefik e Portainer, que não estão instalados.\n\nDeseja instalar Traefik e Portainer também?" 10 60
        if [ $? -eq 0 ]; then
            STACKS_ESCOLHIDAS="1 $STACKS_ESCOLHIDAS"
        else
            dialog --title "Aviso" --msgbox "A instalação não pode continuar sem Traefik e Portainer." 7 50
            exit 1
        fi
    fi
fi

##############################
# 5. Configuração das stacks selecionadas
##############################

# 5.1 Configuração da infraestrutura básica (Traefik + Portainer)
TRAEFIK_DOMAIN=""
PORTAINER_DOMAIN=""
LE_EMAIL=""
CLOUD_FLARE_ENABLED=false
PORTAINER_IMAGE=""
PORTAINER_USERNAME=""
PORTAINER_PASSWORD=""

if [[ "$STACKS_ESCOLHIDAS" == *"1"* ]]; then
    # Configuração específica do Traefik
    TRAEFIK_DOMAIN="traefik.${MAIN_DOMAIN}"
    PORTAINER_DOMAIN="portainer.${MAIN_DOMAIN}"
    
    # Coleta do email para Let's Encrypt
    LE_EMAIL=$(dialog --stdout --title "Configuração do Traefik" --inputbox "Informe o email para Let's Encrypt (ex: email@dominio.com):" 8 60)
    if [ -z "$LE_EMAIL" ]; then
        exibir_erro "Email para Let's Encrypt não pode ser vazio!"
        exit 1
    fi
    
    # Configuração do Cloudflare
    dialog --title "Configuração do Cloudflare" \
           --yesno "Deseja usar Cloudflare para o desafio DNS?" 7 60

    USE_CLOUDFLARE=$?
    
    if [ $USE_CLOUDFLARE -eq 0 ]; then
        CF_EMAIL=$(dialog --stdout --title "Configuração Cloudflare" --inputbox "Informe o email da Cloudflare:" 8 60)
        CF_API_KEY=$(dialog --stdout --title "Configuração Cloudflare" --passwordbox "Informe a chave API da Cloudflare:" 8 60)
        
        if [ -z "$CF_EMAIL" ] || [ -z "$CF_API_KEY" ]; then
            exibir_erro "Email ou API Key da Cloudflare não podem ser vazios!"
            exit 1
        fi
        
        CLOUD_FLARE_ENABLED=true
    fi
    
    # Seleção da edição do Portainer
    dialog --title "Edição do Portainer" \
           --menu "Selecione a edição do Portainer:" 10 60 2 \
           "ce" "Community Edition (Gratuita)" \
           "ee" "Enterprise Edition (Paga)" 2> /tmp/edition.txt

    EDITION=$(cat /tmp/edition.txt)
    rm -f /tmp/edition.txt

    if [[ "$EDITION" == "ee" ]]; then
        PORTAINER_IMAGE="portainer/portainer-ee:2.21.2"
    else
        PORTAINER_IMAGE="portainer/portainer-ce:2.21.2"
    fi
    
    # Solicitar credenciais do Portainer
    solicitar_credenciais_portainer
    if [ $? -ne 0 ]; then
        exit 1
    fi
else
    # Para outras stacks, verificar se temos credenciais do Portainer
    if ! verificar_credenciais_portainer; then
        dialog --title "Credenciais do Portainer" --msgbox "Para instalar esta stack, precisamos das credenciais do Portainer.\nSolicite-as a seguir." 8 60
        solicitar_credenciais_portainer
        if [ $? -ne 0 ]; then
            exit 1
        fi
    else
        obter_credenciais_portainer
    fi
fi

# Resumo das configurações
RESUMO="Domínio Principal: ${MAIN_DOMAIN}\n"

if [[ "$STACKS_ESCOLHIDAS" == *"1"* ]]; then
    RESUMO+="Traefik Domain: ${TRAEFIK_DOMAIN}\n"
    RESUMO+="Portainer Domain: ${PORTAINER_DOMAIN}\n"
    RESUMO+="Let's Encrypt Email: ${LE_EMAIL}\n"
    RESUMO+="Portainer Edition: ${EDITION} (${PORTAINER_IMAGE})\n"
    RESUMO+="Portainer Username: ${PORTAINER_USERNAME}\n"
    RESUMO+="Portainer Password: ${PORTAINER_PASSWORD}\n"
    if [ "$CLOUD_FLARE_ENABLED" = true ]; then
      RESUMO+="Cloudflare Email: ${CF_EMAIL}\n"
      RESUMO+="Cloudflare API Key: ********\n"
    fi
fi

dialog --title "Resumo das Configurações" --yesno "$RESUMO\n\nAs configurações estão corretas?" 15 70

if [ $? -ne 0 ]; then
    clear
    echo "Instalação cancelada pelo usuário."
    exit 0
fi

##############################
# 6. Instalação das stacks selecionadas
##############################

# 6.1 Instalação da infraestrutura básica (Traefik + Portainer)
if [[ "$STACKS_ESCOLHIDAS" == *"1"* ]]; then
    # 6.1.1 Instalação do Traefik
    dialog --title "Traefik" --infobox "Gerando e implantando a stack do Traefik..." 5 60

    if [ "$CLOUD_FLARE_ENABLED" = true ]; then
        # Configuração com Cloudflare
        cat << EOF > traefik.yaml
version: "3.3"
services:
  traefik:
    image: traefik:v2.2.11
    command:
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.web.http.redirections.entryPoint.to=websecure
      - --entrypoints.web.http.redirections.entryPoint.scheme=https
      - --entrypoints.websecure.address=:443
      - --providers.docker.exposedbydefault=false
      - --providers.docker.swarmMode=true
      - --providers.docker.network=externa
      - --providers.docker.endpoint=unix:///var/run/docker.sock
      - --certificatesresolvers.le.acme.email=${LE_EMAIL}
      - --certificatesresolvers.le.acme.httpchallenge.entrypoint=web
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.le.acme.tlschallenge=true
      - --certificatesresolvers.cf.acme.email=${CF_EMAIL}
      - --certificatesresolvers.cf.acme.storage=/cloudflare/acme.json
      - --certificatesresolvers.cf.acme.dnschallenge=true
      - --certificatesresolvers.cf.acme.dnschallenge.provider=cloudflare
      - --certificatesresolvers.cf.acme.dnschallenge.delaybeforecheck=0
      - --certificatesresolvers.cf.acme.dnschallenge.resolvers=1.1.1.1:53,8.8.8.8:53
      - --log.level=DEBUG
    environment:
      CF_API_KEY: "${CF_API_KEY}"
      CF_API_EMAIL: "${CF_EMAIL}"
    ports:
      - target: 80
        published: 80
        mode: host
        protocol: tcp
      - target: 443
        published: 443
        mode: host
        protocol: tcp
    volumes:
      - traefik_certificates:/letsencrypt
      - traefik_certificates:/cloudflare
      - /var/run/docker.sock:/var/run/docker.sock:ro
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    networks:
      - externa

volumes:
  traefik_certificates:
    external: true

networks:
  externa:
    external: true
EOF
    else
        # Configuração apenas com Let's Encrypt
        cat << EOF > traefik.yaml
version: "3.3"
services:
  traefik:
    image: traefik:v2.2.11
    command:
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.web.http.redirections.entryPoint.to=websecure
      - --entrypoints.web.http.redirections.entryPoint.scheme=https
      - --entrypoints.websecure.address=:443
      - --providers.docker.exposedbydefault=false
      - --providers.docker.swarmMode=true
      - --providers.docker.network=externa
      - --providers.docker.endpoint=unix:///var/run/docker.sock
      - --certificatesresolvers.le.acme.email=${LE_EMAIL}
      - --certificatesresolvers.le.acme.httpchallenge.entrypoint=web
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.le.acme.tlschallenge=true
      - --log.level=DEBUG
    ports:
      - target: 80
        published: 80
        mode: host
        protocol: tcp
      - target: 443
        published: 443
        mode: host
        protocol: tcp
    volumes:
      - traefik_certificates:/letsencrypt
      - /var/run/docker.sock:/var/run/docker.sock:ro
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
    networks:
      - externa

volumes:
  traefik_certificates:
    external: true

networks:
  externa:
    external: true
EOF
    fi

    docker stack deploy -c traefik.yaml traefik
    verificar_comando "deploy da stack do Traefik"

    # 6.1.2 Instalação do Portainer
    dialog --title "Portainer" --infobox "Gerando e implantando a stack do Portainer..." 5 60

    # Arquivo para inicialização do Portainer com usuário administrativo
    mkdir -p /tmp/portainer-init
    cat << EOF > /tmp/portainer-init/create-admin.sh
#!/bin/sh
set -e

# Esperar o serviço do Portainer iniciar
echo "Esperando o serviço do Portainer iniciar..."
until wget -q --spider http://localhost:9000/api/status; do
  sleep 2
done

# Criar o usuário administrativo
curl -X POST http://localhost:9000/api/users/admin/init \
  -H "Content-Type: application/json" \
  -d '{
    "Username": "${PORTAINER_USERNAME}",
    "Password": "${PORTAINER_PASSWORD}"
  }'

echo "Usuário administrativo criado com sucesso!"
EOF

    chmod +x /tmp/portainer-init/create-admin.sh

    # Criar config para inicialização
    docker config rm portainer_init 2>/dev/null || true
    docker config create portainer_init /tmp/portainer-init/create-admin.sh

    cat << EOF > portainer.yaml
version: "3.3"

services:
  agent:
    image: portainer/agent:2.21.2
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /var/lib/docker/volumes:/var/lib/docker/volumes
    networks:
      - agent_network
    deploy:
      mode: global
      placement:
        constraints: [ node.platform.os == linux ]

  portainer:
    image: ${PORTAINER_IMAGE}
    command: -H tcp://tasks.agent:9001 --tlsskipverify --templates https://raw.githubusercontent.com/gustavo9br/Stacks-Incriveis/refs/heads/main/templates.json
    volumes:
      - portainer_data:/data
    networks:
      - agent_network
      - externa
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints: [ node.role == manager ]
      labels:
        - "traefik.enable=true"
        - "traefik.docker.network=externa"
        - "traefik.http.routers.portainer.rule=Host(\`${PORTAINER_DOMAIN}\`)"
        - "traefik.http.routers.portainer.entrypoints=websecure"
        - "traefik.http.routers.portainer.priority=1"
        - "traefik.http.routers.portainer.tls.certresolver=le"
        - "traefik.http.routers.portainer.service=portainer"
        - "traefik.http.services.portainer.loadbalancer.server.port=9000"

networks:
  externa:
    external: true
  agent_network:
    external: true

volumes:
  portainer_data:
    external: true
EOF

    docker stack deploy -c portainer.yaml portainer
    verificar_comando "deploy da stack do Portainer"

    # Exibir informações sobre o Portainer
    dialog --title "Portainer" --msgbox "Portainer foi implantado com sucesso!\n\nAcesse: https://${PORTAINER_DOMAIN}\n\nCredenciais de acesso:\nUsuário: ${PORTAINER_USERNAME}\nSenha: ${PORTAINER_PASSWORD}" 12 70
fi

# 6.2 Instalação do PostgreSQL
if [[ "$STACKS_ESCOLHIDAS" == *"2"* ]]; then
    # Instalação do PostgreSQL
    dialog --title "PostgreSQL" --infobox "Configurando o PostgreSQL..." 5 60
    
    # Gerar senha para o PostgreSQL
    POSTGRES_PASSWORD=$(gerar_senha)
    
    # Criar o script de inicialização (entrypoint)
    mkdir -p /tmp/postgres-init
    cat << EOF > /tmp/postgres-init/init-db.sh
#!/bin/bash
set -e

# Chama o entrypoint original
docker-entrypoint.sh "\$@" &

# Espera o PostgreSQL iniciar
until pg_isready -U "\$POSTGRES_USER"; do
  echo "Esperando o PostgreSQL iniciar..."
  sleep 2
done

# Seu script de criação de bancos de dados
DATABASES="chatwoot,n8n,evolution,dify,directus"

IFS=',' read -r -a DB_ARRAY <<< "\$DATABASES"

for db in "\${DB_ARRAY[@]}"; do
  echo "Verificando se o banco de dados '\$db'..."
  RESULT=\$(psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" -tc "SELECT 1 FROM pg_database WHERE datname = '\$db';")
  if [ -z "\$RESULT" ]; then
    echo "Banco de dados '\$db' não existe. Criando..."
    psql -U "\$POSTGRES_USER" -d "\$POSTGRES_DB" -c "CREATE DATABASE \\"\$db\\";"
  else
    echo "Banco de dados '\$db' já existe."
  fi
done

wait -n
EOF
    
    # Criar config do entrypoint
    docker config rm entrypoint_postgres 2>/dev/null || true
    docker config create entrypoint_postgres /tmp/postgres-init/init-db.sh
    
    # Criar o stack file do PostgreSQL
    cat << EOF > postgres.yaml
version: "3.3"

services:
  postgres:
    image: postgres:16
    command: [
        "postgres", 
        "--max_connections=300",
        "--wal_level=minimal",
        "--max_wal_senders=0",
      ]
    environment: 
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_USER=postgres
      - POSTGRES_DB=postgres
      - POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256"
    networks: 
      - interna
    volumes: 
      - postgres_data:/var/lib/postgresql/data
    deploy: 
      mode: replicated
      replicas: 1
      resources: 
        limits: 
          cpus: "2"
          memory: 2048M
      configs: 
        - source: entrypoint_postgres
          target: /docker-entrypoint-initdb.d/init-db.sh
          mode: 0755

volumes: 
  postgres_data: 
    external: true

configs: 
  entrypoint_postgres: 
    external: true

networks: 
  interna: 
    external: true
EOF
    
    # Deploy da stack
    docker stack deploy -c postgres.yaml postgres
    verificar_comando "deploy da stack do PostgreSQL"
    
    # Mostrar informações de acesso
    dialog --title "PostgreSQL Instalado" --msgbox "PostgreSQL instalado com sucesso!\n\nInformações de acesso:\nHost: postgres\nPorta: 5432\nUsuário: postgres\nSenha: ${POSTGRES_PASSWORD}\n\nBancos de dados criados:\n- chatwoot\n- n8n\n- evolution\n- dify\n- directus" 15 70
fi

# 6.3 Instalação do Nginx Proxy Manager (placeholder)
if [[ "$STACKS_ESCOLHIDAS" == *"3"* ]]; then
    dialog --title "Nginx Proxy Manager" --msgbox "Funcionalidade a ser implementada." 5 60
    # Aqui você adicionaria o código para instalar Nginx Proxy Manager
fi

# 6.4 Instalação do WordPress (placeholder)
if [[ "$STACKS_ESCOLHIDAS" == *"4"* ]]; then
    dialog --title "WordPress" --msgbox "Funcionalidade a ser implementada." 5 60
    # Aqui você adicionaria o código para instalar WordPress
fi

##############################
# 7. Mensagens finais de acesso
##############################
clear
echo "-------------------------------------------------------------"
echo "Deploy concluído!"
if verificar_infra_basica; then
    echo "Acesse o Portainer em: https://${PORTAINER_DOMAIN}"
    echo "Usuário: ${PORTAINER_USERNAME}"
    echo "Senha: ${PORTAINER_PASSWORD}"
    echo "Acesse o dashboard do Traefik em: https://${TRAEFIK_DOMAIN}"
    echo "OBS: Pode levar alguns minutos até que os certificados Let's Encrypt sejam emitidos."
fi
echo "-------------------------------------------------------------"

# Opção de salvar as configurações para uso futuro
dialog --title "Salvar Configurações" \
      --yesno "Deseja salvar as configurações utilizadas para uso futuro?" 7 60

if [ $? -eq 0 ]; then
    CONFIG_DIR="/root/.docker_installer"
    mkdir -p $CONFIG_DIR
    
    cat << EOF > $CONFIG_DIR/config.env
MAIN_DOMAIN=${MAIN_DOMAIN}
SERVER_IP=${SERVER_IP}
EOF

    # Adicionar configurações da infraestrutura básica se instalada
    if [[ "$STACKS_ESCOLHIDAS" == *"1"* ]]; then
        cat << EOF >> $CONFIG_DIR/config.env
LE_EMAIL=${LE_EMAIL}
TRAEFIK_DOMAIN=${TRAEFIK_DOMAIN}
PORTAINER_DOMAIN=${PORTAINER_DOMAIN}
EDITION=${EDITION}
PORTAINER_IMAGE=${PORTAINER_IMAGE}
EOF

        cat << EOF >> $CONFIG_DIR/config.env
CLOUD_FLARE_ENABLED=${CLOUD_FLARE_ENABLED}
EOF
        if [ "$CLOUD_FLARE_ENABLED" = true ]; then
            cat << EOF >> $CONFIG_DIR/config.env
CF_EMAIL=${CF_EMAIL}
CF_API_KEY=${CF_API_KEY}
EOF
        fi
    fi

    # Adicionar credenciais do Portainer
    cat << EOF >> $CONFIG_DIR/config.env
PORTAINER_USERNAME=${PORTAINER_USERNAME}
PORTAINER_PASSWORD=${PORTAINER_PASSWORD}
EOF

    # Adicionar configurações do PostgreSQL se instalado
    if [[ "$STACKS_ESCOLHIDAS" == *"2"* ]]; then
        cat << EOF >> $CONFIG_DIR/config.env
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
EOF
    fi
    
    chmod 600 $CONFIG_DIR/config.env
    dialog --title "Configurações Salvas" --msgbox "Configurações salvas em $CONFIG_DIR/config.env" 6 60
fi

MSG_FINAL="A instalação foi concluída com sucesso!\n\n"
if verificar_infra_basica; then
    MSG_FINAL+="Acesse o Portainer em:\nhttps://${PORTAINER_DOMAIN}\n"
    MSG_FINAL+="Usuário: ${PORTAINER_USERNAME}\n"
    MSG_FINAL+="Senha: ${PORTAINER_PASSWORD}\n\n"
    MSG_FINAL+="Acesse o Traefik em:\nhttps://${TRAEFIK_DOMAIN}"
fi

dialog --title "Instalação Concluída" --msgbox "$MSG_FINAL" 12 60
clear 