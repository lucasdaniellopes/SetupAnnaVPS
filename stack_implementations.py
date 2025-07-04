"""
Implementações de todas as stacks disponíveis
"""
from typing import Dict
import secrets
import string

def create_stack_implementations(StackCommand):
    """Factory function para criar as implementações de stacks"""
    
    class PGVectorStack(StackCommand):
        def name(self) -> str:
            return "pgvector"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            pgvector_password = config.get("pgvector_password", self.generate_password())
            prefixo = prefixos.get("pgvector", "pgvector")
            
            return f'''version: "3.8"

services:
  pgvector:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: {pgvector_password}
      POSTGRES_DB: pgvector
    volumes:
      - pgvector_data:/var/lib/postgresql/data
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager

  pgvector-admin:
    image: sosedoff/pgweb:latest
    environment:
      DATABASE_URL: postgres://postgres:{pgvector_password}@pgvector:5432/pgvector?sslmode=disable
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.pgvector.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.pgvector.entrypoints=websecure
        - traefik.http.routers.pgvector.tls.certresolver=le
        - traefik.http.services.pgvector.loadbalancer.server.port=8081

volumes:
  pgvector_data:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    class PGBouncerStack(StackCommand):
        def name(self) -> str:
            return "pgbouncer"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            postgres_password = config.get("postgres_password", "")
            prefixo = prefixos.get("pgbouncer", "pgbouncer")
            
            return f'''version: "3.8"

services:
  pgbouncer:
    image: edoburu/pgbouncer:latest
    environment:
      DATABASES_HOST: postgres
      DATABASES_PORT: 5432
      DATABASES_USER: postgres
      DATABASES_PASSWORD: {postgres_password}
      DATABASES_DBNAME: postgres
      POOL_MODE: session
      MAX_CLIENT_CONN: 1000
      DEFAULT_POOL_SIZE: 25
      ADMIN_USERS: postgres
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.pgbouncer.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.pgbouncer.entrypoints=websecure
        - traefik.http.routers.pgbouncer.tls.certresolver=le
        - traefik.http.services.pgbouncer.loadbalancer.server.port=6432

networks:
  externa:
    external: true
  interna:
    external: true
'''

    class EvolutionStack(StackCommand):
        def name(self) -> str:
            return "evolution"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            postgres_password = config.get("postgres_password", "")
            redis_password = config.get("redis_password", "")
            evolution_api_key = config.get("evolution_api_key", self.generate_password())
            prefixo = prefixos.get("evolution", "evolution")
            
            return f'''version: "3.8"

services:
  evolution:
    image: atendai/evolutionapi:latest
    environment:
      DATABASE_ENABLED: "true"
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: postgresql://postgres:{postgres_password}@postgres:5432/evolution
      DATABASE_CONNECTION_CLIENT_NAME: evolution_client
      CACHE_REDIS_ENABLED: "true"
      CACHE_REDIS_URI: redis://:{redis_password}@redis:6379/1
      CACHE_REDIS_PREFIX_KEY: evolution
      AUTHENTICATION_API_KEY: {evolution_api_key}
      AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "true"
      INSTANCE_WEBHOOK_URL: ""
      INSTANCE_CHATWOOT_ACCOUNT_ID: ""
      INSTANCE_CHATWOOT_TOKEN: ""
      INSTANCE_CHATWOOT_URL: ""
      INSTANCE_CHATWOOT_SIGN_MSG: "false"
    volumes:
      - evolution_instances:/app/instances
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.evolution.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.evolution.entrypoints=websecure
        - traefik.http.routers.evolution.tls.certresolver=le
        - traefik.http.services.evolution.loadbalancer.server.port=8080

volumes:
  evolution_instances:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    class ChatwootStack(StackCommand):
        def name(self) -> str:
            return "chatwoot"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            postgres_password = config.get("postgres_password", "")
            redis_password = config.get("redis_password", "")
            secret_key = config.get("chatwoot_secret_key", self.generate_password())
            prefixo = prefixos.get("chatwoot", "chatwoot")
            
            return f'''version: "3.8"

services:
  chatwoot-web:
    image: chatwoot/chatwoot:latest
    command: bundle exec rails s -b 0.0.0.0 -p 3000
    environment:
      RAILS_ENV: production
      SECRET_KEY_BASE: {secret_key}
      DATABASE_URL: postgres://postgres:{postgres_password}@postgres:5432/chatwoot
      REDIS_URL: redis://:{redis_password}@redis:6379/0
      REDIS_PASSWORD: {redis_password}
      FRONTEND_URL: https://{prefixo}.{dominio_base}
      DEFAULT_LOCALE: pt_BR
      FORCE_SSL: "true"
      ENABLE_ACCOUNT_SIGNUP: "false"
      MAILER_SENDER_EMAIL: noreply@{dominio_base}
    volumes:
      - chatwoot_storage:/app/storage
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.chatwoot.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.chatwoot.entrypoints=websecure
        - traefik.http.routers.chatwoot.tls.certresolver=le
        - traefik.http.services.chatwoot.loadbalancer.server.port=3000

  chatwoot-worker:
    image: chatwoot/chatwoot:latest
    command: bundle exec sidekiq -C config/sidekiq.yml
    environment:
      RAILS_ENV: production
      SECRET_KEY_BASE: {secret_key}
      DATABASE_URL: postgres://postgres:{postgres_password}@postgres:5432/chatwoot
      REDIS_URL: redis://:{redis_password}@redis:6379/0
      REDIS_PASSWORD: {redis_password}
      FRONTEND_URL: https://{prefixo}.{dominio_base}
      DEFAULT_LOCALE: pt_BR
      MAILER_SENDER_EMAIL: noreply@{dominio_base}
    volumes:
      - chatwoot_storage:/app/storage
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager

volumes:
  chatwoot_storage:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(64))

    class DirectusStack(StackCommand):
        def name(self) -> str:
            return "directus"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            postgres_password = config.get("postgres_password", "")
            redis_password = config.get("redis_password", "")
            directus_key = config.get("directus_key", self.generate_password())
            directus_secret = config.get("directus_secret", self.generate_password())
            prefixo = prefixos.get("directus", "directus")
            
            return f'''version: "3.8"

services:
  directus:
    image: directus/directus:latest
    environment:
      KEY: {directus_key}
      SECRET: {directus_secret}
      ADMIN_EMAIL: admin@{dominio_base}
      ADMIN_PASSWORD: {directus_secret[:16]}
      DB_CLIENT: postgres
      DB_HOST: postgres
      DB_PORT: 5432
      DB_DATABASE: directus
      DB_USER: postgres
      DB_PASSWORD: {postgres_password}
      CACHE_ENABLED: "true"
      CACHE_STORE: redis
      CACHE_REDIS: redis://:{redis_password}@redis:6379/2
      PUBLIC_URL: https://{prefixo}.{dominio_base}
      STORAGE_LOCATIONS: local
      STORAGE_LOCAL_DRIVER: local
      STORAGE_LOCAL_ROOT: ./uploads
    volumes:
      - directus_uploads:/directus/uploads
      - directus_extensions:/directus/extensions
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.directus.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.directus.entrypoints=websecure
        - traefik.http.routers.directus.tls.certresolver=le
        - traefik.http.services.directus.loadbalancer.server.port=8055

volumes:
  directus_uploads:
    external: true
  directus_extensions:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

    class MinIOStack(StackCommand):
        def name(self) -> str:
            return "minio"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            minio_root_user = config.get("minio_root_user", "minioadmin")
            minio_root_password = config.get("minio_root_password", self.generate_password())
            prefixo = prefixos.get("minio", "minio")
            prefixo_console = prefixos.get("minio_console", "console.minio")
            
            return f'''version: "3.8"

services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: {minio_root_user}
      MINIO_ROOT_PASSWORD: {minio_root_password}
      MINIO_BROWSER_REDIRECT_URL: https://{prefixo_console}.{dominio_base}
      MINIO_SERVER_URL: https://{prefixo}.{dominio_base}
    volumes:
      - minio_data:/data
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        # API
        - traefik.http.routers.minio-api.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.minio-api.entrypoints=websecure
        - traefik.http.routers.minio-api.tls.certresolver=le
        - traefik.http.routers.minio-api.service=minio-api
        - traefik.http.services.minio-api.loadbalancer.server.port=9000
        # Console
        - traefik.http.routers.minio-console.rule=Host(`{prefixo_console}.{dominio_base}`)
        - traefik.http.routers.minio-console.entrypoints=websecure
        - traefik.http.routers.minio-console.tls.certresolver=le
        - traefik.http.routers.minio-console.service=minio-console
        - traefik.http.services.minio-console.loadbalancer.server.port=9001

volumes:
  minio_data:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    class RabbitMQStack(StackCommand):
        def name(self) -> str:
            return "rabbitmq"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            rabbitmq_user = config.get("rabbitmq_user", "admin")
            rabbitmq_password = config.get("rabbitmq_password", self.generate_password())
            prefixo = prefixos.get("rabbitmq", "rabbitmq")
            
            return f'''version: "3.8"

services:
  rabbitmq:
    image: rabbitmq:3-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: {rabbitmq_user}
      RABBITMQ_DEFAULT_PASS: {rabbitmq_password}
      RABBITMQ_DEFAULT_VHOST: /
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.rabbitmq.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.rabbitmq.entrypoints=websecure
        - traefik.http.routers.rabbitmq.tls.certresolver=le
        - traefik.http.services.rabbitmq.loadbalancer.server.port=15672

volumes:
  rabbitmq_data:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    class StirlingPDFStack(StackCommand):
        def name(self) -> str:
            return "stirlingpdf"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            prefixo = prefixos.get("stirlingpdf", "pdf")
            
            return f'''version: "3.8"

services:
  stirlingpdf:
    image: frooodle/s-pdf:latest
    environment:
      DOCKER_ENABLE_SECURITY: "false"
      INSTALL_BOOK_AND_ADVANCED_HTML_OPS: "true"
      LANGS: pt_BR,en_US
    volumes:
      - stirlingpdf_data:/usr/share/tessdata
      - stirlingpdf_configs:/configs
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
        - traefik.http.routers.stirlingpdf.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.stirlingpdf.entrypoints=websecure
        - traefik.http.routers.stirlingpdf.tls.certresolver=le
        - traefik.http.services.stirlingpdf.loadbalancer.server.port=8080

volumes:
  stirlingpdf_data:
    external: true
  stirlingpdf_configs:

networks:
  externa:
    external: true
'''

    class PrometheusStack(StackCommand):
        def name(self) -> str:
            return "prometheus"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            prefixo = prefixos.get("prometheus", "prometheus")
            
            return f'''version: "3.8"

services:
  prometheus:
    image: prom/prometheus:latest
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --web.console.libraries=/usr/share/prometheus/console_libraries
      - --web.console.templates=/usr/share/prometheus/consoles
      - --web.external-url=https://{prefixo}.{dominio_base}
      - --web.route-prefix=/
    volumes:
      - prometheus_data:/prometheus
    configs:
      - source: config_prometheus
        target: /etc/prometheus/prometheus.yml
    networks:
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.prometheus.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.prometheus.entrypoints=websecure
        - traefik.http.routers.prometheus.tls.certresolver=le
        - traefik.http.services.prometheus.loadbalancer.server.port=9090

  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - --path.procfs=/host/proc
      - --path.sysfs=/host/sys
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
    networks:
      - interna
    deploy:
      mode: global

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    networks:
      - interna
    deploy:
      mode: global

volumes:
  prometheus_data:
    external: true

configs:
  config_prometheus:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''

    class GrafanaStack(StackCommand):
        def name(self) -> str:
            return "grafana"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            grafana_password = config.get("grafana_password", self.generate_password())
            prefixo = prefixos.get("grafana", "grafana")
            
            return f'''version: "3.8"

services:
  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: {grafana_password}
      GF_SERVER_ROOT_URL: https://{prefixo}.{dominio_base}
      GF_SERVER_DOMAIN: {prefixo}.{dominio_base}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - externa
      - interna
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      labels:
        - traefik.enable=true
        - traefik.docker.network=externa
        - traefik.http.routers.grafana.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.grafana.entrypoints=websecure
        - traefik.http.routers.grafana.tls.certresolver=le
        - traefik.http.services.grafana.loadbalancer.server.port=3000

volumes:
  grafana_data:
    external: true

networks:
  externa:
    external: true
  interna:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    class DozzleStack(StackCommand):
        def name(self) -> str:
            return "dozzle"
            
        def generate_yaml(self, dominio_base: str, prefixos: Dict[str, str]) -> str:
            config = self.config_manager.load_config()
            dozzle_password = config.get("dozzle_password", self.generate_password())
            prefixo = prefixos.get("dozzle", "logs")
            
            return f'''version: "3.8"

services:
  dozzle:
    image: amir20/dozzle:latest
    environment:
      DOZZLE_AUTH_PROVIDER: simple
      DOZZLE_USERNAME: admin
      DOZZLE_PASSWORD: {dozzle_password}
      DOZZLE_KEY: {self.generate_password()[:16]}
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    configs:
      - source: config_dozzle
        target: /data/users.yml
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
        - traefik.http.routers.dozzle.rule=Host(`{prefixo}.{dominio_base}`)
        - traefik.http.routers.dozzle.entrypoints=websecure
        - traefik.http.routers.dozzle.tls.certresolver=le
        - traefik.http.services.dozzle.loadbalancer.server.port=8080

configs:
  config_dozzle:
    external: true

networks:
  externa:
    external: true
'''
        
        def generate_password(self) -> str:
            return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))

    # Retornar dicionário com todas as implementações
    return {
        "pgvector": PGVectorStack,
        "pgbouncer": PGBouncerStack,
        "evolution": EvolutionStack,
        "chatwoot": ChatwootStack,
        "directus": DirectusStack,
        "minio": MinIOStack,
        "rabbitmq": RabbitMQStack,
        "stirlingpdf": StirlingPDFStack,
        "prometheus": PrometheusStack,
        "grafana": GrafanaStack,
        "dozzle": DozzleStack
    }