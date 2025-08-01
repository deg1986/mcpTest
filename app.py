# 🚀 MCP Server Corregido para Claude Desktop
import os
import json
import time
import sys
from datetime import datetime
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'simple-secret-key')

# CORS más permisivo para Claude Desktop
CORS(app, 
     origins=["*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["*"],
     supports_credentials=True)

# Cache en memoria
data_cache = None
cache_time = None

def log_to_stderr(message):
    """Log messages to stderr for Claude Desktop debugging"""
    print(f"[MCP] {datetime.now().isoformat()}: {message}", file=sys.stderr, flush=True)

def get_redash_data():
    """Obtener datos de Redash con cache"""
    global data_cache, cache_time
    
    # Usar cache si es reciente (5 minutos)
    if data_cache and cache_time and (time.time() - cache_time) < 300:
        log_to_stderr("Using cached data")
        return data_cache
    
    try:
        log_to_stderr("Fetching fresh data from Redash")
        url = "https://redash-devops.farmuhub.co/api/queries/3654/results.json?api_key=KoRPiEdAKlWuqPk7UVwtFWmjeIEkjlQPZ2kzsG3H"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        raw = response.json()
        rows = raw.get("query_result", {}).get("data", {}).get("rows", [])
        columns = raw.get("query_result", {}).get("data", {}).get("columns", [])
        
        # Procesar datos
        processed_data = []
        column_names = [col.get('name', f'col_{i}') if isinstance(col, dict) else str(col) for i, col in enumerate(columns)]
        
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                if i < len(column_names):
                    row_dict[column_names[i]] = value
            processed_data.append(row_dict)
        
        result = {
            "success": True,
            "data": processed_data,
            "metadata": {
                "total_records": len(processed_data),
                "columns": column_names,
                "source": "Redash Query 3654",
                "retrieved_at": datetime.now().isoformat()
            }
        }
        
        # Actualizar cache
        data_cache = result
        cache_time = time.time()
        log_to_stderr(f"Successfully fetched {len(processed_data)} records")
        return result
        
    except Exception as e:
        log_to_stderr(f"Error fetching Redash data: {str(e)}")
        return {"success": False, "error": str(e), "data": []}

def create_mcp_response(data, status=200):
    """Crear respuesta MCP con headers correctos"""
    response = make_response(jsonify(data), status)
    response.headers.update({
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': '*',
        'Cache-Control': 'no-cache'
    })
    return response

# Manejar OPTIONS para CORS
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

# Endpoint principal MCP - DEBE manejar tanto GET como POST
@app.route("/", methods=["GET", "POST", "OPTIONS"])
def mcp_endpoint():
    """Endpoint principal del servidor MCP"""
    log_to_stderr(f"Received {request.method} request to /")
    
    if request.method == "OPTIONS":
        return create_mcp_response({})
    
    if request.method == "GET":
        # Información del servidor para verificación
        log_to_stderr("Serving server info via GET")
        return create_mcp_response({
            "name": "Redash Orders MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Redash orders data",
            "protocol": "Model Context Protocol v2024-11-05",
            "status": "running",
            "auth_required": False,
            "endpoints": {
                "health": "/health",
                "test": "/test"
            }
        })
    
    if request.method == "POST":
        try:
            # Obtener el JSON de la petición
            if not request.is_json:
                log_to_stderr("Request is not JSON")
                return create_mcp_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Invalid JSON"},
                    "id": None
                }, 400)
            
            rpc_request = request.get_json()
            if not rpc_request:
                log_to_stderr("Empty JSON request")
                return create_mcp_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None
                }, 400)
            
            log_to_stderr(f"Processing MCP request: {rpc_request.get('method', 'unknown')}")
            return handle_mcp_request(rpc_request)
            
        except Exception as e:
            log_to_stderr(f"Error processing request: {str(e)}")
            return create_mcp_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": None
            }, 500)

def handle_mcp_request(rpc_request):
    """Manejar peticiones JSON-RPC del protocolo MCP"""
    method = rpc_request.get('method')
    params = rpc_request.get('params', {})
    request_id = rpc_request.get('id')
    
    log_to_stderr(f"Handling MCP method: {method} with ID: {request_id}")
    
    # CRÍTICO: El método initialize es el primer handshake
    if method == "initialize":
        log_to_stderr("Handling initialize request")
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {"subscribe": False, "listChanged": False},
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "redash-orders-server",
                    "version": "1.0.0"
                }
            },
            "id": request_id
        })
    
    # CRÍTICO: Después del initialize, Claude llama a initialized
    elif method == "initialized":
        log_to_stderr("Handling initialized notification")
        # Este es un notification, no requiere respuesta según JSON-RPC
        return create_mcp_response({})
    
    elif method == "tools/list":
        log_to_stderr("Handling tools/list request")
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "get_orders",
                        "description": "Get orders data from Redash query 3654. Returns order information from the database.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of orders to return (default: 10)",
                                    "default": 10,
                                    "minimum": 1,
                                    "maximum": 100
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["summary", "detailed", "json"],
                                    "description": "Output format for the data (default: summary)",
                                    "default": "summary"
                                }
                            }
                        }
                    },
                    {
                        "name": "get_orders_stats",
                        "description": "Get statistical summary and metadata about the orders data",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            },
            "id": request_id
        })
    
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        log_to_stderr(f"Calling tool: {tool_name} with args: {args}")
        
        if tool_name == "get_orders":
            return handle_get_orders(args, request_id)
        elif tool_name == "get_orders_stats":
            return handle_get_orders_stats(request_id)
        else:
            log_to_stderr(f"Unknown tool: {tool_name}")
            return create_mcp_response({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                "id": request_id
            })
    
    # Manejar otros métodos que Claude puede llamar
    elif method == "resources/list":
        log_to_stderr("Handling resources/list request")
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {"resources": []},
            "id": request_id
        })
    
    elif method == "prompts/list":
        log_to_stderr("Handling prompts/list request")
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {"prompts": []},
            "id": request_id
        })
    
    else:
        log_to_stderr(f"Method not found: {method}")
        return create_mcp_response({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": request_id
        })

def handle_get_orders(args, request_id):
    """Manejar la herramienta get_orders"""
    log_to_stderr(f"Executing get_orders with args: {args}")
    
    data = get_redash_data()
    
    if not data.get("success"):
        error_msg = f"❌ Error getting orders data: {data.get('error', 'Unknown error')}"
        log_to_stderr(error_msg)
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": error_msg
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    limit = min(args.get("limit", 10), 100)  # Máximo 100
    format_type = args.get("format", "summary")
    
    # Aplicar límite
    if isinstance(limit, int) and limit > 0:
        orders = orders[:limit]
    
    # Formatear respuesta según el tipo
    if format_type == "json":
        result_text = f"📊 Orders Data (JSON format) - {len(orders)} records\n\n```json\n{json.dumps(orders[:5], indent=2, ensure_ascii=False)}\n```"
        if len(orders) > 5:
            result_text += f"\n\n... showing first 5 of {len(orders)} total records"
    
    elif format_type == "detailed":
        result_text = f"📊 Detailed Orders Data ({len(orders)} records)\n\n"
        for i, order in enumerate(orders[:10], 1):
            result_text += f"**Order {i}:**\n"
            for key, value in order.items():
                result_text += f"  • {key}: {value}\n"
            result_text += "\n"
        if len(orders) > 10:
            result_text += f"... y {len(orders) - 10} órdenes más disponibles"
    
    else:  # summary
        result_text = f"📊 Orders Summary - {len(orders)} records retrieved\n\n"
        if orders:
            # Mostrar primeras órdenes de forma resumida
            for i, order in enumerate(orders[:5], 1):
                # Mostrar los primeros 3 campos de cada orden
                order_summary = []
                for key, value in list(order.items())[:3]:
                    order_summary.append(f"{key}: {value}")
                
                result_text += f"{i}. {' | '.join(order_summary)}\n"
            
            if len(orders) > 5:
                result_text += f"\n... y {len(orders) - 5} órdenes más disponibles\n"
        
        # Agregar metadata
        metadata = data.get("metadata", {})
        result_text += f"\n**📍 Source:** {metadata.get('source', 'Unknown')}\n"
        result_text += f"**🕐 Retrieved:** {metadata.get('retrieved_at', 'Unknown')}\n"
        result_text += f"**📊 Total columns:** {len(metadata.get('columns', []))}"
    
    log_to_stderr(f"Returning {len(orders)} orders in {format_type} format")
    
    return create_mcp_response({
        "jsonrpc": "2.0",
        "result": {
            "content": [{
                "type": "text",
                "text": result_text
            }]
        },
        "id": request_id
    })

def handle_get_orders_stats(request_id):
    """Manejar la herramienta get_orders_stats"""
    log_to_stderr("Executing get_orders_stats")
    
    data = get_redash_data()
    
    if not data.get("success"):
        error_msg = f"❌ Error getting orders data: {data.get('error', 'Unknown error')}"
        log_to_stderr(error_msg)
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": error_msg
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    metadata = data.get("metadata", {})
    
    # Calcular estadísticas básicas
    total_records = len(orders)
    columns = metadata.get("columns", [])
    
    result_text = f"📈 Orders Database Statistics\n\n"
    result_text += f"**📊 Total Records:** {total_records:,}\n"
    result_text += f"**🏷️ Total Columns:** {len(columns)}\n"
    result_text += f"**🔗 Data Source:** {metadata.get('source', 'Unknown')}\n"
    result_text += f"**⏰ Last Updated:** {metadata.get('retrieved_at', 'Unknown')}\n\n"
    
    if columns:
        result_text += "**📋 Available Columns:**\n"
        for i, col in enumerate(columns, 1):
            result_text += f"  {i}. {col}\n"
    
    # Estadísticas adicionales si hay datos
    if orders:
        result_text += f"\n**🔍 Sample Data (First Record):**\n"
        sample_order = orders[0]
        for key, value in list(sample_order.items())[:5]:
            value_type = type(value).__name__
            result_text += f"  • **{key}:** {value} `({value_type})`\n"
        
        if len(sample_order) > 5:
            result_text += f"  ... and {len(sample_order) - 5} more fields\n"
    
    log_to_stderr("Returning statistics summary")
    
    return create_mcp_response({
        "jsonrpc": "2.0",
        "result": {
            "content": [{
                "type": "text",
                "text": result_text
            }]
        },
        "id": request_id
    })

@app.route("/health")
def health():
    """Health check endpoint"""
    log_to_stderr("Health check requested")
    return create_mcp_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "render",
        "auth_required": False,
        "mcp_protocol": "2024-11-05"
    })

@app.route("/test")
def test_redash():
    """Test endpoint para verificar la conexión a Redash"""
    log_to_stderr("Test endpoint requested")
    data = get_redash_data()
    return create_mcp_response({
        "test_result": data,
        "timestamp": datetime.now().isoformat(),
        "server_status": "operational"
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    log_to_stderr(f"🚀 Starting MCP Server on port {port}")
    log_to_stderr("📡 No authentication required")
    log_to_stderr("🔧 Enhanced debugging enabled")
    app.run(host='0.0.0.0', port=port, debug=False)
