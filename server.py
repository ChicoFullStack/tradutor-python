import asyncio
import json
import logging
import os
import uuid

from aiohttp import web

logging.basicConfig(level=logging.INFO)
ROOT = os.path.dirname(__file__)

# Dicionário para armazenar as salas e os seus clientes
# Estrutura: { "nome_da_sala": { "client_id": ws_socket, ... } }
rooms = {}

async def websocket_handler(request):
    """
    Manipula as conexões WebSocket, agora ciente das salas.
    """
    room_name = request.match_info.get("room_name", "geral")
    client_id = str(uuid.uuid4())
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Adiciona o cliente à sala
    if room_name not in rooms:
        rooms[room_name] = {}
    rooms[room_name][client_id] = ws
    logging.info(f"Cliente {client_id} conectado à sala '{room_name}'.")

    try:
        # Informa o novo cliente sobre os outros já na sala
        other_clients = [cid for cid in rooms[room_name] if cid != client_id]
        await ws.send_json({"type": "all_users", "users": other_clients})

        # Informa os outros clientes na sala sobre o novo participante
        for cid, client_ws in rooms[room_name].items():
            if cid != client_id:
                await client_ws.send_json({"type": "user_joined", "user_id": client_id})

        # Loop principal para receber e retransmitir mensagens dentro da sala
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                target_id = data.get("target")
                
                # Retransmite a mensagem para o cliente alvo na mesma sala
                if target_id and target_id in rooms[room_name]:
                    data["sender"] = client_id
                    await rooms[room_name][target_id].send_json(data)
                else:
                    logging.warning(f"Mensagem para alvo desconhecido '{target_id}' na sala '{room_name}'")

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f"Erro no WebSocket do cliente {client_id}: {ws.exception()}")

    finally:
        # Limpeza quando um cliente se desconecta
        logging.info(f"Cliente {client_id} desconectado da sala '{room_name}'.")
        if room_name in rooms:
            rooms[room_name].pop(client_id, None)
            # Informa os clientes restantes na sala que este saiu
            for client_ws in rooms[room_name].values():
                await client_ws.send_json({"type": "user_left", "user_id": client_id})
            
            # Se a sala ficar vazia, remove-a
            if not rooms[room_name]:
                logging.info(f"Sala '{room_name}' está vazia, a remover.")
                del rooms[room_name]

    return ws

async def index(request):
    """Serve o ficheiro principal da aplicação (index.html)."""
    with open(os.path.join(ROOT, "index.html"), "r") as f:
        return web.Response(text=f.read(), content_type="text/html")

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/", index)
    # A rota do WebSocket agora aceita um nome de sala
    app.router.add_get("/ws/{room_name}", websocket_handler)
    print("Servidor iniciado em http://localhost:8080")
    web.run_app(app, access_log=None, host="0.0.0.0", port=8080)
