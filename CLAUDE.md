# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a VPS infrastructure installer that automates the deployment of Docker Swarm clusters with pre-configured application stacks. The project provides both interactive (Python) and automated (Bash) installation methods.

## Key Commands

### Running the Installer
```bash
# Method 1: Direct Python execution (with all features)
sudo python3 instalador_vps.py

# Method 2: Bootstrap script (downloads and runs installer)
curl -fsSL https://raw.githubusercontent.com/lucasdaniellopes/SetupAnnaVPS/main/bootstrap.sh | sudo bash

# Method 3: Original deploy stacks script
sudo bash deploy_stacks.sh

# Method 4: Enhanced deploy script with all features
sudo bash deploy_stacks_v2.sh
```

### Common Development Commands
```bash
# Check Docker status
docker ps
docker stack ls
docker service ls

# View stack configuration
docker stack ps [stack_name]
docker service logs [service_name]

# Remove a stack
docker stack rm [stack_name]

# Test Portainer API connection
curl -k https://localhost:9443/api/auth
```

## Architecture

### Core Components
1. **instalador_vps.py** - Interactive Python installer with enhanced features
   - System of stack categorization (Infrastructure, Databases, Applications, Monitoring)
   - Dependency resolution system
   - Batch installation with predefined profiles (Minimal, Basic, Complete)
   - Customizable domain prefixes
   - DNS configuration generator for Cloudflare
   - Real-time installation feedback
   - Service status verification after deployment
   - Configuration import/export

2. **deploy_stacks.sh** - Original automated bash deployment script
   - Uses dialog for interactive UI
   - Stores config in /root/.docker_installer/config.env
   - Basic stack deployment functionality

3. **deploy_stacks_v2.sh** - Enhanced bash script with Python feature parity
   - All features from Python installer
   - Advanced menu system with categories
   - Profile-based installation
   - DNS configuration generation
   - Stack management tools

4. **bootstrap.sh** - Initial setup script
   - Detects OS (Ubuntu/Debian/CentOS/RHEL)
   - Installs Python3 and dependencies
   - Downloads and runs main installer

5. **stack_implementations.py** - Additional stack implementations
   - Factory pattern for creating stack classes
   - Implementations for all 15 available stacks

### Stack Structure
All Docker stack configurations are in `/stacks/`:
- **Infrastructure**: traefik.yaml, portainer.yaml
- **Databases**: postgres.yaml, pgvector.yaml, redis.yaml
- **Applications**: evolution.yaml, chatwoot.yaml, directus.yaml, minio.yaml
- **Monitoring**: prometheus.yaml, grafana.yaml, dozzle.yaml

### Network Architecture
- **externa** - Public-facing services (overlay network)
- **interna** - Internal services (overlay network)
- **agent_network** - Portainer agent communication

## Key Patterns

### Stack Deployment Flow
1. Create Docker networks and volumes
2. Generate YAML configurations with environment variables
3. Deploy stacks using `docker stack deploy` or Portainer API
4. Configure services post-deployment

### Configuration Management
- Python script: Uses JSON (portainer_config.json)
- Bash script: Uses shell environment file (/root/.docker_installer/config.env)
- Stack configs: YAML files with environment variable substitution

### API Integration
The Python installer integrates with Portainer API for stack management:
- Authentication endpoint: `/api/auth`
- Stack deployment: `/api/stacks` with swarm file type (1)
- Requires admin credentials stored in portainer_config.json

## New Features (v2)

### Installation Profiles
- **Minimal**: Traefik + Portainer (basic infrastructure)
- **Basic**: Minimal + PostgreSQL + Redis
- **Complete**: All 15 available stacks
- **Custom**: Select individual stacks by category

### Stack Categories
- **Infrastructure**: Traefik, Portainer
- **Databases**: PostgreSQL, PGVector, PGBouncer, Redis
- **Applications**: Evolution, Chatwoot, Directus, MinIO, RabbitMQ, StirlingPDF
- **Monitoring**: Prometheus, Grafana, Dozzle

### Enhanced Features
1. **Automatic Dependency Resolution**: Stacks dependencies are resolved automatically
2. **Custom Domain Prefixes**: Each service can have a custom subdomain
3. **DNS Configuration Export**: Generates Cloudflare DNS configuration file
4. **Password Management**: Automatic secure password generation with display
5. **Status Verification**: Checks if services are running after deployment
6. **Configuration Backup/Restore**: Export and import all settings

## Important Notes

1. **Root Access Required**: All scripts must run with sudo/root privileges
2. **Port 9443**: Default Portainer HTTPS port (self-signed certificate)
3. **Swarm Mode**: Docker must be in swarm mode for stack deployment
4. **Service Dependencies**: Handled automatically by the installer
5. **SSL Certificates**: Traefik handles Let's Encrypt SSL with optional Cloudflare DNS challenge
6. **Generated Files**: DNS configuration and passwords are saved to timestamped files

## Common Tasks

### Adding a New Stack
1. Create YAML file in `/stacks/` directory
2. Add deployment logic to StackCommand subclass in instalador_vps.py
3. Update menu options in both Python and Bash scripts
4. Ensure proper network and volume configuration

### Debugging Deployment Issues
```bash
# Check service logs
docker service logs [service_name]

# Check stack status
docker stack ps [stack_name] --no-trunc

# Verify network connectivity
docker network inspect externa

# Check Portainer logs
docker service logs portainer_portainer
```

### Updating Stack Configuration
1. Modify the YAML file in `/stacks/`
2. Remove existing stack: `docker stack rm [stack_name]`
3. Redeploy: `docker stack deploy -c [yaml_file] [stack_name]`