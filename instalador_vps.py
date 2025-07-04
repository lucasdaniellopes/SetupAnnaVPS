#!/usr/bin/env python3
"""
Instalador VPS Híbrido - Versão Melhorada
- Sistema de categorização de stacks
- Instalação em lote com perfis
- Sistema de dependências
- Prefixos de domínio customizáveis
- Geração de configuração DNS Cloudflare
"""
import os
import subprocess
import sys
import json
import requests
import secrets
import string
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Configuração de stacks e suas propriedades
STACK_CONFIG = {
    "traefik": {
        "categoria": "infraestrutura",
        "descricao": "Reverse proxy com SSL automático",
        "prefixo": "traefik",
        "dependencias": [],
        "volumes": ["traefik_certificates"],
        "networks": ["externa"]
    },
    "portainer": {
        "categoria": "infraestrutura", 
        "descricao": "Interface web para gerenciar Docker",
        "prefixo": "portainer",
        "dependencias": [],
        "volumes": ["portainer_data"],
        "networks": ["externa", "agent_network"]
    },
    "postgres": {
        "categoria": "banco_dados",
        "descricao": "Banco de dados PostgreSQL",
        "prefixo": "pgadmin",
        "dependencias": [],
        "volumes": ["postgres_data", "postgres_config"],
        "networks": ["interna"],
        "configs": ["entrypoint_postgres"]
    },
    "pgvector": {
        "categoria": "banco_dados",
        "descricao": "PostgreSQL com extensão pgvector",
        "prefixo": "pgvector",
        "dependencias": [],
        "volumes": ["pgvector_data"],
        "networks": ["interna"]
    },
    "pgbouncer": {
        "categoria": "banco_dados",
        "descricao": "Pool de conexões PostgreSQL",
        "prefixo": "pgbouncer",
        "dependencias": ["postgres"],
        "volumes": [],
        "networks": ["interna"]
    },
    "redis": {
        "categoria": "banco_dados",
        "descricao": "Cache em memória",
        "prefixo": "redis",
        "dependencias": [],
        "volumes": ["redis_data"],
        "networks": ["interna"]
    },
    "evolution": {
        "categoria": "aplicacao",
        "descricao": "API do WhatsApp",
        "prefixo": "evolution",
        "dependencias": ["postgres", "redis"],
        "volumes": ["evolution_instances"],
        "networks": ["externa", "interna"]
    },
    "chatwoot": {
        "categoria": "aplicacao",
        "descricao": "Plataforma de atendimento ao cliente",
        "prefixo": "chatwoot",
        "dependencias": ["postgres", "redis"],
        "volumes": ["chatwoot_storage"],
        "networks": ["externa", "interna"]
    },
    "directus": {
        "categoria": "aplicacao",
        "descricao": "CMS Headless",
        "prefixo": "directus",
        "dependencias": ["postgres", "redis"],
        "volumes": ["directus_uploads", "directus_extensions"],
        "networks": ["externa", "interna"]
    },
    "minio": {
        "categoria": "aplicacao",
        "descricao": "Armazenamento de objetos S3",
        "prefixo": "minio",
        "prefixo_console": "console.minio",
        "dependencias": [],
        "volumes": ["minio_data"],
        "networks": ["externa", "interna"]
    },
    "rabbitmq": {
        "categoria": "aplicacao",
        "descricao": "Message broker",
        "prefixo": "rabbitmq",
        "dependencias": [],
        "volumes": ["rabbitmq_data"],
        "networks": ["externa", "interna"]
    },
    "stirlingpdf": {
        "categoria": "aplicacao",
        "descricao": "Ferramenta de manipulação de PDF",
        "prefixo": "pdf",
        "dependencias": [],
        "volumes": ["stirlingpdf_data"],
        "networks": ["externa"]
    },
    "prometheus": {
        "categoria": "monitoramento",
        "descricao": "Sistema de monitoramento",
        "prefixo": "prometheus",
        "dependencias": [],
        "volumes": ["prometheus_data"],
        "networks": ["interna"],
        "configs": ["config_prometheus"]
    },
    "grafana": {
        "categoria": "monitoramento",
        "descricao": "Dashboard de métricas",
        "prefixo": "grafana",
        "dependencias": ["prometheus"],
        "volumes": ["grafana_data"],
        "networks": ["externa", "interna"]
    },
    "dozzle": {
        "categoria": "monitoramento",
        "descricao": "Visualizador de logs Docker",
        "prefixo": "logs",
        "dependencias": [],
        "volumes": [],
        "networks": ["externa"],
        "configs": ["config_dozzle"]
    }
}

# Perfis de instalação
PERFIS_INSTALACAO = {
    "minimo": {
        "nome": "Mínimo",
        "descricao": "Infraestrutura básica (Traefik + Portainer)",
        "stacks": ["traefik", "portainer"]
    },
    "basico": {
        "nome": "Básico", 
        "descricao": "Mínimo + Bancos de dados",
        "stacks": ["traefik", "portainer", "postgres", "redis"]
    },
    "completo": {
        "nome": "Completo",
        "descricao": "Todas as stacks disponíveis",
        "stacks": list(STACK_CONFIG.keys())
    }
}

class ConfigManager:
    """Gerenciador de configurações do instalador"""
    
    def __init__(self):
        self.config_dir = os.path.join(os.path.dirname(__file__), ".vps_installer")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.portainer_config_file = os.path.join(os.path.dirname(__file__), "portainer_config.json")
        self._ensure_config_dir()
        
    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, mode=0o700)
            
    def load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {}
        
    def save_config(self, config: Dict):
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
    def load_portainer_config(self) -> Optional[Dict]:
        if os.path.exists(self.portainer_config_file):
            with open(self.portainer_config_file, 'r') as f:
                return json.load(f)
        return None
        
    def save_portainer_config(self, username: str, password: str):
        with open(self.portainer_config_file, 'w') as f:
            json.dump({"PORTAINER_USERNAME": username, "PORTAINER_PASSWORD": password}, f)

class DependencyManager:
    """Gerenciador de dependências entre stacks"""
    
    @staticmethod
    def get_all_dependencies(stack_name: str, resolved: Optional[set] = None) -> List[str]:
        if resolved is None:
            resolved = set()
            
        if stack_name in resolved:
            return []
            
        dependencies = []
        stack_info = STACK_CONFIG.get(stack_name, {})
        
        for dep in stack_info.get("dependencias", []):
            dependencies.extend(DependencyManager.get_all_dependencies(dep, resolved))
            
        if stack_name not in resolved:
            dependencies.append(stack_name)
            resolved.add(stack_name)
            
        return dependencies

class DNSConfigGenerator:
    """Gerador de configuração DNS para Cloudflare"""
    
    @staticmethod
    def generate_dns_config(dominio_base: str, stacks: List[str], prefixos_customizados: Dict[str, str]) -> str:
        config_lines = [
            "=" * 60,
            "CONFIGURAÇÃO DNS - CLOUDFLARE",
            "=" * 60,
            f"Domínio Base: {dominio_base}",
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            "",
            "REGISTROS DNS NECESSÁRIOS:",
            "-" * 40,
            f"1. Registro A:",
            f"   Nome: @",
            f"   Conteúdo: [IP_DO_SEU_SERVIDOR]",
            f"   Proxy: Desativado (DNS only)",
            "",
            "2. Registros CNAME:",
        ]
        
        for stack in stacks:
            stack_info = STACK_CONFIG.get(stack, {})
            prefixo = prefixos_customizados.get(stack, stack_info.get("prefixo", stack))
            
            config_lines.append(f"   - Nome: {prefixo}")
            config_lines.append(f"     Conteúdo: @")
            config_lines.append(f"     Proxy: Desativado (DNS only)")
            
            # Adicionar prefixo extra se existir (ex: console.minio)
            if "prefixo_console" in stack_info:
                prefixo_console = prefixos_customizados.get(f"{stack}_console", stack_info["prefixo_console"])
                config_lines.append(f"   - Nome: {prefixo_console}")
                config_lines.append(f"     Conteúdo: @")
                config_lines.append(f"     Proxy: Desativado (DNS only)")
            
            config_lines.append("")
        
        config_lines.extend([
            "-" * 40,
            "URLS DE ACESSO APÓS INSTALAÇÃO:",
            "-" * 40
        ])
        
        for stack in stacks:
            stack_info = STACK_CONFIG.get(stack, {})
            prefixo = prefixos_customizados.get(stack, stack_info.get("prefixo", stack))
            config_lines.append(f"- {stack_info.get('descricao', stack)}: https://{prefixo}.{dominio_base}")
            
            if "prefixo_console" in stack_info:
                prefixo_console = prefixos_customizados.get(f"{stack}_console", stack_info["prefixo_console"])
                config_lines.append(f"  Console: https://{prefixo_console}.{dominio_base}")
        
        config_lines.extend([
            "",
            "=" * 60,
            "IMPORTANTE:",
            "- Aguarde a propagação DNS (até 48h)",
            "- Certificados SSL serão gerados automaticamente",
            "- Mantenha o Proxy do Cloudflare desativado inicialmente",
            "=" * 60
        ])
        
        return "\n".join(config_lines)

class StackCommand(ABC):
    """Classe base para comandos de stack"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        
    @abstractmethod
    def name(self) -> str:
        pass
        
    @abstractmethod
    def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
        pass
        
    def get_required_resources(self) -> Dict[str, List[str]]:
        """Retorna volumes, networks e configs necessários"""
        stack_info = STACK_CONFIG.get(self.name(), {})
        return {
            "volumes": stack_info.get("volumes", []),
            "networks": stack_info.get("networks", []),
            "configs": stack_info.get("configs", [])
        }
        
    def create_resources(self):
        """Cria os recursos necessários para a stack"""
        resources = self.get_required_resources()
        
        # Criar networks
        for network in resources["networks"]:
            self.create_network(network)
            
        # Criar volumes
        for volume in resources["volumes"]:
            self.create_volume(volume)
            
        # Criar configs
        for config in resources["configs"]:
            self.create_config(config)
            
    def create_network(self, nome: str, driver: str = "overlay"):
        result = subprocess.run(["docker", "network", "ls", "--format", "{{.Name}}"], 
                              capture_output=True, text=True)
        if nome not in result.stdout.split():
            subprocess.run(["docker", "network", "create", "--driver", driver, nome], check=True)
            print(f"[+] Network '{nome}' criada")
        else:
            print(f"[i] Network '{nome}' já existe")
            
    def create_volume(self, nome: str):
        result = subprocess.run(["docker", "volume", "ls", "--format", "{{.Name}}"], 
                              capture_output=True, text=True)
        if nome not in result.stdout.split():
            subprocess.run(["docker", "volume", "create", nome], check=True)
            print(f"[+] Volume '{nome}' criado")
        else:
            print(f"[i] Volume '{nome}' já existe")
            
    def create_config(self, nome: str):
        config_path = os.path.join(os.path.dirname(__file__), "stacks", "configs", nome)
        if os.path.exists(config_path):
            result = subprocess.run(["docker", "config", "ls", "--format", "{{.Name}}"], 
                                  capture_output=True, text=True)
            if nome not in result.stdout.split():
                subprocess.run(["docker", "config", "create", nome, config_path], check=True)
                print(f"[+] Config '{nome}' criada")
            else:
                print(f"[i] Config '{nome}' já existe")
                
    def deploy_via_cli(self, yaml_content: str):
        """Deploy usando Docker CLI"""
        yaml_file = f"{self.name()}.yaml"
        with open(yaml_file, 'w') as f:
            f.write(yaml_content)
        subprocess.run(["docker", "stack", "deploy", "-c", yaml_file, self.name()], check=True)
        print(f"[OK] Stack '{self.name()}' deployada via Docker CLI")
        
    def deploy_via_portainer(self, yaml_content: str, portainer_url: str, username: str, password: str):
        """Deploy usando Portainer API"""
        try:
            # Autenticar
            resp = requests.post(
                f"{portainer_url}/api/auth",
                json={"Username": username, "Password": password},
                verify=False
            )
            resp.raise_for_status()
            jwt = resp.json()["jwt"]
            
            # Headers
            headers = {"Authorization": f"Bearer {jwt}"}
            
            # Obter endpoint ID
            endpoints_resp = requests.get(f"{portainer_url}/api/endpoints", headers=headers, verify=False)
            endpoints_resp.raise_for_status()
            endpoint_id = endpoints_resp.json()[0]["Id"] if endpoints_resp.json() else 1
            
            # Criar stack
            payload = {
                "Name": self.name(),
                "StackFileContent": yaml_content,
                "Env": []
            }
            
            stack_resp = requests.post(
                f"{portainer_url}/api/stacks?type=1&method=string&endpointId={endpoint_id}",
                headers=headers,
                json=payload,
                verify=False
            )
            stack_resp.raise_for_status()
            print(f"[OK] Stack '{self.name()}' deployada via Portainer API")
            
        except Exception as e:
            print(f"[!] Erro ao deployar via Portainer, tentando via CLI: {str(e)}")
            self.deploy_via_cli(yaml_content)

# Implementação das stacks específicas
class TraefikStack(StackCommand):
    def name(self) -> str:
        return "traefik"
        
    def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
        config = self.config_manager.load_config()
        le_email = config.get("le_email", "admin@" + dominio_base)
        cf_email = config.get("cf_email", "")
        cf_api_key = config.get("cf_api_key", "")
        prefixo = prefixos.get("traefik", "traefik")
        
        return f'''version: "3.8"

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
      - --certificatesresolvers.le.acme.email={le_email}
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
      - --certificatesresolvers.le.acme.tlschallenge=true
      - --certificatesresolvers.le.acme.httpchallenge.entrypoint=web
      {"- --certificatesresolvers.le.acme.dnschallenge=true" if cf_email and cf_api_key else ""}
      {"- --certificatesresolvers.le.acme.dnschallenge.provider=cloudflare" if cf_email and cf_api_key else ""}
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
      CF_API_EMAIL: "{cf_email}"
      CF_API_KEY: "{cf_api_key}"
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
        - traefik.http.routers.traefik.rule=Host(`{prefixo}.{dominio_base}`)
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
'''

class PortainerStack(StackCommand):
    def name(self) -> str:
        return "portainer"
        
    def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
        prefixo = prefixos.get("portainer", "portainer")
        
        return f'''version: "3.8"

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
        - traefik.http.routers.portainer.rule=Host(`{prefixo}.{dominio_base}`)
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
'''

class PostgresStack(StackCommand):
    def name(self) -> str:
        return "postgres"
        
    def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
        config = self.config_manager.load_config()
        postgres_password = config.get("postgres_password", self.generate_password())
        prefixo = prefixos.get("postgres", "pgadmin")
        
        return f'''version: "3.8"

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: {postgres_password}
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
      PGADMIN_DEFAULT_EMAIL: admin@{dominio_base}
      PGADMIN_DEFAULT_PASSWORD: {postgres_password}
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
        - traefik.http.routers.pgadmin.rule=Host(`{prefixo}.{dominio_base}`)
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
'''
    
    def generate_password(self) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

# Implementações das outras stacks seguem o mesmo padrão...
# Por brevidade, vou adicionar apenas mais algumas como exemplo

class RedisStack(StackCommand):
    def name(self) -> str:
        return "redis"
        
    def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
        config = self.config_manager.load_config()
        redis_password = config.get("redis_password", self.generate_password())
        prefixo = prefixos.get("redis", "redis")
        
        return f'''version: "3.8"

services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass {redis_password} --appendonly yes
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
      REDIS_HOSTS: local:redis:6379:0:{redis_password}
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.redis-commander.rule=Host(`{prefixo}.{dominio_base}`)
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
'''
    
    def generate_password(self) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

# Mapeamento de stacks para suas classes
STACK_CLASSES = {
    "traefik": TraefikStack,
    "portainer": PortainerStack,
    "postgres": PostgresStack,
    "redis": RedisStack,
}

# Importar implementações adicionais de todas as stacks
try:
    from stack_implementations import create_stack_implementations
    additional_stacks = create_stack_implementations(StackCommand)
    STACK_CLASSES.update(additional_stacks)
except ImportError:
    # Se o arquivo não existir, usar apenas as implementações básicas
    pass

class VPSInstaller:
    """Classe principal do instalador"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.dependency_manager = DependencyManager()
        self.dns_generator = DNSConfigGenerator()
        
    def print_header(self):
        print("=" * 60)
        print("INSTALADOR VPS - SISTEMA MELHORADO")
        print("=" * 60)
        
    def print_menu(self):
        print("\n1. Instalar Docker e Docker Compose")
        print("2. Inicializar Swarm")
        print("3. Instalação Rápida (Perfis)")
        print("4. Instalação Personalizada")
        print("5. Gerenciar Stacks Instaladas")
        print("6. Configurações")
        print("7. Sair")
        
    def run(self):
        while True:
            self.print_header()
            self.print_menu()
            
            choice = input("\nEscolha uma opção: ")
            
            if choice == '1':
                self.instalar_docker()
            elif choice == '2':
                self.inicializar_swarm()
            elif choice == '3':
                self.instalacao_rapida()
            elif choice == '4':
                self.instalacao_personalizada()
            elif choice == '5':
                self.gerenciar_stacks()
            elif choice == '6':
                self.configuracoes()
            elif choice == '7':
                print("Saindo...")
                sys.exit(0)
            else:
                print("Opção inválida!")
                
    def instalar_docker(self):
        print("\n[+] Instalando Docker...")
        try:
            subprocess.run("curl -fsSL https://get.docker.com | sh", shell=True, check=True)
            subprocess.run(["systemctl", "enable", "docker"])
            subprocess.run(["systemctl", "start", "docker"])
            print("[OK] Docker instalado com sucesso!")
        except Exception as e:
            print(f"[ERRO] Falha ao instalar Docker: {e}")
            
    def inicializar_swarm(self):
        print("\n[+] Inicializando Docker Swarm...")
        try:
            # Obter IP do servidor
            result = subprocess.run(
                ["hostname", "-I"], 
                capture_output=True, 
                text=True
            )
            server_ip = result.stdout.strip().split()[0]
            
            subprocess.run(
                ["docker", "swarm", "init", "--advertise-addr", server_ip], 
                check=True
            )
            print(f"[OK] Swarm inicializado com IP: {server_ip}")
        except Exception as e:
            print(f"[ERRO] Falha ao inicializar Swarm: {e}")
            
    def instalacao_rapida(self):
        print("\n=== INSTALAÇÃO RÁPIDA ===")
        print("\nPerfis disponíveis:")
        
        for key, perfil in PERFIS_INSTALACAO.items():
            print(f"\n{key}: {perfil['nome']}")
            print(f"   {perfil['descricao']}")
            print(f"   Stacks: {', '.join(perfil['stacks'])}")
            
        perfil_escolhido = input("\nEscolha um perfil (minimo/basico/completo): ").lower()
        
        if perfil_escolhido not in PERFIS_INSTALACAO:
            print("Perfil inválido!")
            return
            
        stacks = PERFIS_INSTALACAO[perfil_escolhido]["stacks"]
        self._executar_instalacao(stacks)
        
    def instalacao_personalizada(self):
        print("\n=== INSTALAÇÃO PERSONALIZADA ===")
        
        # Organizar stacks por categoria
        categorias = {
            "infraestrutura": [],
            "banco_dados": [],
            "aplicacao": [],
            "monitoramento": []
        }
        
        for stack, info in STACK_CONFIG.items():
            categoria = info.get("categoria", "aplicacao")
            categorias[categoria].append(stack)
            
        # Mostrar stacks por categoria
        stacks_selecionadas = []
        
        for categoria, stacks in categorias.items():
            print(f"\n--- {categoria.upper().replace('_', ' ')} ---")
            for stack in stacks:
                info = STACK_CONFIG[stack]
                print(f"{stack}: {info['descricao']}")
                
            selecionadas = input(f"\nSelecione stacks de {categoria} (separadas por vírgula, ou 'todas'): ")
            
            if selecionadas.lower() == 'todas':
                stacks_selecionadas.extend(stacks)
            elif selecionadas:
                for s in selecionadas.split(','):
                    s = s.strip()
                    if s in stacks:
                        stacks_selecionadas.append(s)
                        
        if stacks_selecionadas:
            self._executar_instalacao(stacks_selecionadas)
        else:
            print("Nenhuma stack selecionada!")
            
    def _executar_instalacao(self, stacks_selecionadas: List[str]):
        # Resolver dependências
        stacks_com_deps = []
        for stack in stacks_selecionadas:
            deps = self.dependency_manager.get_all_dependencies(stack)
            for dep in deps:
                if dep not in stacks_com_deps:
                    stacks_com_deps.append(dep)
                    
        print(f"\n[INFO] Stacks a serem instaladas (com dependências): {', '.join(stacks_com_deps)}")
        
        # Obter domínio base
        dominio_base = input("\nDigite o domínio base (ex: exemplo.com.br): ").strip()
        while not dominio_base:
            dominio_base = input("Domínio base não pode ser vazio: ").strip()
            
        # Perguntar sobre prefixos customizados
        prefixos = {}
        customizar = input("\nDeseja customizar os prefixos de domínio? (s/N): ").lower() == 's'
        
        if customizar:
            print("\nPrefixos padrão:")
            for stack in stacks_com_deps:
                info = STACK_CONFIG.get(stack, {})
                prefixo_padrao = info.get("prefixo", stack)
                print(f"- {stack}: {prefixo_padrao}.{dominio_base}")
                
                novo_prefixo = input(f"Novo prefixo para {stack} (Enter para manter '{prefixo_padrao}'): ").strip()
                if novo_prefixo:
                    prefixos[stack] = novo_prefixo
                else:
                    prefixos[stack] = prefixo_padrao
                    
                # Se tiver console adicional (como MinIO)
                if "prefixo_console" in info:
                    prefixo_console_padrao = info["prefixo_console"]
                    print(f"- {stack} console: {prefixo_console_padrao}.{dominio_base}")
                    novo_prefixo_console = input(f"Novo prefixo para console (Enter para '{prefixo_console_padrao}'): ").strip()
                    if novo_prefixo_console:
                        prefixos[f"{stack}_console"] = novo_prefixo_console
                    else:
                        prefixos[f"{stack}_console"] = prefixo_console_padrao
        else:
            # Usar prefixos padrão
            for stack in stacks_com_deps:
                info = STACK_CONFIG.get(stack, {})
                prefixos[stack] = info.get("prefixo", stack)
                if "prefixo_console" in info:
                    prefixos[f"{stack}_console"] = info["prefixo_console"]
                    
        # Gerar e mostrar configuração DNS
        dns_config = self.dns_generator.generate_dns_config(dominio_base, stacks_com_deps, prefixos)
        
        print("\n" + dns_config)
        
        # Salvar configuração DNS em arquivo
        dns_file = f"dns_config_{dominio_base.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(dns_file, 'w') as f:
            f.write(dns_config)
        print(f"\n[INFO] Configuração DNS salva em: {dns_file}")
        
        input("\nPressione Enter após configurar o DNS no Cloudflare...")
        
        # Coletar informações adicionais necessárias
        config = self.config_manager.load_config()
        
        if "traefik" in stacks_com_deps:
            config["le_email"] = input("\nE-mail para Let's Encrypt: ").strip()
            config["cf_email"] = input("E-mail do Cloudflare (opcional): ").strip()
            config["cf_api_key"] = input("API Key do Cloudflare (opcional): ").strip()
            
        # Gerar senhas para serviços
        if "postgres" in stacks_com_deps and "postgres_password" not in config:
            config["postgres_password"] = self._generate_password()
            print(f"[INFO] Senha PostgreSQL gerada: {config['postgres_password']}")
            
        if "redis" in stacks_com_deps and "redis_password" not in config:
            config["redis_password"] = self._generate_password()
            print(f"[INFO] Senha Redis gerada: {config['redis_password']}")
            
        if "pgvector" in stacks_com_deps and "pgvector_password" not in config:
            config["pgvector_password"] = self._generate_password()
            print(f"[INFO] Senha PGVector gerada: {config['pgvector_password']}")
            
        if "rabbitmq" in stacks_com_deps and "rabbitmq_password" not in config:
            config["rabbitmq_user"] = "admin"
            config["rabbitmq_password"] = self._generate_password()
            print(f"[INFO] Credenciais RabbitMQ - Usuário: admin, Senha: {config['rabbitmq_password']}")
            
        if "minio" in stacks_com_deps and "minio_root_password" not in config:
            config["minio_root_user"] = "minioadmin"
            config["minio_root_password"] = self._generate_password()
            print(f"[INFO] Credenciais MinIO - Usuário: minioadmin, Senha: {config['minio_root_password']}")
            
        if "grafana" in stacks_com_deps and "grafana_password" not in config:
            config["grafana_password"] = self._generate_password()
            print(f"[INFO] Senha Grafana (admin): {config['grafana_password']}")
            
        if "dozzle" in stacks_com_deps and "dozzle_password" not in config:
            config["dozzle_password"] = self._generate_password()
            print(f"[INFO] Senha Dozzle (admin): {config['dozzle_password']}")
            
        if "evolution" in stacks_com_deps and "evolution_api_key" not in config:
            config["evolution_api_key"] = self._generate_password(32)
            print(f"[INFO] Evolution API Key: {config['evolution_api_key']}")
            
        if "chatwoot" in stacks_com_deps and "chatwoot_secret_key" not in config:
            config["chatwoot_secret_key"] = self._generate_password(64)
            
        if "directus" in stacks_com_deps:
            if "directus_key" not in config:
                config["directus_key"] = self._generate_password(32)
            if "directus_secret" not in config:
                config["directus_secret"] = self._generate_password(32)
                print(f"[INFO] Credenciais Directus - Admin: admin@{dominio_base}, Senha: {config['directus_secret'][:16]}")
            
        self.config_manager.save_config(config)
        
        # Instalar Portainer primeiro se estiver na lista
        if "portainer" in stacks_com_deps:
            self._instalar_portainer(dominio_base, prefixos)
            stacks_com_deps.remove("portainer")
            
        # Instalar as demais stacks
        portainer_config = self.config_manager.load_portainer_config()
        use_portainer = portainer_config is not None
        
        for stack in stacks_com_deps:
            print(f"\n[+] Instalando {stack}...")
            try:
                self._instalar_stack(stack, dominio_base, prefixos, use_portainer)
                print(f"[OK] {stack} instalada com sucesso!")
            except Exception as e:
                print(f"[ERRO] Falha ao instalar {stack}: {e}")
                
        # Mostrar resumo final
        print("\n" + "=" * 60)
        print("INSTALAÇÃO CONCLUÍDA!")
        print("=" * 60)
        print(f"\nArquivo de configuração DNS: {dns_file}")
        print("\nAcesse os serviços pelos URLs listados acima.")
        print("Aguarde alguns minutos para os certificados SSL serem gerados.")
        
    def _instalar_portainer(self, dominio_base: str, prefixos: Dict[str, str]):
        print("\n[+] Instalando Portainer...")
        
        # Verificar se já existe
        portainer_config = self.config_manager.load_portainer_config()
        
        if not portainer_config:
            username = input("Usuário admin do Portainer: ").strip()
            while not username:
                username = input("Usuário não pode ser vazio: ").strip()
                
            password = self._generate_password()
            self.config_manager.save_portainer_config(username, password)
            
            print(f"[INFO] Credenciais Portainer:")
            print(f"  Usuário: {username}")
            print(f"  Senha: {password}")
        else:
            username = portainer_config["PORTAINER_USERNAME"]
            password = portainer_config["PORTAINER_PASSWORD"]
            print("[INFO] Usando credenciais Portainer existentes")
            
        # Instalar stack
        stack_class = PortainerStack(self.config_manager)
        stack_class.create_resources()
        yaml_content = stack_class.generate_yaml(dominio_base, prefixos)
        stack_class.deploy_via_cli(yaml_content)
        
        # Aguardar Portainer iniciar
        print("[INFO] Aguardando Portainer iniciar...")
        portainer_url = "https://localhost:9443"
        
        for i in range(30):
            try:
                resp = requests.get(f"{portainer_url}/api/status", verify=False, timeout=2)
                if resp.status_code == 200:
                    print("[OK] Portainer está pronto!")
                    
                    # Configurar admin na primeira execução
                    if not portainer_config:
                        self._configurar_portainer_admin(portainer_url, username, password)
                    break
            except:
                time.sleep(2)
        else:
            print("[AVISO] Portainer pode não estar totalmente inicializado")
            
    def _configurar_portainer_admin(self, portainer_url: str, username: str, password: str):
        """Configura o usuário admin do Portainer na primeira execução"""
        try:
            # Criar usuário admin
            resp = requests.post(
                f"{portainer_url}/api/users/admin/init",
                json={"Username": username, "Password": password},
                verify=False
            )
            if resp.status_code == 200:
                print("[OK] Usuário admin do Portainer configurado")
        except Exception as e:
            print(f"[AVISO] Não foi possível configurar admin automaticamente: {e}")
            
    def _instalar_stack(self, stack_name: str, dominio_base: str, prefixos: Dict[str, str], use_portainer: bool):
        # Obter classe da stack
        stack_class = STACK_CLASSES.get(stack_name)
        
        if not stack_class:
            print(f"[AVISO] Stack {stack_name} ainda não implementada")
            return
            
        # Criar instância e recursos
        stack = stack_class(self.config_manager)
        stack.create_resources()
        
        # Gerar YAML
        yaml_content = stack.generate_yaml(dominio_base, prefixos)
        
        # Deploy
        if use_portainer:
            portainer_config = self.config_manager.load_portainer_config()
            stack.deploy_via_portainer(
                yaml_content,
                "https://localhost:9443",
                portainer_config["PORTAINER_USERNAME"],
                portainer_config["PORTAINER_PASSWORD"]
            )
        else:
            stack.deploy_via_cli(yaml_content)
            
        # Verificar status após deploy
        print(f"[INFO] Verificando status de {stack_name}...")
        if self._verificar_status_stack(stack_name):
            print(f"[OK] {stack_name} está funcionando corretamente")
        else:
            print(f"[AVISO] {stack_name} pode estar com problemas. Verifique os logs.")
            
    def gerenciar_stacks(self):
        print("\n=== GERENCIAR STACKS ===")
        
        # Listar stacks instaladas
        result = subprocess.run(
            ["docker", "stack", "ls", "--format", "table {{.Name}}\t{{.Services}}"],
            capture_output=True,
            text=True
        )
        
        print("\nStacks instaladas:")
        print(result.stdout)
        
        print("\n1. Remover stack")
        print("2. Ver logs de uma stack")
        print("3. Voltar")
        
        choice = input("\nEscolha uma opção: ")
        
        if choice == '1':
            stack_name = input("Nome da stack para remover: ").strip()
            if stack_name:
                subprocess.run(["docker", "stack", "rm", stack_name])
                print(f"[OK] Stack {stack_name} removida")
        elif choice == '2':
            stack_name = input("Nome da stack para ver logs: ").strip()
            if stack_name:
                subprocess.run(["docker", "stack", "services", stack_name])
                service = input("Nome do serviço: ").strip()
                if service:
                    subprocess.run(["docker", "service", "logs", f"{stack_name}_{service}", "-f"])
                    
    def configuracoes(self):
        print("\n=== CONFIGURAÇÕES ===")
        
        config = self.config_manager.load_config()
        
        print("\n1. Configurar Cloudflare")
        print("2. Alterar senhas dos serviços")
        print("3. Exportar configuração")
        print("4. Importar configuração")
        print("5. Voltar")
        
        choice = input("\nEscolha uma opção: ")
        
        if choice == '1':
            config["cf_email"] = input("E-mail do Cloudflare: ").strip()
            config["cf_api_key"] = input("API Key do Cloudflare: ").strip()
            self.config_manager.save_config(config)
            print("[OK] Configuração do Cloudflare salva")
            
        elif choice == '2':
            print("\nServiços disponíveis:")
            if "postgres_password" in config:
                print("1. PostgreSQL")
            if "redis_password" in config:
                print("2. Redis")
                
            service = input("\nEscolha o serviço: ")
            
            if service == '1' and "postgres_password" in config:
                config["postgres_password"] = input("Nova senha PostgreSQL: ").strip()
            elif service == '2' and "redis_password" in config:
                config["redis_password"] = input("Nova senha Redis: ").strip()
                
            self.config_manager.save_config(config)
            print("[OK] Senha atualizada (necessário redeployar a stack)")
            
        elif choice == '3':
            export_file = f"vps_config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(export_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"[OK] Configuração exportada para: {export_file}")
            
        elif choice == '4':
            import_file = input("Caminho do arquivo de configuração: ").strip()
            try:
                with open(import_file, 'r') as f:
                    imported_config = json.load(f)
                config.update(imported_config)
                self.config_manager.save_config(config)
                print("[OK] Configuração importada com sucesso")
            except Exception as e:
                print(f"[ERRO] Falha ao importar: {e}")
                
    def _verificar_status_stack(self, stack_name: str, timeout: int = 30) -> bool:
        """Verifica se todos os serviços de uma stack estão rodando"""
        import time
        
        for i in range(timeout):
            try:
                # Obter serviços da stack
                result = subprocess.run(
                    ["docker", "stack", "services", stack_name, "--format", "{{.Replicas}}"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    time.sleep(1)
                    continue
                    
                # Verificar se todos os serviços têm replicas rodando
                all_running = True
                for line in result.stdout.strip().split('\n'):
                    if line and '/' in line:
                        running, total = line.split('/')
                        if running != total or running == '0':
                            all_running = False
                            break
                            
                if all_running and result.stdout.strip():
                    return True
                    
            except Exception:
                pass
                
            time.sleep(1)
            
        return False
        
    def _generate_password(self, length: int = 16) -> str:
        return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

def main():
    # Verificar se está rodando como root
    if os.geteuid() != 0:
        print("Este script precisa ser executado como root!")
        sys.exit(1)
        
    installer = VPSInstaller()
    installer.run()

if __name__ == "__main__":
    main()