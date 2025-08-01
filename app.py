# 🚀 MCP Server para Render.com - Versión de deploy
import os
import json
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, make_response, redirect
from flask_cors import CORS
from urllib.parse import urlencode
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# CORS configurado para Claude
CORS(app, 
     origins=["https://claude.ai", "https://claude.com", "*"],
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
     supports_credentials=True)

# Storage en memoria (en producción usarías una base de datos)
data_cache = None
cache_time = None
oauth_clients = {}
auth_codes = {}
access_tokens = {}

def get_redash_data():
    """Obtener datos de Redash"""
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

def verify_token(token):
    """Verificar token de acceso"""
    if not token or token not in access_tokens:
        return False
    token_data = access_tokens[token]
    if datetime.now() > token_data['expires']:
        del access_tokens[token]
        return False
    return True

# OAuth Well-Known Endpoints
@app.route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
def oauth_authorization_server():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    base_url = request.url_root.rstrip('/')
    return create_json_response({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "scopes_supported": ["read", "mcp", "orders"]
    })

@app.route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
def oauth_protected_resource():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    base_url = request.url_root.rstrip('/')
    return create_json_response({
        "resource": base_url,
        "authorization_servers": [f"{base_url}/.well-known/oauth-authorization-server"],
        "scopes_supported": ["read", "mcp", "orders"],
        "bearer_methods_supported": ["header"]
    })

# Dynamic Client Registration
@app.route("/register", methods=["GET", "POST", "OPTIONS"])
def register_client():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    if request.method == "GET":
        base_url = request.url_root.rstrip('/')
        return create_json_response({
            "registration_endpoint": f"{base_url}/register",
            "grant_types_supported": ["authorization_code"],
            "response_types_supported": ["code"]
        })
    
    try:
        client_metadata = request.get_json() or {}
        
        client_id = f"claude_client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)
        
        redirect_uris = client_metadata.get("redirect_uris", [
            "https://claude.ai/api/mcp/auth_callback",
            "https://claude.com/api/mcp/auth_callback"
        ])
        
        oauth_clients[client_id] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_metadata.get("client_name", "Claude MCP Client"),
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": "read mcp orders"
        }
        
        return create_json_response({
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": oauth_clients[client_id]["client_name"],
            "redirect_uris": redirect_uris,
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": "read mcp orders"
        }, 201)
        
    except Exception as e:
        return create_json_response({
            "error": "invalid_request",
            "error_description": str(e)
        }, 400)

# OAuth Authorization
@app.route("/oauth/authorize", methods=["GET", "OPTIONS"])
def oauth_authorize():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    try:
        client_id = request.args.get('client_id')
        redirect_uri = request.args.get('redirect_uri')
        response_type = request.args.get('response_type', 'code')
        scope = request.args.get('scope', 'read')
        state = request.args.get('state')
        
        if not client_id or client_id not in oauth_clients:
            error_params = {"error": "invalid_client"}
            if state:
                error_params["state"] = state
            return redirect(f"{redirect_uri}?{urlencode(error_params)}")
        
        client = oauth_clients[client_id]
        
        if redirect_uri not in client['redirect_uris']:
            return create_json_response({
                "error": "invalid_request",
                "error_description": "Invalid redirect URI"
            }, 400)
        
        if response_type != 'code':
            error_params = {"error": "unsupported_response_type"}
            if state:
                error_params["state"] = state
            return redirect(f"{redirect_uri}?{urlencode(error_params)}")
        
        auth_code = secrets.token_urlsafe(32)
        auth_codes[auth_code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "expires": datetime.now() + timedelta(minutes=10),
            "used": False
        }
        
        callback_params = {"code": auth_code}
        if state:
            callback_params["state"] = state
        
        return redirect(f"{redirect_uri}?{urlencode(callback_params)}")
        
    except Exception as e:
        error_params = {"error": "server_error"}
        if 'state' in locals() and state:
            error_params["state"] = state
        return redirect(f"{redirect_uri}?{urlencode(error_params)}")

# OAuth Token
@app.route("/oauth/token", methods=["POST", "OPTIONS"])
def oauth_token():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    try:
        if request.content_type == 'application/json':
            data = request.get_json() or {}
        else:
            data = request.form.to_dict()
        
        grant_type = data.get('grant_type')
        code = data.get('code')
        client_id = data.get('client_id')
        
        if grant_type != 'authorization_code':
            return create_json_response({
                "error": "unsupported_grant_type"
            }, 400)
        
        if not code or code not in auth_codes:
            return create_json_response({
                "error": "invalid_grant"
            }, 400)
        
        auth_data = auth_codes[code]
        
        if datetime.now() > auth_data['expires'] or auth_data['used']:
            del auth_codes[code]
            return create_json_response({
                "error": "invalid_grant"
            }, 400)
        
        if auth_data['client_id'] != client_id:
            return create_json_response({
                "error": "invalid_client"
            }, 400)
        
        auth_codes[code]['used'] = True
        
        access_token = secrets.token_urlsafe(32)
        access_tokens[access_token] = {
            "client_id": client_id,
            "scope": auth_data['scope'],
            "expires": datetime.now() + timedelta(hours=24)
        }
        
        return create_json_response({
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 86400,
            "scope": auth_data['scope']
        })
        
    except Exception as e:
        return create_json_response({
            "error": "server_error"
        }, 500)

# Main MCP endpoint
@app.route("/", methods=["GET", "POST", "OPTIONS"])
def mcp_endpoint():
    if request.method == "OPTIONS":
        return create_json_response({})
    
    if request.method == "POST":
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return create_json_response({
                "error": "invalid_token",
                "error_description": "Missing or invalid access token"
            }, 401)
        
        token = auth_header[7:]
        if not verify_token(token):
            return create_json_response({
                "error": "invalid_token",
                "error_description": "Token expired or invalid"
            }, 401)
        
        try:
            rpc_request = request.get_json()
            return handle_mcp_request(rpc_request)
        except Exception as e:
            return create_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": "Internal error"},
                "id": None
            }, 500)
    
    # GET - server info
    base_url = request.url_root.rstrip('/')
    return create_json_response({
        "name": "Redash Orders MCP Server",
        "version": "1.0.0",
        "description": "MCP server for Redash orders data",
        "protocol": "Model Context Protocol v2024-11-05",
        "auth": {
            "type": "oauth2",
            "required": True,
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": f"{base_url}/oauth/authorize",
                    "tokenUrl": f"{base_url}/oauth/token"
                }
            }
        }
    })

def handle_mcp_request(rpc_request):
    """Handle MCP JSON-RPC requests"""
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
                "tools": [{
                    "name": "get_orders",
                    "description": "Get orders data from Redash",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of orders"
                            }
                        }
                    }
                }]
            },
            "id": request_id
        })
    
    elif method == "tools/call":
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "get_orders":
            data = get_redash_data()
            limit = args.get("limit", 10)
            
            orders = data.get("data", [])
            if isinstance(limit, int):
                orders = orders[:limit]
            
            result_text = f"📊 Orders Data ({len(orders)} records)\n\n"
            for i, order in enumerate(orders[:5], 1):
                result_text += f"{i}. {order}\n"
            
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
    
    return create_json_response({
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": request_id
    })

@app.route("/health")
def health():
    return create_json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "environment": "render"
    })

if __name__ == "__main__":
    import time
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
