# 🚀 MCP Server Simplificado para Render.com (Sin OAuth)
import os
import json
import time
from datetime import datetime
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'simple-secret-key')

# CORS configurado para Claude
CORS(app, 
     origins=["https://claude.ai", "https://claude.com", "*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
     supports_credentials=True)

# Cache en memoria
data_cache = None
cache_time = None

def get_redash_data():
    """Obtener datos de Redash con cache"""
    global data_cache, cache_time
    
    # Usar cache si es reciente (5 minutos)
    if data_cache and cache_time and (time.time() - cache_time) < 300:
        return data_cache
    
    try:
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
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def create_json_response(data, status=200):
    """Crear respuesta JSON con headers correctos"""
    response = make_response(jsonify(data), status)
    response.headers.update({
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Cache-Control': 'no-cache'
    })
    return response

# Endpoint principal MCP
@app.route("/", methods=["GET", "POST", "OPTIONS"])
def mcp_endpoint():
    """Endpoint principal del servidor MCP"""
    if request.method == "OPTIONS":
        return create_json_response({})
    
    if request.method == "GET":
        # Información del servidor
        return create_json_response({
            "name": "Redash Orders MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Redash orders data (No Auth)",
            "protocol": "Model Context Protocol v2024-11-05",
            "status": "running",
            "auth_required": False
        })
    
    if request.method == "POST":
        try:
            rpc_request = request.get_json()
            if not rpc_request:
                return create_json_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                    "id": None
                }, 400)
            
            return handle_mcp_request(rpc_request)
            
        except Exception as e:
            return create_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": None
            }, 500)

def handle_mcp_request(rpc_request):
    """Manejar peticiones JSON-RPC del protocolo MCP"""
    method = rpc_request.get('method')
    params = rpc_request.get('params', {})
    request_id = rpc_request.get('id')
    
    if method == "initialize":
        return create_json_response({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "resources": {"subscribe": False},
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "redash-orders-server",
                    "version": "1.0.0"
                }
            },
            "id": request_id
        })
    
    elif method == "tools/list":
        return create_json_response({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "get_orders",
                        "description": "Get orders data from Redash query 3654",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of orders to return",
                                    "default": 10
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["summary", "detailed", "json"],
                                    "description": "Output format",
                                    "default": "summary"
                                }
                            }
                        }
                    },
                    {
                        "name": "get_orders_stats",
                        "description": "Get statistical summary of orders data",
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
        
        if tool_name == "get_orders":
            return handle_get_orders(args, request_id)
        
        elif tool_name == "get_orders_stats":
            return handle_get_orders_stats(request_id)
        
        else:
            return create_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                "id": request_id
            })
    
    else:
        return create_json_response({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": request_id
        })

def handle_get_orders(args, request_id):
    """Manejar la herramienta get_orders"""
    data = get_redash_data()
    
    if not data.get("success"):
        return create_json_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error getting orders data: {data.get('error', 'Unknown error')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    limit = args.get("limit", 10)
    format_type = args.get("format", "summary")
    
    # Aplicar límite
    if isinstance(limit, int) and limit > 0:
        orders = orders[:limit]
    
    # Formatear respuesta según el tipo
    if format_type == "json":
        result_text = f"📊 Orders Data (JSON format)\n\n```json\n{json.dumps(orders[:5], indent=2)}\n```"
    
    elif format_type == "detailed":
        result_text = f"📊 Detailed Orders Data ({len(orders)} records)\n\n"
        for i, order in enumerate(orders[:10], 1):
            result_text += f"**Order {i}:**\n"
            for key, value in order.items():
                result_text += f"  - {key}: {value}\n"
            result_text += "\n"
    
    else:  # summary
        result_text = f"📊 Orders Summary ({len(orders)} records)\n\n"
        if orders:
            # Mostrar primeras 5 órdenes de forma resumida
            for i, order in enumerate(orders[:5], 1):
                # Intentar mostrar campos más relevantes
                order_summary = []
                for key, value in list(order.items())[:3]:  # Primeros 3 campos
                    order_summary.append(f"{key}: {value}")
                
                result_text += f"{i}. {' | '.join(order_summary)}\n"
            
            if len(orders) > 5:
                result_text += f"\n... y {len(orders) - 5} órdenes más\n"
        
        # Agregar metadata
        metadata = data.get("metadata", {})
        result_text += f"\n**Source:** {metadata.get('source', 'Unknown')}\n"
        result_text += f"**Retrieved:** {metadata.get('retrieved_at', 'Unknown')}\n"
        result_text += f"**Total columns:** {len(metadata.get('columns', []))}"
    
    return create_json_response({
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
    data = get_redash_data()
    
    if not data.get("success"):
        return create_json_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ Error getting orders data: {data.get('error', 'Unknown error')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    metadata = data.get("metadata", {})
    
    # Calcular estadísticas básicas
    total_records = len(orders)
    columns = metadata.get("columns", [])
    
    result_text = f"📈 Orders Statistics\n\n"
    result_text += f"**Total Records:** {total_records}\n"
    result_text += f"**Total Columns:** {len(columns)}\n"
    result_text += f"**Data Source:** {metadata.get('source', 'Unknown')}\n"
    result_text += f"**Last Updated:** {metadata.get('retrieved_at', 'Unknown')}\n\n"
    
    if columns:
        result_text += "**Available Columns:**\n"
        for col in columns:
            result_text += f"  • {col}\n"
    
    # Estadísticas adicionales si hay datos
    if orders:
        result_text += f"\n**Sample Data:**\n"
        sample_order = orders[0]
        for key, value in list(sample_order.items())[:5]:
            result_text += f"  • {key}: {value} ({type(value).__name__})\n"
    
    return create_json_response({
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
    return create_json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "render",
        "auth_required": False
    })

# Endpoint de test para verificar la conexión a Redash
@app.route("/test")
def test_redash():
    """Test endpoint para verificar la conexión a Redash"""
    data = get_redash_data()
    return create_json_response({
        "test_result": data,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting MCP Server on port {port}")
    print("📡 No authentication required")
    app.run(host='0.0.0.0', port=port, debug=False)
