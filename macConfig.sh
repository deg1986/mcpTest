#!/bin/bash

# 🚀 Script de Configuración Automática: Claude Desktop + MCP Remoto
# Autor: Diego
# Fecha: $(date '+%Y-%m-%d')
# Versión: 1.0
#
# Este script configura automáticamente Claude Desktop para conectarse a servidores MCP remotos
# Uso: curl -fsSL https://tu-dominio.com/setup-claude-mcp.sh | bash

set -e  # Salir si hay errores

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones de logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo "=================================================================="
echo "🚀 CONFIGURACIÓN AUTOMÁTICA DE CLAUDE DESKTOP + MCP REMOTO"
echo "=================================================================="
echo ""

# Verificar que estamos en macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    log_error "Este script está diseñado para macOS únicamente"
    exit 1
fi

# Configuración de servidores MCP remotos
# 🔧 CONFIGURACIÓN: Agrega aquí tus servidores MCP remotos
declare -A MCP_SERVERS=(
    ["redash-orders"]="https://mcptest-k2zl.onrender.com/"
    # Agregar más servidores aquí:
    # ["analytics"]="https://analytics-server.onrender.com/"
    # ["crm-data"]="https://crm-server.onrender.com/"
)

# Función para verificar si una URL está disponible
check_server_availability() {
    local name=$1
    local url=$2
    
    log_info "Verificando servidor $name en $url"
    
    if curl -s --max-time 10 "$url" > /dev/null 2>&1; then
        log_success "✅ Servidor $name está disponible"
        return 0
    else
        log_warning "⚠️  Servidor $name no responde. Continuando con la configuración..."
        return 1
    fi
}

# Función para descargar e instalar Claude Desktop
install_claude_desktop() {
    log_info "Verificando instalación de Claude Desktop..."
    
    if [ -d "/Applications/Claude.app" ]; then
        log_success "Claude Desktop ya está instalado"
        return 0
    fi
    
    log_info "Claude Desktop no encontrado. Descargando..."
    
    # Crear directorio temporal
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # Descargar Claude Desktop (URL oficial de Anthropic)
    log_info "Descargando Claude Desktop..."
    curl -L -o "Claude.dmg" "https://storage.googleapis.com/osprey-downloads-c02f6a0d-347c-492b-a752-3e0651722e97/nest-prod/Claude-darwin-arm64-latest.dmg"
    
    if [ ! -f "Claude.dmg" ]; then
        log_error "Error al descargar Claude Desktop"
        exit 1
    fi
    
    # Montar el DMG
    log_info "Instalando Claude Desktop..."
    hdiutil attach "Claude.dmg" -quiet
    
    # Copiar la aplicación
    cp -R "/Volumes/Claude/Claude.app" "/Applications/"
    
    # Desmontar el DMG
    hdiutil detach "/Volumes/Claude" -quiet
    
    # Limpiar archivos temporales
    cd - > /dev/null
    rm -rf "$TEMP_DIR"
    
    log_success "✅ Claude Desktop instalado correctamente"
}

# Función para crear el directorio de proxies MCP
create_mcp_proxy_directory() {
    log_info "Creando directorio para proxies MCP..."
    
    MCP_PROXY_DIR="$HOME/mcp-proxy"
    mkdir -p "$MCP_PROXY_DIR"
    
    log_success "✅ Directorio creado: $MCP_PROXY_DIR"
}

# Función para crear el proxy genérico
create_generic_proxy() {
    log_info "Creando proxy genérico para servidores MCP remotos..."
    
    cat > "$HOME/mcp-proxy/generic-mcp-proxy.sh" << 'PROXY_EOF'
#!/bin/bash

# Proxy MCP genérico para servidores remotos
# Uso: generic-mcp-proxy.sh <URL_DEL_SERVIDOR>

if [ -z "$1" ]; then
    echo "Error: URL del servidor requerida" >&2
    echo "Uso: $0 <URL_DEL_SERVIDOR>" >&2
    exit 1
fi

REMOTE_SERVER="$1"
SERVER_NAME=$(basename "$REMOTE_SERVER" | sed 's/[^a-zA-Z0-9]//g')

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [MCP-PROXY-${SERVER_NAME}]: $1" >&2
}

log_error "🚀 Iniciando proxy MCP para: $REMOTE_SERVER"

while IFS= read -r line; do
    if [ -n "$line" ]; then
        log_error "📥 Request recibido de Claude Desktop"
        
        response=$(curl -s --max-time 30 -X POST "$REMOTE_SERVER" \
            -H "Content-Type: application/json" \
            -H "User-Agent: Claude-MCP-Proxy/1.0" \
            -d "$line" 2>/dev/null)
        
        if [ $? -eq 0 ] && [ -n "$response" ]; then
            log_error "📤 Response enviado a Claude Desktop"
            echo "$response"
        else
            log_error "❌ Error de comunicación con servidor remoto"
            # Respuesta de error estándar JSON-RPC
            echo '{"jsonrpc":"2.0","error":{"code":-32603,"message":"Proxy communication error","data":{"server":"'$REMOTE_SERVER'"}},"id":null}'
        fi
    fi
done

log_error "🔚 Proxy MCP cerrado"
PROXY_EOF

    chmod +x "$HOME/mcp-proxy/generic-mcp-proxy.sh"
    log_success "✅ Proxy genérico creado"
}

# Función para crear proxies específicos para cada servidor
create_specific_proxies() {
    log_info "Creando proxies específicos para cada servidor..."
    
    for server_name in "${!MCP_SERVERS[@]}"; do
        server_url="${MCP_SERVERS[$server_name]}"
        proxy_file="$HOME/mcp-proxy/${server_name}-proxy.sh"
        
        log_info "Creando proxy para $server_name"
        
        cat > "$proxy_file" << SPECIFIC_PROXY_EOF
#!/bin/bash

# Proxy específico para $server_name
# Servidor: $server_url
# Generado automáticamente el $(date)

REMOTE_SERVER="$server_url"

log_error() {
    echo "\$(date '+%Y-%m-%d %H:%M:%S') [$server_name-PROXY]: \$1" >&2
}

log_error "🚀 Iniciando proxy para $server_name en \$REMOTE_SERVER"

while IFS= read -r line; do
    if [ -n "\$line" ]; then
        log_error "📥 Request de Claude Desktop"
        
        response=\$(curl -s --max-time 30 -X POST "\$REMOTE_SERVER" \\
            -H "Content-Type: application/json" \\
            -H "User-Agent: Claude-MCP-Proxy-$server_name/1.0" \\
            -d "\$line" 2>/dev/null)
        
        if [ \$? -eq 0 ] && [ -n "\$response" ]; then
            log_error "📤 Response del servidor $server_name"
            echo "\$response"
        else
            log_error "❌ Error comunicación con $server_name"
            echo '{"jsonrpc":"2.0","error":{"code":-32603,"message":"$server_name communication error"},"id":null}'
        fi
    fi
done

log_error "🔚 Proxy $server_name cerrado"
SPECIFIC_PROXY_EOF

        chmod +x "$proxy_file"
        log_success "✅ Proxy creado para $server_name"
    done
}

# Función para generar la configuración de Claude Desktop
generate_claude_config() {
    log_info "Generando configuración de Claude Desktop..."
    
    # Crear directorio si no existe
    CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
    mkdir -p "$CLAUDE_CONFIG_DIR"
    
    # Respaldar configuración existente
    if [ -f "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" ]; then
        log_warning "Respaldando configuración existente..."
        cp "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" "$CLAUDE_CONFIG_DIR/claude_desktop_config.json.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Generar nueva configuración
    cat > "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" << CONFIG_EOF
{
  "mcpServers": {
CONFIG_EOF

    # Agregar cada servidor a la configuración
    local first_server=true
    for server_name in "${!MCP_SERVERS[@]}"; do
        if [ "$first_server" = false ]; then
            echo "," >> "$CLAUDE_CONFIG_DIR/claude_desktop_config.json"
        fi
        first_server=false
        
        cat >> "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" << CONFIG_SERVER_EOF
    "$server_name": {
      "command": "$HOME/mcp-proxy/${server_name}-proxy.sh"
    }
CONFIG_SERVER_EOF
    done
    
    # Cerrar configuración
    cat >> "$CLAUDE_CONFIG_DIR/claude_desktop_config.json" << CONFIG_EOF
  }
}
CONFIG_EOF

    log_success "✅ Configuración de Claude Desktop generada"
}

# Función para crear script de testing
create_test_script() {
    log_info "Creando script de testing..."
    
    cat > "$HOME/mcp-proxy/test-mcp-servers.sh" << 'TEST_EOF'
#!/bin/bash

# Script de testing para servidores MCP
# Uso: ./test-mcp-servers.sh

echo "🧪 TESTING DE SERVIDORES MCP"
echo "============================"

# Leer configuración de Claude
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuración de Claude no encontrada"
    exit 1
fi

# Extraer servidores de la configuración
servers=$(grep -o '"[^"]*": {' "$CONFIG_FILE" | sed 's/": {//' | sed 's/"//g' | grep -v mcpServers)

for server in $servers; do
    echo ""
    echo "🔍 Testing servidor: $server"
    echo "------------------------"
    
    proxy_script="$HOME/mcp-proxy/${server}-proxy.sh"
    
    if [ ! -f "$proxy_script" ]; then
        echo "❌ Proxy script no encontrado: $proxy_script"
        continue
    fi
    
    # Test de inicialización
    test_request='{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
    
    echo "📤 Enviando request de inicialización..."
    response=$(echo "$test_request" | timeout 15 "$proxy_script" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$response" ]; then
        echo "✅ Servidor $server responde correctamente"
        echo "📄 Response (primeros 200 chars): ${response:0:200}..."
    else
        echo "❌ Servidor $server no responde o error en comunicación"
    fi
done

echo ""
echo "🏁 Testing completado"
TEST_EOF

    chmod +x "$HOME/mcp-proxy/test-mcp-servers.sh"
    log_success "✅ Script de testing creado: $HOME/mcp-proxy/test-mcp-servers.sh"
}

# Función para crear documentación
create_documentation() {
    log_info "Creando documentación..."
    
    cat > "$HOME/mcp-proxy/README.md" << 'DOC_EOF'
# 📚 Configuración MCP para Claude Desktop

## 🎯 Servidores Configurados

Esta instalación incluye los siguientes servidores MCP remotos:

DOC_EOF

    for server_name in "${!MCP_SERVERS[@]}"; do
        server_url="${MCP_SERVERS[$server_name]}"
        cat >> "$HOME/mcp-proxy/README.md" << DOC_SERVER_EOF
- **$server_name**: $server_url

DOC_SERVER_EOF
    done

    cat >> "$HOME/mcp-proxy/README.md" << 'DOC_USAGE_EOF'

## 🔧 Archivos Generados

- `~/mcp-proxy/generic-mcp-proxy.sh` - Proxy genérico reutilizable
- `~/mcp-proxy/[servidor]-proxy.sh` - Proxies específicos para cada servidor
- `~/mcp-proxy/test-mcp-servers.sh` - Script de testing
- `~/Library/Application Support/Claude/claude_desktop_config.json` - Configuración de Claude

## 🧪 Testing

Para verificar que los servidores funcionan:

```bash
cd ~/mcp-proxy
./test-mcp-servers.sh
```

## ➕ Agregar Nuevos Servidores

Para agregar un nuevo servidor MCP remoto:

### Opción 1: Usar el proxy genérico

1. Editar `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Agregar nueva entrada:

```json
{
  "mcpServers": {
    "servidor-existente": {
      "command": "/Users/[usuario]/mcp-proxy/servidor-existente-proxy.sh"
    },
    "nuevo-servidor": {
      "command": "/Users/[usuario]/mcp-proxy/generic-mcp-proxy.sh",
      "args": ["https://nuevo-servidor.com/"]
    }
  }
}
```

### Opción 2: Crear proxy específico

1. Crear nuevo proxy:

```bash
cp ~/mcp-proxy/generic-mcp-proxy.sh ~/mcp-proxy/nuevo-servidor-proxy.sh
# Editar el archivo para hacer hardcode de la URL
```

2. Agregar a configuración:

```json
"nuevo-servidor": {
  "command": "/Users/[usuario]/mcp-proxy/nuevo-servidor-proxy.sh"
}
```

3. Reiniciar Claude Desktop

## 🔍 Debugging

### Ver logs de MCP:
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

### Verificar procesos:
```bash
ps aux | grep mcp-proxy
```

### Test manual de proxy:
```bash
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | ~/mcp-proxy/[servidor]-proxy.sh
```

## 🔄 Actualización

Para actualizar la configuración, vuelve a ejecutar el script de instalación:

```bash
curl -fsSL https://tu-dominio.com/setup-claude-mcp.sh | bash
```

DOC_USAGE_EOF

    log_success "✅ Documentación creada: $HOME/mcp-proxy/README.md"
}

# Función para verificar la instalación
verify_installation() {
    log_info "Verificando instalación..."
    
    # Verificar Claude Desktop
    if [ ! -d "/Applications/Claude.app" ]; then
        log_error "Claude Desktop no está instalado"
        return 1
    fi
    
    # Verificar configuración
    if [ ! -f "$HOME/Library/Application Support/Claude/claude_desktop_config.json" ]; then
        log_error "Configuración de Claude no encontrada"
        return 1
    fi
    
    # Verificar proxies
    local all_proxies_ok=true
    for server_name in "${!MCP_SERVERS[@]}"; do
        if [ ! -f "$HOME/mcp-proxy/${server_name}-proxy.sh" ]; then
            log_error "Proxy para $server_name no encontrado"
            all_proxies_ok=false
        fi
    done
    
    if [ "$all_proxies_ok" = true ]; then
        log_success "✅ Verificación completada - Todo instalado correctamente"
        return 0
    else
        log_error "Algunos componentes faltan"
        return 1
    fi
}

# FUNCIÓN PRINCIPAL
main() {
    log_info "Iniciando configuración automática..."
    
    # Verificar disponibilidad de servidores
    log_info "Verificando disponibilidad de servidores remotos..."
    for server_name in "${!MCP_SERVERS[@]}"; do
        check_server_availability "$server_name" "${MCP_SERVERS[$server_name]}"
    done
    
    # Instalar Claude Desktop
    install_claude_desktop
    
    # Crear estructura de proxies
    create_mcp_proxy_directory
    create_generic_proxy
    create_specific_proxies
    
    # Configurar Claude Desktop
    generate_claude_config
    
    # Crear herramientas adicionales
    create_test_script
    create_documentation
    
    # Verificar instalación
    if verify_installation; then
        echo ""
        echo "=================================================================="
        log_success "🎉 INSTALACIÓN COMPLETADA EXITOSAMENTE"
        echo "=================================================================="
        echo ""
        log_info "📋 Próximos pasos:"
        echo "   1. Reinicia Claude Desktop si estaba abierto"
        echo "   2. Abre Claude Desktop"
        echo "   3. Verifica que los servidores aparezcan conectados"
        echo "   4. Prueba con: 'Dame las estadísticas de órdenes'"
        echo ""
        log_info "📁 Archivos creados en: $HOME/mcp-proxy/"
        log_info "📖 Lee la documentación: $HOME/mcp-proxy/README.md"
        log_info "🧪 Ejecuta tests: $HOME/mcp-proxy/test-mcp-servers.sh"
        echo ""
    else
        echo ""
        log_error "❌ La instalación tuvo problemas. Revisa los errores anteriores."
        exit 1
    fi
}

# Ejecutar función principal
main "$@"
EOF
