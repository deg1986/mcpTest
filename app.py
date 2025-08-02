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
    
    # Cache por 5 minutos
    if data_cache and cache_time and (time.time() - cache_time) < 300:
        print("📦 Using cached data")
        return data_cache
    
    try:
        print("🔄 Fetching fresh data from Redash...")
        url = "https://redash-devops.farmuhub.co/api/queries/3654/results.json?api_key=KoRPiEdAKlWuqPk7UVwtFWmjeIEkjlQPZ2kzsG3H"
        
        headers = {
            'User-Agent': 'MCP-Server/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, timeout=30, headers=headers)
        print(f"📡 Redash response status: {response.status_code}")
        
        response.raise_for_status()
        
        raw_data = response.json()
        print(f"📊 Raw data structure: {list(raw_data.keys())}")
        
        # Extraer datos anidados correctamente
        query_result = raw_data.get("query_result", {})
        data_section = query_result.get("data", {})
        rows = data_section.get("rows", [])
        columns = data_section.get("columns", [])
        
        print(f"📈 Found {len(rows)} rows and {len(columns)} columns")
        
        if not rows:
            print("⚠️ No rows found in response")
            return {
                "success": False, 
                "error": "No data found in Redash response",
                "data": [],
                "debug_info": {
                    "raw_keys": list(raw_data.keys()),
                    "query_result_keys": list(query_result.keys()) if query_result else [],
                    "data_keys": list(data_section.keys()) if data_section else []
                }
            }
        
        # Procesar nombres de columnas
        column_names = []
        for i, col in enumerate(columns):
            if isinstance(col, dict):
                name = col.get('name', f'column_{i}')
            else:
                name = str(col) if col is not None else f'column_{i}'
            
            # Limpiar nombre de columna
            name = name.strip().replace(' ', '_').replace('-', '_').lower()
            if not name or name == '_':
                name = f'column_{i}'
            column_names.append(name)
        
        print(f"📋 Column names: {column_names}")
        
        # Procesar filas
        processed_data = []
        for row_idx, row in enumerate(rows):
            if not isinstance(row, (list, tuple)):
                print(f"⚠️ Skipping invalid row {row_idx}: {type(row)}")
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
                "data_cleaned": True,
                "query_id": "3654"
            }
        }
        
        print(f"✅ Successfully processed {len(processed_data)} orders")
        
        # Actualizar cache
        data_cache = result
        cache_time = time.time()
        return result
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error connecting to Redash: {str(e)}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg, "data": []}
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response from Redash: {str(e)}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg, "data": []}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg, "data": []}

def create_mcp_response(data, status=200):
    """Crear respuesta MCP con headers específicos para Claude Desktop"""
    response = make_response(jsonify(data), status)
    response.headers.update({
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': '*',
        'Cache-Control': 'no-cache',
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

@app.route("/", methods=["GET", "POST", "OPTIONS"])
def mcp_endpoint():
    """Endpoint principal optimizado para Claude Desktop MCP"""
    
    if request.method == "OPTIONS":
        return create_mcp_response({})
    
    if request.method == "GET":
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
    """Manejar peticiones JSON-RPC del protocolo MCP"""
    method = rpc_request.get('method')
    params = rpc_request.get('params', {})
    request_id = rpc_request.get('id')
    
    if method == "initialize":
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
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
                }
            },
            "id": request_id
        })
    
    elif method == "initialized":
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
                        "name": "list_orders",
                        "description": "Retrieve all orders from Redash database with optional limit and format options.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of orders to return (default: 20, max: 100)",
                                    "default": 20,
                                    "minimum": 1,
                                    "maximum": 100
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["summary", "detailed", "json"],
                                    "description": "Output format - summary: key fields only, detailed: all fields, json: raw data",
                                    "default": "summary"
                                }
                            },
                            "additionalProperties": False
                        }
                    },
                    {
                        "name": "search_orders_by_number",
                        "description": "Search for orders by order number. Supports exact match and partial search.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "order_number": {
                                    "type": "string",
                                    "description": "Order number to search for (can be partial)"
                                },
                                "exact_match": {
                                    "type": "boolean",
                                    "description": "Whether to use exact match (true) or partial search (false)",
                                    "default": False
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum results to return",
                                    "default": 10,
                                    "minimum": 1,
                                    "maximum": 50
                                }
                            },
                            "required": ["order_number"],
                            "additionalProperties": False
                        }
                    },
                    {
                        "name": "search_orders_by_email",
                        "description": "Search for orders by customer email address. Supports exact match and partial search.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "email": {
                                    "type": "string",
                                    "description": "Email address to search for (can be partial)"
                                },
                                "exact_match": {
                                    "type": "boolean",
                                    "description": "Whether to use exact match (true) or partial search (false)",
                                    "default": False
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum results to return",
                                    "default": 10,
                                    "minimum": 1,
                                    "maximum": 50
                                }
                            },
                            "required": ["email"],
                            "additionalProperties": False
                        }
                    },
                    {
                        "name": "get_orders_stats",
                        "description": "Get statistical overview and metadata about the orders database.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
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
        
        if tool_name == "list_orders":
            return handle_list_orders(args, request_id)
        elif tool_name == "search_orders_by_number":
            return handle_search_by_order_number(args, request_id)
        elif tool_name == "search_orders_by_email":
            return handle_search_by_email(args, request_id)
        elif tool_name == "get_orders_stats":
            return handle_get_orders_stats(request_id)
        else:
            return create_mcp_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                    "data": {"available_tools": ["list_orders", "search_orders_by_number", "search_orders_by_email", "get_orders_stats"]}
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

def format_order_summary(order, index=None):
    """Formatear orden para vista resumida"""
    summary_parts = []
    
    # Buscar campos comunes de orden
    order_fields = {
        'order_number': ['order_number', 'order_id', 'number', 'id'],
        'email': ['email', 'customer_email', 'user_email', 'client_email'],
        'customer': ['customer', 'customer_name', 'client', 'client_name', 'name'],
        'status': ['status', 'order_status', 'state'],
        'total': ['total', 'amount', 'total_amount', 'price'],
        'date': ['date', 'created_at', 'order_date', 'created']
    }
    
    found_fields = {}
    for field_type, possible_names in order_fields.items():
        for name in possible_names:
            if name in order:
                found_fields[field_type] = str(order[name])
                break
    
    # Construir resumen
    if 'order_number' in found_fields:
        summary_parts.append(f"**Orden:** {found_fields['order_number']}")
    
    if 'email' in found_fields:
        summary_parts.append(f"**Email:** {found_fields['email']}")
    
    if 'customer' in found_fields:
        summary_parts.append(f"**Cliente:** {found_fields['customer']}")
    
    if 'status' in found_fields:
        summary_parts.append(f"**Estado:** {found_fields['status']}")
    
    if 'total' in found_fields:
        summary_parts.append(f"**Total:** {found_fields['total']}")
    
    if 'date' in found_fields:
        summary_parts.append(f"**Fecha:** {found_fields['date']}")
    
    # Si no encontramos campos específicos, usar los primeros 3 campos
    if not summary_parts:
        items = list(order.items())[:3]
        for key, value in items:
            if value and str(value).strip():
                safe_value = str(value)[:50] + ("..." if len(str(value)) > 50 else "")
                summary_parts.append(f"**{key}:** {safe_value}")
    
    prefix = f"**{index}.** " if index else ""
    return prefix + " • ".join(summary_parts) if summary_parts else f"{prefix}*Orden sin datos válidos*"

def handle_list_orders(args, request_id):
    """Listar órdenes con formato mejorado"""
    data = get_redash_data()
    
    if not data.get("success"):
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error al obtener órdenes**\n\n**Error:** {data.get('error', 'Error desconocido')}\n\n*Información de debug:*\n```json\n{json.dumps(data.get('debug_info', {}), indent=2)}\n```"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    
    # Validar argumentos
    try:
        limit = int(args.get("limit", 20))
        limit = max(1, min(limit, 100))
    except (ValueError, TypeError):
        limit = 20
    
    format_type = args.get("format", "summary")
    if format_type not in ["summary", "detailed", "json"]:
        format_type = "summary"
    
    # Aplicar límite
    limited_orders = orders[:limit] if orders else []
    
    try:
        if format_type == "json":
            json_str = json.dumps(limited_orders, indent=2, ensure_ascii=False, default=str)
            result_text = f"📊 **Órdenes en formato JSON**\n\n**Registros devueltos:** {len(limited_orders)} de {len(orders)} totales\n\n```json\n{json_str}\n```"
        
        elif format_type == "detailed":
            result_text = f"📊 **Listado Detallado de Órdenes**\n\n**Total de órdenes:** {len(orders)}\n**Mostrando:** {len(limited_orders)}\n\n"
            
            for i, order in enumerate(limited_orders, 1):
                if not isinstance(order, dict):
                    continue
                    
                result_text += f"### 📦 Orden #{i}\n"
                for key, value in order.items():
                    safe_key = str(key) if key is not None else "campo_desconocido"
                    safe_value = str(value) if value is not None else "N/A"
                    result_text += f"- **{safe_key}:** {safe_value}\n"
                result_text += "\n"
        
        else:  # summary
            result_text = f"📋 **Lista de Órdenes**\n\n**Total encontradas:** {len(orders)}\n**Mostrando:** {len(limited_orders)}\n\n"
            
            if limited_orders:
                for i, order in enumerate(limited_orders, 1):
                    if isinstance(order, dict):
                        result_text += format_order_summary(order, i) + "\n"
            else:
                result_text += "*No se encontraron órdenes.*\n"
            
            # Información adicional
            metadata = data.get("metadata", {})
            result_text += f"\n---\n"
            result_text += f"**📍 Fuente:** {metadata.get('source', 'Desconocida')}\n"
            result_text += f"**🕐 Actualizado:** {metadata.get('retrieved_at', 'Desconocido')}\n"
            result_text += f"**📊 Columnas disponibles:** {len(metadata.get('columns', []))}"
    
    except Exception as e:
        result_text = f"📊 **Lista de Órdenes**\n\n**Error de formato:** {str(e)}\n**Órdenes encontradas:** {len(orders)}\n\n*Los datos están disponibles pero hubo un problema al formatearlos. Intenta con formato 'json'.*"
    
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

def handle_search_by_order_number(args, request_id):
    """Buscar órdenes por número de orden"""
    try:
        order_number = str(args.get("order_number", "")).strip()
        exact_match = bool(args.get("exact_match", False))
        limit = int(args.get("limit", 10))
        limit = max(1, min(limit, 50))
    except (ValueError, TypeError):
        limit = 10
        exact_match = False
        order_number = ""
    
    if not order_number:
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": "❌ **Número de orden requerido**\n\nPor favor proporciona un número de orden para buscar."
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
                    "text": f"❌ **Error al buscar órdenes**\n\n**Error:** {data.get('error', 'Error desconocido')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    matching_orders = []
    
    # Campos posibles para número de orden
    order_number_fields = ['order_number', 'order_id', 'number', 'id', 'order', 'orderid']
    
    try:
        search_term = order_number.lower()
        for order in orders:
            if not isinstance(order, dict):
                continue
                
            found_match = False
            for field in order_number_fields:
                if field in order:
                    field_value = str(order[field]).lower()
                    
                    if exact_match:
                        if field_value == search_term:
                            matching_orders.append(order)
                            found_match = True
                            break
                    else:
                        if search_term in field_value:
                            matching_orders.append(order)
                            found_match = True
                            break
            
            if found_match and len(matching_orders) >= limit:
                break
        
        match_type = "exacta" if exact_match else "parcial"
        result_text = f"🔍 **Búsqueda por Número de Orden**\n\n"
        result_text += f"**Término:** `{order_number}` (búsqueda {match_type})\n"
        result_text += f"**Encontradas:** {len(matching_orders)} órdenes\n\n"
        
        if matching_orders:
            for i, order in enumerate(matching_orders[:limit], 1):
                result_text += format_order_summary(order, i) + "\n"
                
            if len(matching_orders) > limit:
                result_text += f"\n*... y {len(matching_orders) - limit} órdenes más*\n"
        else:
            result_text += f"*No se encontraron órdenes con el número '{order_number}'.*\n"
            result_text += f"\n**Sugerencia:** Intenta con búsqueda parcial (exact_match: false) o verifica el número de orden."
    
    except Exception as e:
        result_text = f"🔍 **Error en Búsqueda**\n\n**Término:** `{order_number}`\n**Error:** {str(e)}"
    
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

def handle_search_by_email(args, request_id):
    """Buscar órdenes por email del cliente"""
    try:
        email = str(args.get("email", "")).strip().lower()
        exact_match = bool(args.get("exact_match", False))
        limit = int(args.get("limit", 10))
        limit = max(1, min(limit, 50))
    except (ValueError, TypeError):
        limit = 10
        exact_match = False
        email = ""
    
    if not email:
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": "❌ **Email requerido**\n\nPor favor proporciona un email para buscar órdenes."
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
                    "text": f"❌ **Error al buscar órdenes**\n\n**Error:** {data.get('error', 'Error desconocido')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    matching_orders = []
    
    # Campos posibles para email
    email_fields = ['email', 'customer_email', 'user_email', 'client_email', 'mail', 'customer_mail']
    
    try:
        for order in orders:
            if not isinstance(order, dict):
                continue
                
            found_match = False
            for field in email_fields:
                if field in order:
                    field_value = str(order[field]).lower().strip()
                    
                    if exact_match:
                        if field_value == email:
                            matching_orders.append(order)
                            found_match = True
                            break
                    else:
                        if email in field_value:
                            matching_orders.append(order)
                            found_match = True
                            break
            
            if found_match and len(matching_orders) >= limit:
                break
        
        match_type = "exacta" if exact_match else "parcial"
        result_text = f"📧 **Búsqueda por Email**\n\n"
        result_text += f"**Email:** `{args.get('email')}` (búsqueda {match_type})\n"
        result_text += f"**Encontradas:** {len(matching_orders)} órdenes\n\n"
        
        if matching_orders:
            for i, order in enumerate(matching_orders[:limit], 1):
                result_text += format_order_summary(order, i) + "\n"
                
            if len(matching_orders) > limit:
                result_text += f"\n*... y {len(matching_orders) - limit} órdenes más*\n"
        else:
            result_text += f"*No se encontraron órdenes para el email '{args.get('email')}'.*\n"
            result_text += f"\n**Sugerencia:** Intenta con búsqueda parcial (exact_match: false) o verifica el email."
    
    except Exception as e:
        result_text = f"📧 **Error en Búsqueda**\n\n**Email:** `{args.get('email')}`\n**Error:** {str(e)}"
    
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
    """Obtener estadísticas de las órdenes"""
    data = get_redash_data()
    
    if not data.get("success"):
        return create_mcp_response({
            "jsonrpc": "2.0",
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"❌ **Error al obtener estadísticas**\n\n**Error:** {data.get('error', 'Error desconocido')}"
                }]
            },
            "id": request_id
        })
    
    orders = data.get("data", [])
    metadata = data.get("metadata", {})
    
    try:
        result_text = f"📈 **Estadísticas de la Base de Datos de Órdenes**\n\n"
        result_text += f"**📊 Total de Registros:** {len(orders):,}\n"
        
        columns = metadata.get("columns", [])
        result_text += f"**🏷️ Total de Columnas:** {len(columns)}\n"
        result_text += f"**🔗 Fuente de Datos:** {metadata.get('source', 'Desconocida')}\n"
        result_text += f"**⏰ Última Actualización:** {metadata.get('retrieved_at', 'Desconocida')}\n"
        
        if metadata.get('data_cleaned'):
            result_text += f"**✅ Estado de Datos:** Limpiados y validados\n"
        
        result_text += "\n"
        
        if columns:
            result_text += "**📋 Columnas Disponibles:**\n"
            for i, col in enumerate(columns[:20], 1):
                safe_col = str(col) if col is not None else f"columna_{i}"
                result_text += f"{i}. `{safe_col}`\n"
            
            if len(columns) > 20:
                result_text += f"*... y {len(columns) - 20} columnas más*\n"
        
        if orders and isinstance(orders[0], dict):
            result_text += f"\n**🔍 Vista Previa de Datos:**\n"
            sample_order = orders[0]
            sample_items = list(sample_order.items())[:5]
            
            for key, value in sample_items:
                safe_key = str(key) if key is not None else "desconocido"
                safe_value = str(value) if value is not None else "N/A"
                value_type = type(value).__name__
                
                if len(safe_value) > 100:
                    safe_value = safe_value[:97] + "..."
                
                result_text += f"- **{safe_key}:** `{safe_value}` *({value_type})*\n"
            
            if len(sample_order) > 5:
                result_text += f"*... y {len(sample_order) - 5} campos más por registro*\n"
    
    except Exception as e:
        result_text = f"📈 **Estadísticas de Órdenes**\n\n**Registros:** {len(orders)}\n**Estado:** Datos disponibles pero falló la generación de estadísticas\n**Error:** {str(e)}"
    
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
        "tools_available": ["list_orders", "search_orders_by_number", "search_orders_by_email", "get_orders_stats"],
        "claude_desktop_compatible": True,
        "status": "operational"
    })

@app.route("/test-redash")
def test_redash():
    """Endpoint para probar la conexión con Redash directamente"""
    data = get_redash_data()
    return create_mcp_response(data)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting MCP Server (Claude Desktop Compatible) on port {port}")
    print("📡 Enhanced MCP protocol support enabled")
    print("🔧 Available tools: list_orders, search_orders_by_number, search_orders_by_email, get_orders_stats")
    app.run(host='0.0.0.0', port=port, debug=False)
