# server.py
#
# SERVIDOR WEB PARA VIDEOCHAMADA MULTI-SALA
# Este servidor gere múltiplas salas de chamada independentes.

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from aiohttp import web

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)

# ESTRUTURA DE DADOS PARA AS SALAS:
# ROOMS = {
#   'room_id_1': {client_ws_1, client_ws_2},
#   'room_id_2': {client_ws_3}
# }
# CLIENTS = {
#   client_ws_1: {'room_id': 'room_id_1', 'user_id': 'user_1'},
#   client_ws_2: {'room_id': 'room_id_1', 'user_id': 'user_2'}
# }
ROOMS = defaultdict(set)
CLIENTS = {}

# O tradutor continua a ser global
from googletrans import Translator
translator = Translator()

async def handle_translation(data):
    """Lida com o pedido de tradução."""
    try:
        text_to_translate = data.get('text')
        source_lang = data.get('source_lang', 'pt').split('-')[0]
        dest_lang = data.get('dest_lang', 'en').split('-')[0]
        if not text_to_translate:
            return None
        translated = translator.translate(text_to_translate, src=source_lang, dest=dest_lang)
        return translated.text
    except Exception as e:
        logging.error(f"Erro na tradução: {e}")
        return "[Erro na tradução]"

async def broadcast(room_id, message, exclude_ws):
    """Envia uma mensagem para todos os clientes numa sala, exceto um."""
    if room_id in ROOMS:
        for ws in ROOMS[room_id]:
            if ws != exclude_ws:
                await ws.send_json(message)

async def websocket_handler(request):
    """Lida com as conexões WebSocket para sinalização, chat e gestão de salas."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    logging.info(f"Nova conexão WebSocket estabelecida.")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')

                    if msg_type == 'join':
                        room_id = data['room_id']
                        user_id = data['user_id']
                        
                        # Adiciona o cliente à sala
                        ROOMS[room_id].add(ws)
                        CLIENTS[ws] = {'room_id': room_id, 'user_id': user_id}
                        
                        logging.info(f"Utilizador {user_id} entrou na sala {room_id}. Participantes: {len(ROOMS[room_id])}")

                        # Notifica os outros utilizadores na sala sobre o novo participante
                        join_message = {'type': 'user-joined', 'user_id': user_id}
                        await broadcast(room_id, join_message, ws)

                    elif msg_type in ['offer', 'answer', 'candidate']:
                        # Retransmite mensagens de sinalização WebRTC para o utilizador alvo
                        target_id = data.get('target_id')
                        # Encontra o websocket do alvo
                        target_ws = None
                        for client_ws, client_info in CLIENTS.items():
                            if client_info.get('user_id') == target_id:
                                target_ws = client_ws
                                break
                        
                        if target_ws:
                            await target_ws.send_json(data)
                        else:
                            logging.warning(f"Sinalização: Utilizador alvo {target_id} não encontrado.")

                    elif msg_type == 'translate':
                        # Lida com a tradução e envia para a sala
                        client_info = CLIENTS.get(ws, {})
                        room_id = client_info.get('room_id')
                        if room_id:
                            translated_text = await handle_translation(data)
                            if translated_text:
                                response = {
                                    'type': 'translation', 
                                    'user_id': data.get('user_id'),
                                    'original': data.get('text'),
                                    'translated': translated_text
                                }
                                await broadcast(room_id, response, None) # Envia para todos, incluindo quem falou

                except Exception as e:
                    logging.error(f"Erro ao processar mensagem: {e}")

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f'Conexão WebSocket fechada com exceção {ws.exception()}')

    finally:
        # Lógica de limpeza quando um cliente se desconecta
        if ws in CLIENTS:
            client_info = CLIENTS[ws]
            room_id = client_info['room_id']
            user_id = client_info['user_id']
            
            ROOMS[room_id].remove(ws)
            del CLIENTS[ws]
            
            logging.info(f"Utilizador {user_id} saiu da sala {room_id}. Participantes restantes: {len(ROOMS[room_id])}")
            
            # Notifica os restantes que o utilizador saiu
            await broadcast(room_id, {'type': 'user-left', 'user_id': user_id}, ws)

            # Se a sala ficar vazia, remove-a
            if not ROOMS[room_id]:
                del ROOMS[room_id]
                logging.info(f"Sala {room_id} vazia, a ser removida.")

    return ws

async def handle_room(request):
    """Serve o ficheiro principal index.html para qualquer rota de sala."""
    return web.FileResponse('./index.html')

async def redirect_to_new_room(request):
    """Redireciona o acesso à raiz para uma nova sala com um ID aleatório."""
    new_room_id = str(uuid.uuid4().hex[:8])
    raise web.HTTPFound(f'/sala/{new_room_id}')

# Configuração da aplicação web
app = web.Application()
app.add_routes([
    web.get('/', redirect_to_new_room),
    web.get('/sala/{room_id}', handle_room), # Rota dinâmica para salas
    web.get('/ws', websocket_handler)
])

if __name__ == '__main__':
    port = 8080
    logging.info(f"A iniciar servidor em http://0.0.0.0:{port}")
    web.run_app(app, host='0.0.0.0', port=port)
