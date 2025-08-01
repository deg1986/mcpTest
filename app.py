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

def clean_value(value):
    """Limpiar y convertir valores para evitar errores de validación"""
    if value is None:
        return ""
    if isinstance(value, (int, float)) and (value != value):  # NaN check
        return 0
    if isinstance(value, str):
        return value.strip()
    return str(value)

def get_redash_data():
    """Obtener datos de Redash con cache y limpieza de datos"""
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
        
        # Limpiar nombres de columnas
        column_names = []
        for i, col in enumerate(columns):
            if isinstance(col, dict):
                name = col.get('name', f'col_{i}')
            else:
                name = str(col) if col is not None else f'col_{i}'
            # Limpiar nombre de columna
            name = name.strip().replace(' ', '_').replace('-', '_')
            if not name:
                name = f'col_{i}'
            column_names.append(name)
        
        # Procesar y limpiar datos
        processed_data = []
        for row_idx, row in enumerate(rows):
            if not isinstance(row, (list, tuple)):
                continue
                
            row_dict = {}
            for i, value in enumerate(row):
                if i < len(column_names):
                    column_name = column_names[i]
                    cleaned_value = clean_value(value)
                    row_dict[column_name] = cleaned_value
            
            # Solo agregar filas que tengan al menos un valor no vacío
            if any(str(v).strip() for v in row_dict.values() if v):
                processed_data.append(row_dict)
        
        result = {
            "success": True,
            "data": processed_data,
            "metadata": {
                "total_records": len(processed_data),
                "columns": column_names,
                "source": "Redash Query 3654",
                "retrieved_at": datetime.now().isoformat(),
                "data_cleaned": True
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
    """Manejar get_orders con validación estricta para Claude Desktop"""
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
    
    # Validar y limpiar argumentos
    try:
        limit = int(args.get("limit", 10))
        limit = max(1, min(limit, 100))  # Entre 1 y 100
    except (ValueError, TypeError):
        limit = 10
    
    format_type = args.get("format", "summary")
    if format_type not in ["summary", "detailed", "json"]:
        format_type = "summary"
    
    # Aplicar límite de forma segura
    orders = orders[:limit] if orders else []
    
    try:
        if format_type == "json":
            # Validar que los datos son serializables
            sample_data = orders[:5] if orders else []
            json_str = json.dumps(sample_data, indent=2, ensure_ascii=False, default=str)
            
            result_text = f"📊 **Orders Data** (JSON Format)\n\n**Records returned:** {len(orders)}\n\n```json\n{json_str}\n```"
            if len(orders) > 5:
                result_text += f"\n\n*Showing first 5 of {len(orders)} total records*"
        
        elif format_type == "detailed":
            result_text = f"📊 **Detailed Orders Report**\n\n**Total records:** {len(orders)}\n\n"
            
            for i, order in enumerate(orders[:10], 1):
                if not isinstance(order, dict):
                    continue
                    
                result_text += f"### Order #{i}\n"
                for key, value in order.items():
                    # Asegurar que key y value son strings válidos
                    safe_key = str(key) if key is not None else "unknown_field"
                    safe_value = str(value) if value is not None else "N/A"
                    result_text += f"- **{safe_key}:** {safe_value}\n"
                result_text += "\n"
                
            if len(orders) > 10:
                result_text += f"*... and {len(orders) - 10} more orders available*"
        
        else:  # summary
            result_text = f"📊 **Orders Summary**\n\n**Records retrieved:** {len(orders)}\n\n"
            
            if orders:
                for i, order in enumerate(orders[:5], 1):
                    if not isinstance(order, dict):
                        continue
                        
                    order_summary = []
                    order_items = list(order.items())[:3]  # Primeros 3 campos
                    
                    for key, value in order_items:
                        safe_key = str(key) if key is not None else "field"
                        safe_value = str(value) if value is not None else "N/A"
                        # Truncar valores muy largos
                        if len(safe_value) > 50:
                            safe_value = safe_value[:47] + "..."
                        order_summary.append(f"**{safe_key}:** {safe_value}")
                    
                    if order_summary:
                        result_text += f"**{i}.** {' • '.join(order_summary)}\n"
                
                if len(orders) > 5:
                    result_text += f"\n*... and {len(orders) - 5} more orders available*\n"
            
            # Metadata segura
            metadata = data.get("metadata", {})
            result_text += f"\n---\n**📍 Source:** {metadata.get('source', 'Unknown')}\n"
            result_text += f"**🕐 Retrieved:** {metadata.get('retrieved_at', 'Unknown')}\n"
            result_text += f"**📊 Columns:** {len(metadata.get('columns', []))}"
    
    except Exception as e:
        # Fallback en caso de error de formateo
        result_text = f"📊 **Orders Data**\n\n**Records found:** {len(orders)}\n\n*Data retrieved successfully but encountered formatting issues. Raw data available via JSON format.*\n\n**Error:** {str(e)}"
    
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
    """Manejar estadísticas con validación robusta"""
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
    
    try:
        result_text = f"📈 **Orders Database Statistics**\n\n"
        result_text += f"**📊 Total Records:** {len(orders):,}\n"
        
        columns = metadata.get("columns", [])
        result_text += f"**🏷️ Total Columns:** {len(columns)}\n"
        result_text += f"**🔗 Data Source:** {metadata.get('source', 'Unknown')}\n"
        result_text += f"**⏰ Last Updated:** {metadata.get('retrieved_at', 'Unknown')}\n"
        
        if metadata.get('data_cleaned'):
            result_text += f"**✅ Data Status:** Cleaned and validated\n"
        
        result_text += "\n"
        
        if columns:
            result_text += "**📋 Available Columns:**\n"
            for i, col in enumerate(columns[:20], 1):  # Limitar a 20 columnas
                safe_col = str(col) if col is not None else f"column_{i}"
                result_text += f"{i}. `{safe_col}`\n"
            
            if len(columns) > 20:
                result_text += f"*... and {len(columns) - 20} more columns*\n"
        
        if orders and isinstance(orders[0], dict):
            result_text += f"\n**🔍 Sample Data Preview:**\n"
            sample_order = orders[0]
            sample_items = list(sample_order.items())[:5]
            
            for key, value in sample_items:
                safe_key = str(key) if key is not None else "unknown"
                safe_value = str(value) if value is not None else "N/A"
                value_type = type(value).__name__
                
                # Truncar valores largos
                if len(safe_value) > 100:
                    safe_value = safe_value[:97] + "..."
                
                result_text += f"- **{safe_key}:** `{safe_value}` *({value_type})*\n"
            
            if len(sample_order) > 5:
                result_text += f"*... and {len(sample_order) - 5} more fields per record*\n"
    
    except Exception as e:
        result_text = f"📈 **Orders Database Statistics**\n\n**Records:** {len(orders)}\n**Status:** Data available but stats generation failed\n**Error:** {str(e)}"
    
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
    """Manejar búsqueda con validación mejorada"""
    try:
        query = str(args.get("query", "")).lower().strip()
        limit = int(args.get("limit", 10))
        limit = max(1, min(limit, 50))  # Entre 1 y 50
    except (ValueError, TypeError):
        limit = 10
        query = ""
    
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
    
    try:
        # Búsqueda segura en todos los campos
        for order in orders:
            if not isinstance(order, dict):
                continue
                
            found_match = False
            for key, value in order.items():
                try:
                    if query in str(value).lower():
                        matching_orders.append(order)
                        found_match = True
                        break
                except:
                    continue  # Skip problematic values
            
            if found_match and len(matching_orders) >= limit:
                break
        
        result_text = f"🔍 **Search Results for:** `{args.get('query')}`\n\n"
        result_text += f"**Found:** {len(matching_orders)} matches (showing {min(len(matching_orders), limit)})\n\n"
        
        if matching_orders:
            for i, order in enumerate(matching_orders[:limit], 1):
                order_summary = []
                order_items = list(order.items())[:3]
                
                for key, value in order_items:
                    safe_key = str(key) if key is not None else "field"
                    safe_value = str(value) if value is not None else "N/A"
                    if len(safe_value) > 50:
                        safe_value = safe_value[:47] + "..."
                    order_summary.append(f"**{safe_key}:** {safe_value}")
                
                if order_summary:
                    result_text += f"**{i}.** {' • '.join(order_summary)}\n"
        else:
            result_text += "*No orders found matching your search criteria.*"
    
    except Exception as e:
        result_text = f"🔍 **Search Error**\n\n**Query:** `{args.get('query')}`\n**Error:** {str(e)}"
    
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
