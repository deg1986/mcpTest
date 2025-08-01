# 🚀 Servidor MCP Remoto Corregido para Claude Desktop
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

# CORS más permisivo
CORS(app, 
     origins=["*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["*"],
     supports_credentials=True)

# Cache en memoria
data_cache = None
cache_time = None

def get_redash_data():
    """Obtener datos de Redash con cache"""
    global data_cache, cache_time
    
    if data_cache and cache_time and (time.time() - cache_time) < 300:
        return data_cache
    
    try:
        url = "https://redash-devops.farmuhub.co/api/queries/3654/results.json?api_key=KoRPiEdAKlWuqPk7UVwtFWmjeIEkjlQPZ2kzsG3H"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        raw = response.json()
        rows = raw.get("query_result", {}).get("data", {}).get("rows", [])
        columns = raw.get("query_result", {}).get("data", {}).get("columns", [])
        
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
        
        data_cache = result
        cache_time = time.time()
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "data": []}

def create_mcp_response(data, status=200):
    """Crear respuesta MCP con headers específicos para Claude Desktop"""
    response = make_response(jsonify(data), status)
    response.headers.update({
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': '*',
        'Cache-Control': 'no-cache',
        # Headers específicos para MCP
        'X-MCP-Protocol': '2024-11-05',
        'X-MCP-Server': 'redash-orders-server'
    })
    return response

@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response

# Endpoint principal MCP con manejo específico para Claude Desktop
@app.route("/", methods=["GET", "POST", "OPTIONS"])
def mcp_endpoint():
    """Endpoint principal optimizado para Claude Desktop MCP"""
    
    if request.method == "OPTIONS":
        return create_mcp_response({})
    
    if request.method == "GET":
        # Información del servidor para verificación
        return create_mcp_response({
            "name": "Redash Orders MCP Server",
            "version": "1.0.0",
            "description": "MCP server for Redash orders data - Claude Desktop compatible",
            "protocol": "Model Context Protocol v2024-11-05",
            "status": "running",
            "auth_required": False,
            "capabilities": {
                "resources": {"subscribe": False, "listChanged": False},
                "tools": {"listChanged": False}
            },
            "compatibility": {
                "claude_desktop": True,
                "protocol_version": "2024-11-05"
            }
        })
    
    if request.method == "POST":
        try:
            if not request.is_json:
                return create_mcp_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Content must be JSON"},
                    "id": None
                }, 400)
            
            rpc_request = request.get_json()
            if not rpc_request:
                return create_mcp_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Empty request body"},
                    "id": None
                }, 400)
            
            # Verificar que es un request JSON-RPC válido
            if not isinstance(rpc_request, dict) or 'method' not in rpc_request:
                return create_mcp_response({
                    "jsonrpc": "2.0",
                    "error": {"code": -32600, "message": "Invalid JSON-RPC request"},
                    "id": rpc_request.get('id')
                }, 400)
            
            return handle_mcp_request(rpc_request)
            
        except Exception as e:
            return create_mcp_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": None
            }, 500)

def handle_mcp_request(rpc_request):
    """Manejar peticiones JSON-RPC del protocolo MCP con compatibilidad específica para Claude Desktop"""
    method = rpc_request.get('method')
    params = rpc_request.get('params', {})
    request_id = rpc_request.get('id')
    
    # CRÍTICO: Manejo específico para Claude Desktop
    if method == "initialize":
        # Claude Desktop puede enviar diferentes versiones del protocolo
        client_protocol = params.get('protocolVersion', '2024-11-05')
        
        # Responder con la versión que Claude Desktop espera
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",  # Versión estable
                "capabilities": {
                    "resources": {
                        "subscribe": False,
                        "listChanged": False
                    },
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "redash-orders-server",
                    "version": "1.0.0"
                },
                "_meta": {
                    "clientProtocol": client_protocol,
                    "serverTime": datetime.now().isoformat()
                }
            },
            "id": request_id
        })
    
    elif method == "initialized":
        # Notification que no requiere respuesta pero debemos ack
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {},
            "id": request_id
        })
    
    elif method == "tools/list":
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "get_orders",
                        "description": "Retrieve orders data from Redash database. Get comprehensive order information with flexible formatting options.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of orders to return",
                                    "default": 10,
                                    "minimum": 1,
                                    "maximum": 100
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["summary", "detailed", "json"],
                                    "description": "Output format: 'summary' for overview, 'detailed' for full info, 'json' for raw data",
                                    "default": "summary"
                                }
                            },
                            "additionalProperties": False
                        }
                    },
                    {
                        "name": "get_orders_stats",
                        "description": "Get statistical overview and metadata about the orders database including record counts, column information, and data source details.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    },
                    {
                        "name": "search_orders",
                        "description": "Search through orders data with basic filtering capabilities.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search term to look for in order data"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum results to return",
                                    "default": 10,
                                    "minimum": 1,
                                    "maximum": 50
                                }
                            },
                            "required": ["query"],
                            "additionalProperties": False
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
        elif tool_name == "search_orders":
            return handle_search_orders(args, request_id)
        else:
            return create_mcp_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                    "data": {"available_tools": ["get_orders", "get_orders_stats", "search_orders"]}
                },
                "id": request_id
            })
    
    elif method == "resources/list":
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {"resources": []},
            "id": request_id
        })
    
    elif method == "prompts/list":
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {"prompts": []},
            "id": request_id
        })
    
    # Manejar métodos adicionales que Claude Desktop puede llamar
    elif method == "ping":
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {"status": "pong", "timestamp": datetime.now().isoformat()},
            "id": request_id
        })
    
    else:
        return create_mcp_response({
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
                "data": {
                    "supported_methods": [
                        "initialize", "initialized", "tools/list", "tools/call",
                        "resources/list", "prompts/list", "ping"
                    ]
                }
            },
            "id": request_id
        })

def handle_get_orders(args, request_id):
    """Manejar get_orders con mejor formato para Claude Desktop"""
    data = get_redash_data()
    
    if not data.get("success"):
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error retrieving orders data**\n\n**Error:** {data.get('error', 'Unknown error')}\n\n*Please check the Redash connection and try again.*"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    limit = min(args.get("limit", 10), 100)
    format_type = args.get("format", "summary")
    
    if isinstance(limit, int) and limit > 0:
        orders = orders[:limit]
    
    if format_type == "json":
        result_text = f"📊 **Orders Data** (JSON Format)\n\n**Records returned:** {len(orders)}\n\n```json\n{json.dumps(orders[:5], indent=2, ensure_ascii=False)}\n```"
        if len(orders) > 5:
            result_text += f"\n\n*Showing first 5 of {len(orders)} total records*"
    
    elif format_type == "detailed":
        result_text = f"📊 **Detailed Orders Report**\n\n**Total records:** {len(orders)}\n\n"
        for i, order in enumerate(orders[:10], 1):
            result_text += f"### Order #{i}\n"
            for key, value in order.items():
                result_text += f"- **{key}:** {value}\n"
            result_text += "\n"
        if len(orders) > 10:
            result_text += f"*... and {len(orders) - 10} more orders available*"
    
    else:  # summary
        result_text = f"📊 **Orders Summary**\n\n**Records retrieved:** {len(orders)}\n\n"
        if orders:
            for i, order in enumerate(orders[:5], 1):
                order_summary = []
                for key, value in list(order.items())[:3]:
                    order_summary.append(f"**{key}:** {value}")
                
                result_text += f"**{i}.** {' • '.join(order_summary)}\n"
            
            if len(orders) > 5:
                result_text += f"\n*... and {len(orders) - 5} more orders available*\n"
        
        metadata = data.get("metadata", {})
        result_text += f"\n---\n**📍 Source:** {metadata.get('source', 'Unknown')}\n"
        result_text += f"**🕐 Retrieved:** {metadata.get('retrieved_at', 'Unknown')}\n"
        result_text += f"**📊 Columns:** {len(metadata.get('columns', []))}"
    
    return create_mcp_response({
        "jsonrpc": "2.0",
        "result": {
            "content": [{
                "type": "text",
                "text": result_text
            }],
            "_meta": {
                "tool": "get_orders",
                "format": format_type,
                "count": len(orders),
                "timestamp": datetime.now().isoformat()
            }
        },
        "id": request_id
    })

def handle_get_orders_stats(request_id):
    """Manejar estadísticas de órdenes"""
    data = get_redash_data()
    
    if not data.get("success"):
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error retrieving statistics**\n\n**Error:** {data.get('error', 'Unknown error')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    metadata = data.get("metadata", {})
    
    result_text = f"📈 **Orders Database Statistics**\n\n"
    result_text += f"**📊 Total Records:** {len(orders):,}\n"
    result_text += f"**🏷️ Total Columns:** {len(metadata.get('columns', []))}\n"
    result_text += f"**🔗 Data Source:** {metadata.get('source', 'Unknown')}\n"
    result_text += f"**⏰ Last Updated:** {metadata.get('retrieved_at', 'Unknown')}\n\n"
    
    columns = metadata.get("columns", [])
    if columns:
        result_text += "**📋 Available Columns:**\n"
        for i, col in enumerate(columns, 1):
            result_text += f"{i}. `{col}`\n"
    
    if orders:
        result_text += f"\n**🔍 Sample Data Preview:**\n"
        sample_order = orders[0]
        for key, value in list(sample_order.items())[:5]:
            result_text += f"- **{key}:** `{value}` *({type(value).__name__})*\n"
        
        if len(sample_order) > 5:
            result_text += f"*... and {len(sample_order) - 5} more fields per record*\n"
    
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

def handle_search_orders(args, request_id):
    """Manejar búsqueda básica en órdenes"""
    query = args.get("query", "").lower()
    limit = min(args.get("limit", 10), 50)
    
    if not query:
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": "❌ **Search query required**\n\nPlease provide a search term to look for in the orders data."
                }]
            },
            "id": request_id
        })
    
    data = get_redash_data()
    if not data.get("success"):
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error searching orders**\n\n**Error:** {data.get('error', 'Unknown error')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    matching_orders = []
    
    # Búsqueda simple en todos los campos
    for order in orders:
        for key, value in order.items():
            if query in str(value).lower():
                matching_orders.append(order)
                break
        if len(matching_orders) >= limit:
            break
    
    result_text = f"🔍 **Search Results for:** `{args.get('query')}`\n\n"
    result_text += f"**Found:** {len(matching_orders)} matches (showing {min(len(matching_orders), limit)})\n\n"
    
    if matching_orders:
        for i, order in enumerate(matching_orders[:limit], 1):
            order_summary = []
            for key, value in list(order.items())[:3]:
                order_summary.append(f"**{key}:** {value}")
            result_text += f"**{i}.** {' • '.join(order_summary)}\n"
    else:
        result_text += "*No orders found matching your search criteria.*"
    
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
    """Health check específico para MCP"""
    return create_mcp_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "render",
        "auth_required": False,
        "mcp_protocol": "2024-11-05",
        "claude_desktop_compatible": True
    })

@app.route("/mcp-info")
def mcp_info():
    """Información específica del servidor MCP"""
    return create_mcp_response({
        "server_type": "MCP Server",
        "protocol_version": "2024-11-05",
        "capabilities": ["tools", "resources", "prompts"],
        "tools_available": ["get_orders", "get_orders_stats", "search_orders"],
        "claude_desktop_compatible": True,
        "status": "operational"
    })

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting MCP Server (Claude Desktop Compatible) on port {port}")
    print("📡 Enhanced MCP protocol support enabled")
    app.run(host='0.0.0.0', port=port, debug=False)
