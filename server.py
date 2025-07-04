import asyncio
import json
import logging
import os
import uuid

from aiohttp import web

logging.basicConfig(level=logging.INFO)
ROOT = os.path.dirname(__file__)

# Dicionário para armazenar os clientes conectados (websockets)
clients = {}

async def websocket_handler(request):
    """
    Manipula as conexões WebSocket para a sinalização.
    """
    client_id = str(uuid.uuid4())
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients[client_id] = ws
    logging.info(f"Cliente {client_id} conectado.")

    try:
        # Informa o novo cliente sobre os outros já conectados
        other_clients = [cid for cid in clients if cid != client_id]
        await ws.send_json({"type": "all_users", "users": other_clients})

        # Informa os outros clientes sobre o novo participante
        for cid, client_ws in clients.items():
            if cid != client_id:
                await client_ws.send_json({"type": "user_joined", "user_id": client_id})

        # Loop principal para receber e retransmitir mensagens
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                target_id = data.get("target")
                
                # Retransmite a mensagem para o cliente alvo
                if target_id and target_id in clients:
                    # Adiciona o ID do remetente para que o destinatário saiba quem enviou
                    data["sender"] = client_id
                    await clients[target_id].send_json(data)
                else:
                    logging.warning(f"Mensagem para alvo desconhecido: {target_id}")

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f"Erro no WebSocket do cliente {client_id}: {ws.exception()}")

    finally:
        # Limpeza quando um cliente se desconecta
        logging.info(f"Cliente {client_id} desconectado.")
        clients.pop(client_id, None)
        # Informa os clientes restantes que este saiu
        for client_ws in clients.values():
            await client_ws.send_json({"type": "user_left", "user_id": client_id})

    return ws

async def index(request):
    """Serve o ficheiro principal da aplicação (index.html)."""
    with open(os.path.join(ROOT, "index.html"), "r") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def favicon(request):
    """Serve uma resposta vazia para o favicon para evitar erros 404 no console."""
    return web.Response(status=204)

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    # Adiciona a rota para o favicon
    app.router.add_get("/favicon.ico", favicon)
    
    print("Servidor iniciado em http://localhost:8080")
    web.run_app(app, access_log=None, host="0.0.0.0", port=8080)
