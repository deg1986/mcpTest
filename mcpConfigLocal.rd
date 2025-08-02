# 📋 Guía: Cómo Agregar Nuevos Servidores MCP

## 🎯 Opciones para Agregar Nuevos Servidores

### **Opción 1: Modificar el Script de Instalación (Recomendado)**

Para que el nuevo servidor se incluya automáticamente en futuras instalaciones:

#### 1.1 Editar la sección de configuración en el script:

```bash
# Encontrar esta línea en el script:
declare -A MCP_SERVERS=(
    ["redash-orders"]="https://mcptest-k2zl.onrender.com/"
    # Agregar más servidores aquí:
    # ["analytics"]="https://analytics-server.onrender.com/"
    # ["crm-data"]="https://crm-server.onrender.com/"
)

# Cambiar por:
declare -A MCP_SERVERS=(
    ["redash-orders"]="https://mcptest-k2zl.onrender.com/"
    ["analytics"]="https://analytics-server.onrender.com/"
    ["crm-data"]="https://crm-server.onrender.com/"
    ["nuevo-servidor"]="https://nuevo-servidor.onrender.com/"
)
```

#### 1.2 Volver a ejecutar el script:

```bash
curl -fsSL https://tu-dominio.com/setup-claude-mcp.sh | bash
```

---

### **Opción 2: Agregado Manual (Más Rápido)**

Para agregar un servidor sin modificar el script principal:

#### 2.1 Crear proxy específico para el nuevo servidor:

```bash
# Método A: Usar el proxy genérico (más simple)
# Solo agregar a la configuración de Claude Desktop

# Método B: Crear proxy específico (más control)
cp ~/mcp-proxy/generic-mcp-proxy.sh ~/mcp-proxy/nuevo-servidor-proxy.sh

# Editar el archivo para hacer hardcode de la URL:
sed -i '' 's|REMOTE_SERVER="$1"|REMOTE_SERVER="https://nuevo-servidor.com/"|' ~/mcp-proxy/nuevo-servidor-proxy.sh
sed -i '' '/if \[ -z "\$1" \]/,/fi/d' ~/mcp-proxy/nuevo-servidor-proxy.sh
```

#### 2.2 Actualizar configuración de Claude Desktop:

```bash
# Respaldar configuración actual
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup

# Opción A: Usar proxy genérico
cat > ~/Library/Application\ Support/Claude/claude_desktop_config.json << EOF
{
  "mcpServers": {
    "redash-orders": {
      "command": "$HOME/mcp-proxy/redash-orders-proxy.sh"
    },
    "nuevo-servidor": {
      "command": "$HOME/mcp-proxy/generic-mcp-proxy.sh",
      "args": ["https://nuevo-servidor.onrender.com/"]
    }
  }
}
EOF

# Opción B: Usar proxy específico
cat > ~/Library/Application\ Support/Claude/claude_desktop_config.json << EOF
{
  "mcpServers": {
    "redash-orders": {
      "command": "$HOME/mcp-proxy/redash-orders-proxy.sh"
    },
    "nuevo-servidor": {
      "command": "$HOME/mcp-proxy/nuevo-servidor-proxy.sh"
    }
  }
}
EOF
```

#### 2.3 Reiniciar Claude Desktop:

```bash
# Cerrar Claude Desktop completamente
osascript -e 'tell application "Claude" to quit'

# Esperar y reabrir
sleep 3
open -a Claude
```

---

## 🧪 Testing del Nuevo Servidor

### Test Manual:

```bash
# Para proxy genérico:
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | ~/mcp-proxy/generic-mcp-proxy.sh https://nuevo-servidor.onrender.com/

# Para proxy específico:
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | ~/mcp-proxy/nuevo-servidor-proxy.sh
```

### Test con Script Automático:

```bash
~/mcp-proxy/test-mcp-servers.sh
```

### Verificar en Claude Desktop:

1. Abre Claude Desktop
2. Verifica que el nuevo servidor aparezca en la configuración
3. Prueba comandos específicos del servidor

---

## 🔍 Debugging de Nuevos Servidores

### Ver logs específicos:

```bash
# Logs generales de MCP
tail -f ~/Library/Logs/Claude/mcp*.log

# Logs específicos del nuevo servidor
tail -f ~/Library/Logs/Claude/mcp-server-nuevo-servidor.log
```

### Verificar configuración:

```bash
# Ver configuración actual
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Verificar que el proxy existe y es ejecutable
ls -la ~/mcp-proxy/nuevo-servidor-proxy.sh
```

### Test de conectividad del servidor remoto:

```bash
# Verificar que el servidor remoto responde
curl -X POST https://nuevo-servidor.onrender.com/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```

---

## 📊 Comparación: Proxy Genérico vs Específico

| Aspecto | Proxy Genérico | Proxy Específico |
|---------|----------------|------------------|
| **Simplicidad** | ✅ Solo agregar a config | ❌ Crear archivo + config |
| **Performance** | ❌ Parámetro extra | ✅ URL hardcodeada |
| **Mantenimiento** | ✅ Un archivo para todos | ❌ Un archivo por servidor |
| **Debugging** | ❌ Logs genéricos | ✅ Logs específicos |
| **Personalización** | ❌ Limitada | ✅ Total control |

### **Recomendación:**
- **Proxy genérico**: Para testing rápido o servidores temporales
- **Proxy específico**: Para servidores de producción a largo plazo

---

## 🔄 Gestión de Múltiples Servidores

### Template de configuración para muchos servidores:

```json
{
  "mcpServers": {
    "redash-orders": {
      "command": "/Users/diego/mcp-proxy/redash-orders-proxy.sh"
    },
    "analytics": {
      "command": "/Users/diego/mcp-proxy/analytics-proxy.sh"
    },
    "crm": {
      "command": "/Users/diego/mcp-proxy/generic-mcp-proxy.sh",
      "args": ["https://crm-api.company.com/"]
    },
    "inventory": {
      "command": "/Users/diego/mcp-proxy/generic-mcp-proxy.sh",
      "args": ["https://inventory-api.company.com/"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/Users/diego/Documents"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-brave-search"]
    }
  }
}
```

### Script para gestionar múltiples servidores:

```bash
#!/bin/bash
# Gestor de servidores MCP

case "$1" in
  "list")
    echo "Servidores MCP configurados:"
    grep -o '"[^"]*": {' ~/Library/Application\ Support/Claude/claude_desktop_config.json | sed 's/": {//' | sed 's/"//g' | grep -v mcpServers
    ;;
  "test")
    if [ -n "$2" ]; then
      # Test servidor específico
      ~/mcp-proxy/test-mcp-servers.sh | grep -A 10 "$2"
    else
      # Test todos
      ~/mcp-proxy/test-mcp-servers.sh
    fi
    ;;
  "logs")
    if [ -n "$2" ]; then
      tail -f ~/Library/Logs/Claude/mcp-server-$2.log
    else
      tail -f ~/Library/Logs/Claude/mcp*.log
    fi
    ;;
  *)
    echo "Uso: $0 {list|test [servidor]|logs [servidor]}"
    ;;
esac
```

---

## 🚀 Desarrollo de Nuevos Servidores MCP

### Template básico para servidor remoto:

```python
# Usar el template del servidor que ya tienes funcionando
# Personalizar estas secciones:

# 1. URL de la API externa
def get_external_data():
    url = "TU_NUEVA_API_AQUI"  # 🔄 CAMBIAR
    # ... resto del código

# 2. Información del servidor
@app.route("/", methods=["GET"])
def mcp_endpoint():
    return create_mcp_response({
        "name": "Tu Nuevo Servidor MCP",  # 🔄 CAMBIAR
        "description": "Descripción del servidor",  # 🔄 CAMBIAR
        # ... resto

# 3. Herramientas disponibles
elif method == "tools/list":
    return create_mcp_response({
        "tools": [
            {
                "name": "tu_herramienta",  # 🔄 CAMBIAR
                "description": "Descripción de la herramienta",  # 🔄 CAMBIAR
                # ... resto
```

### Checklist para nuevo servidor:

- [ ] Servidor remoto desplegado y funcionando
- [ ] Endpoint `/health` responde correctamente
- [ ] Método `initialize` implementado
- [ ] Método `tools/list` implementado
- [ ] Herramientas específicas implementadas
- [ ] Proxy local creado
- [ ] Configuración de Claude actualizada
- [ ] Tests de conectividad pasando
- [ ] Logs funcionando correctamente

---

## 📝 Notas Importantes

1. **Orden de servidores**: Claude Desktop carga los servidores en el orden que aparecen en la configuración
2. **Límite de servidores**: No hay límite técnico, pero muchos servidores pueden afectar el rendimiento
