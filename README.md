# VPS Installer - Instalador Automatizado de Infraestrutura

Instale uma infraestrutura completa no seu VPS com apenas um comando!

## 🚀 Instalação Rápida

Execute este comando único na sua VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/bootstrap.sh | sudo bash
```

Ou se preferir baixar primeiro:

```bash
wget https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/bootstrap.sh
chmod +x bootstrap.sh
sudo ./bootstrap.sh
```

## 📦 O que será instalado?

### Perfis Disponíveis:

#### 🔹 **Mínimo** (Essencial)
- **Traefik**: Proxy reverso com SSL automático
- **Portainer**: Interface web para gerenciar Docker

#### 🔹 **Básico** (Recomendado)
- Tudo do Mínimo +
- **PostgreSQL**: Banco de dados principal
- **Redis**: Cache em memória

#### 🔹 **Completo** (Todas as 15 stacks)
- **Infraestrutura**: Traefik, Portainer
- **Bancos de Dados**: PostgreSQL, PGVector, PGBouncer, Redis
- **Aplicações**: Evolution API, Chatwoot, Directus, MinIO, RabbitMQ, StirlingPDF
- **Monitoramento**: Prometheus, Grafana, Dozzle

## 🎯 Como usar?

### 1. Execute o comando de instalação
```bash
curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/bootstrap.sh | sudo bash
```

### 2. O instalador vai:
- ✅ Detectar seu sistema operacional
- ✅ Instalar todas as dependências
- ✅ Baixar todos os arquivos necessários
- ✅ Criar um comando global `vps-installer`

### 3. Execute o instalador
```bash
vps-installer
```

### 4. Siga o menu interativo:
1. **Instalar Docker** (se ainda não tiver)
2. **Inicializar Swarm** 
3. **Instalação Rápida** → Escolha um perfil

### 5. Configure seu domínio:
- Digite seu domínio (ex: `exemplo.com.br`)
- O instalador vai gerar um arquivo com a configuração DNS
- Configure no Cloudflare conforme instruções

### 6. Pronto! 
Acesse seus serviços:
- `https://portainer.seudominio.com`
- `https://traefik.seudominio.com`
- E todos os outros que você instalou!

## 📝 Informações Importantes

### Senhas Geradas
- Todas as senhas são geradas automaticamente
- São mostradas durante a instalação
- Ficam salvas no arquivo `dns_config_*.txt`

### Requisitos
- VPS com Ubuntu/Debian (ou CentOS/RHEL)
- Acesso root
- Domínio próprio
- Conta no Cloudflare (recomendado)

### Arquivos de Configuração
- Configurações salvas em: `/root/.docker_installer/`
- Logs de instalação: `/opt/vps-installer/install.log`
- DNS e senhas: `dns_config_seudominio_[data].txt`

## 🔧 Comandos Úteis

### Após a instalação:
```bash
# Ver stacks instaladas
docker stack ls

# Ver serviços rodando
docker service ls

# Ver logs de um serviço
docker service logs nome_do_servico

# Executar o instalador novamente
vps-installer
```

## 🆘 Problemas?

### Docker não instalou?
```bash
curl -fsSL https://get.docker.com | sh
```

### Swarm não inicializou?
```bash
docker swarm init --advertise-addr SEU_IP
```

### Serviço não está acessível?
1. Verifique se o DNS propagou (pode levar até 48h)
2. Verifique os logs: `docker service logs nome_stack_nome_servico`
3. Verifique se o serviço está rodando: `docker service ps nome_stack_nome_servico`

## 📋 Exemplo Completo

```bash
# 1. Conectar na VPS
ssh root@45.67.89.123

# 2. Executar instalação
curl -fsSL https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/bootstrap.sh | sudo bash

# 3. Quando terminar, executar:
vps-installer

# 4. No menu:
# - Opção 1: Instalar Docker
# - Opção 2: Inicializar Swarm  
# - Opção 3: Instalação Rápida
# - Escolher: "basico"
# - Domínio: meusite.com.br
# - Customizar prefixos: N
# - Email: meuemail@gmail.com

# 5. Configurar DNS no Cloudflare conforme arquivo gerado

# 6. Acessar: https://portainer.meusite.com.br
```

---

**Desenvolvido com ❤️ para facilitar sua vida!**