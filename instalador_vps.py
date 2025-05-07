#!/usr/bin/env python3
"""
Instalador VPS Híbrido
- Menu interativo para instalar Docker, Swarm, stacks, etc.
- Validação de pré-requisitos
- Expansível para novas funções
"""
import os
import subprocess
import sys

def print_header():
    print("="*50)
    print("INSTALADOR VPS - MENU PRINCIPAL")
    print("="*50)

def menu():
    while True:
        print_header()
        print("1. Instalar Docker e Docker Compose")
        print("2. Inicializar Swarm")
        print("3. Deploy de Stacks (Traefik, Portainer, etc)")
        print("4. Sair")
        choice = input("Escolha uma opção: ")
        if choice == '1':
            instalar_docker()
        elif choice == '2':
            inicializar_swarm()
        elif choice == '3':
            deploy_stacks()
        elif choice == '4':
            print("Saindo...")
            sys.exit(0)
        else:
            print("Opção inválida!\n")

def instalar_docker():
    print("[+] Instalando Docker...")
    # Instala Docker (exemplo para Ubuntu/Debian)
    subprocess.run("curl -fsSL https://get.docker.com | sh", shell=True, check=True)
    subprocess.run(["systemctl", "enable", "docker"])
    subprocess.run(["systemctl", "start", "docker"])
    print("[OK] Docker instalado!\n")

def inicializar_swarm():
    print("[+] Inicializando Docker Swarm...")
    subprocess.run(["docker", "swarm", "init"], check=False)
    print("[OK] Swarm inicializado!\n")

import json

def obter_portainer_config_path():
    return os.path.join(os.path.dirname(__file__), "portainer_config.json")

def ler_portainer_config():
    config_path = obter_portainer_config_path()
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return None

def salvar_portainer_config(username, password):
    config_path = obter_portainer_config_path()
    with open(config_path, "w") as f:
        json.dump({"PORTAINER_USERNAME": username, "PORTAINER_PASSWORD": password}, f)

def solicitar_credenciais_portainer():
    print("Insira as credenciais para o Portainer:")
    username = input("Usuário: ").strip()
    while not username:
        username = input("Usuário (não pode ser vazio): ").strip()
    password = input("Senha: ").strip()
    while not password:
        password = input("Senha (não pode ser vazia): ").strip()
    salvar_portainer_config(username, password)
    return {"PORTAINER_USERNAME": username, "PORTAINER_PASSWORD": password}

def criar_network(nome, driver="overlay"):
    result = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    if nome not in result.stdout.split():
        subprocess.run(["docker", "network", "create", "--driver", driver, nome], check=True)
        print(f"[+] Network '{nome}' criada.")
    else:
        print(f"[i] Network '{nome}' já existe.")

def criar_volume(nome):
    result = subprocess.run(["docker", "volume", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)
    if nome not in result.stdout.split():
        subprocess.run(["docker", "volume", "create", nome], check=True)
        print(f"[+] Volume '{nome}' criado.")
    else:
        print(f"[i] Volume '{nome}' já existe.")

def gerar_traefik_yaml(le_email, traefik_domain):
    return f'''version: "3.3"
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
      - --certificatesresolvers.le.acme.email={le_email}
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
'''

def gerar_portainer_yaml(portainer_image, portainer_domain):
    return f'''version: "3.3"
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
    image: {portainer_image}
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
        constraints: [ node.role == manager ]
      labels:
        - "traefik.enable=true"
        - "traefik.docker.network=externa"
        - "traefik.http.routers.portainer.rule=Host(`{portainer_domain}`)"
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
'''

def deploy_stacks():
    print("[+] Deploy das stacks...")

    # 1. Criar networks e volumes necessários
    criar_network("externa")
    criar_network("agent_network")
    criar_volume("traefik_certificates")
    criar_volume("portainer_data")

    # 2. Coletar dados mínimos para geração dos YAMLs
    le_email = input("E-mail para Let's Encrypt (Traefik): ").strip()
    while not le_email:
        le_email = input("E-mail não pode ser vazio: ").strip()
    traefik_domain = input("Domínio para o painel Traefik (ex: traefik.seudominio.com): ").strip()
    while not traefik_domain:
        traefik_domain = input("Domínio não pode ser vazio: ").strip()
    portainer_domain = input("Domínio para o Portainer (ex: portainer.seudominio.com): ").strip()
    while not portainer_domain:
        portainer_domain = input("Domínio não pode ser vazio: ").strip()
    portainer_image = "portainer/portainer-ce:2.21.2"  # Pode ser ajustado conforme opção do usuário

    # 3. Gerar YAMLs
    with open("traefik.yaml", "w") as f:
        f.write(gerar_traefik_yaml(le_email, traefik_domain))
    with open("portainer.yaml", "w") as f:
        f.write(gerar_portainer_yaml(portainer_image, portainer_domain))

    # --- Command Pattern para stacks ---
    from abc import ABC, abstractmethod
    import requests

    class StackCommand(ABC):
        @abstractmethod
        def name(self):
            pass
        @abstractmethod
        def generate_yaml(self):
            pass
        def deploy(self, portainer_url, username, password):
            # 1. Autentica e obtém token JWT
            resp = requests.post(
                f"{portainer_url}/api/auth",
                json={"Username": username, "Password": password}
            )
            resp.raise_for_status()
            jwt = resp.json()["jwt"]
            # 2. Obter ID do Swarm
            headers = {"Authorization": f"Bearer {jwt}"}
            swarm_resp = requests.get(f"{portainer_url}/api/swarm", headers=headers)
            swarm_resp.raise_for_status()
            swarm_id = swarm_resp.json().get("Id", "local")
            # 3. Criar stack
            payload = {
                "Name": self.name(),
                "StackFileContent": self.generate_yaml(),
                "SwarmID": swarm_id,
                "Env": []
            }
            stack_resp = requests.post(
                f"{portainer_url}/api/stacks?type=3&method=string&endpointId=1",
                headers={**headers, "Content-Type": "application/json"},
                json=payload
            )
            stack_resp.raise_for_status()
            print(f"Stack '{self.name()}' criada via Portainer API!")

    class TraefikStack(StackCommand):
        def __init__(self, le_email, traefik_domain):
            self.le_email = le_email
            self.traefik_domain = traefik_domain
        def name(self):
            return "traefik"
        def generate_yaml(self):
            return gerar_traefik_yaml(self.le_email, self.traefik_domain)

    # --- Fim Command Pattern ---

    # Dados do Portainer
    portainer_url = f"http://localhost:9000"
    import secrets, string, time, requests
    from abc import ABC, abstractmethod

    portainer_url = f"http://localhost:9000"
    config = ler_portainer_config()
    if not config or not config.get("PORTAINER_USERNAME") or not config.get("PORTAINER_PASSWORD"):
        print("[INFO] Portainer não detectado ou sem credenciais. Instalando Portainer...")
        portainer_domain = input("Domínio para o Portainer (ex: portainer.seudominio.com): ").strip()
        while not portainer_domain:
            portainer_domain = input("Domínio não pode ser vazio: ").strip()
        username = input("Usuário admin do Portainer: ").strip()
        while not username:
            username = input("Usuário não pode ser vazio: ").strip()
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        salvar_portainer_config(username, password)
        # Deploy do Portainer via Docker CLI (primeiro acesso)
        with open("portainer.yaml", "w") as f:
            f.write(PortainerStack(portainer_domain, username, password).generate_yaml())
        subprocess.run(["docker", "stack", "deploy", "-c", "portainer.yaml", "portainer"], check=True)
        print(f"[INFO] Portainer deployado.")
        print(f"Usuário: {username}")
        print(f"Senha gerada: {password}")
        # Esperar Portainer estar pronto
        for i in range(30):
            try:
                r = requests.get(f"{portainer_url}/api/status", timeout=2)
                if r.status_code == 200:
                    print("[OK] Portainer está pronto para uso!")
                    break
            except Exception:
                time.sleep(2)
        else:
            print("[ERRO] Portainer não respondeu a tempo. Tente novamente.")
            return
    else:
        portainer_domain = input("Domínio para o Portainer (ex: portainer.seudominio.com): ").strip()
        while not portainer_domain:
            portainer_domain = input("Domínio não pode ser vazio: ").strip()
        username = config.get("PORTAINER_USERNAME")
        password = config.get("PORTAINER_PASSWORD")
        print("[OK] Portainer já está instalado e credenciais carregadas.")

    import secrets, string, time, requests
    from abc import ABC, abstractmethod

    def gerar_senha_aleatoria(tamanho=12):
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(tamanho))

    class StackCommand(ABC):
        @abstractmethod
        def name(self):
            pass
        @abstractmethod
        def generate_yaml(self):
            pass
        def deploy(self, portainer_url, username, password):
            resp = requests.post(
                f"{portainer_url}/api/auth",
                json={"Username": username, "Password": password}
            )
            resp.raise_for_status()
            jwt = resp.json()["jwt"]
            headers = {"Authorization": f"Bearer {jwt}"}
            swarm_resp = requests.get(f"{portainer_url}/api/swarm", headers=headers)
            swarm_resp.raise_for_status()
            swarm_id = swarm_resp.json().get("Id", "local")
            payload = {
                "Name": self.name(),
                "StackFileContent": self.generate_yaml(),
                "SwarmID": swarm_id,
                "Env": []
            }
            stack_resp = requests.post(
                f"{portainer_url}/api/stacks?type=3&method=string&endpointId=1",
                headers={**headers, "Content-Type": "application/json"},
                json=payload
            )
            stack_resp.raise_for_status()
            print(f"Stack '{self.name()}' criada via Portainer API!")

    class PortainerStack(StackCommand):
        def __init__(self, portainer_domain, username, password, image="portainer/portainer-ce:2.21.2"):
            self.portainer_domain = portainer_domain
            self.username = username
            self.password = password
            self.image = image
        def name(self):
            return "portainer"
        def generate_yaml(self):
            return f'''version: "3.3"
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
    image: {self.image}
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
        constraints: [ node.role == manager ]
      labels:
        - "traefik.enable=true"
        - "traefik.docker.network=externa"
        - "traefik.http.routers.portainer.rule=Host(`{self.portainer_domain}`)"
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
'''

    class TraefikStack(StackCommand):
        def __init__(self, le_email, traefik_domain):
            self.le_email = le_email
            self.traefik_domain = traefik_domain
        def name(self):
            return "traefik"
        def generate_yaml(self):
            return gerar_traefik_yaml(self.le_email, self.traefik_domain)

    # --- Garantir Portainer instalado antes de tudo ---
    portainer_url = f"http://localhost:9000"
    config = ler_portainer_config()
    if not config or not config.get("PORTAINER_USERNAME") or not config.get("PORTAINER_PASSWORD"):
        print("[INFO] Portainer não detectado ou sem credenciais. Instalando Portainer...")
        portainer_domain = input("Domínio para o Portainer (ex: portainer.seudominio.com): ").strip()
        while not portainer_domain:
            portainer_domain = input("Domínio não pode ser vazio: ").strip()
        username = input("Usuário admin do Portainer: ").strip()
        while not username:
            username = input("Usuário não pode ser vazio: ").strip()
        password = gerar_senha_aleatoria()
        salvar_portainer_config(username, password)
        # Deploy do Portainer via Docker CLI (primeiro acesso)
        with open("portainer.yaml", "w") as f:
            f.write(PortainerStack(portainer_domain, username, password).generate_yaml())
        subprocess.run(["docker", "stack", "deploy", "-c", "portainer.yaml", "portainer"], check=True)
        print(f"[INFO] Portainer deployado.")
        print(f"Usuário: {username}")
        print(f"Senha gerada: {password}")
        # Esperar Portainer estar pronto
        for i in range(30):
            try:
                r = requests.get(f"{portainer_url}/api/status", timeout=2)
                if r.status_code == 200:
                    print("[OK] Portainer está pronto para uso!")
                    break
            except Exception:
                time.sleep(2)
        else:
            print("[ERRO] Portainer não respondeu a tempo. Tente novamente.")
            return
    else:
        portainer_domain = input("Domínio para o Portainer (ex: portainer.seudominio.com): ").strip()
        while not portainer_domain:
            portainer_domain = input("Domínio não pode ser vazio: ").strip()
        username = config.get("PORTAINER_USERNAME")
        password = config.get("PORTAINER_PASSWORD")
        print("[OK] Portainer já está instalado e credenciais carregadas.")

    # 4. Criar e deploy das stacks (agora já pode usar API)
    stacks = []
    le_email = input("E-mail para Let's Encrypt (Traefik): ").strip()
    while not le_email:
        le_email = input("E-mail não pode ser vazio: ").strip()
    traefik_domain = input("Domínio para o painel Traefik (ex: traefik.seudominio.com): ").strip()
    while not traefik_domain:
        traefik_domain = input("Domínio não pode ser vazio: ").strip()
    stacks.append(TraefikStack(le_email, traefik_domain))
    for stack in stacks:
        stack.deploy(portainer_url, username, password)

    # 5. Exibir informações finais
    print("\n[OK] Deploy concluído!")
    print(f"Acesse o painel Traefik: https://{traefik_domain}")
    print(f"Acesse o Portainer: https://{portainer_domain}")
    print("OBS: Pode levar alguns minutos até que os certificados Let's Encrypt estejam emitidos.")

if __name__ == "__main__":
    menu()
