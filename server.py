# server.py
#
# INSTRUÇÕES PARA O SERVIDOR WEB (PRODUÇÃO - DOKPLOY):
# 1. Este ficheiro está pronto para produção.
# 2. Certifique-se de que os ficheiros 'requirements.txt' e 'Dockerfile' existem.
# 3. O Dokploy irá usar o Dockerfile para construir e executar este servidor.

import asyncio
import json
import logging
from aiohttp import web
from googletrans import Translator

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)

# Armazena as conexões WebSocket ativas e os usuários por sala
CONNECTIONS = set()
USERS = {}

# Inicializa o tradutor
translator = Translator()

async def handle_translation(data):
    """Lida com o pedido de tradução."""
    try:
        text_to_translate = data.get('text')
        source_lang = data.get('source_lang', 'pt')
        dest_lang = data.get('dest_lang', 'en')
        
        source_lang = source_lang.split('-')[0]
        dest_lang = dest_lang.split('-')[0]

        if not text_to_translate:
            return None

        translated = translator.translate(text_to_translate, src=source_lang, dest=dest_lang)
        return translated.text
    except Exception as e:
        logging.error(f"Erro na tradução: {e}")
        return "[Erro na tradução]"

async def websocket_handler(request):
    """Lida com as conexões WebSocket para sinalização e chat."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    CONNECTIONS.add(ws)
    
    user_id = None
    logging.info(f"Nova conexão WebSocket. Total: {len(CONNECTIONS)}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')

                    async def broadcast(message):
                        for conn in CONNECTIONS:
                            if conn != ws:
                                await conn.send_json(message)
                    
                    if msg_type == 'join':
                        user_id = data['user_id']
                        USERS[user_id] = ws
                        logging.info(f"Usuário {user_id} entrou. Usuários online: {list(USERS.keys())}")
                        await broadcast({'type': 'user-joined', 'user_id': user_id})
                        await ws.send_json({'type': 'existing-users', 'user_ids': list(USERS.keys())})

                    elif msg_type in ['offer', 'answer', 'candidate']:
                        target_id = data.get('target_id')
                        if target_id in USERS:
                            await USERS[target_id].send_json(data)
                        else:
                            logging.warning(f"Sinalização: Usuário alvo {target_id} não encontrado.")

                    elif msg_type == 'translate':
                        translated_text = await handle_translation(data)
                        if translated_text:
                            response = {
                                'type': 'translation', 
                                'user_id': data.get('user_id'),
                                'original': data.get('text'),
                                'translated': translated_text
                            }
                            for conn in CONNECTIONS:
                                await conn.send_json(response)

                except Exception as e:
                    logging.error(f"Erro ao processar mensagem: {e}")

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f'Conexão WebSocket fechada com exceção {ws.exception()}')

    finally:
        CONNECTIONS.remove(ws)
        if user_id and user_id in USERS:
            del USERS[user_id]
            for conn in CONNECTIONS:
                await conn.send_json({'type': 'user-left', 'user_id': user_id})
        logging.info(f"Conexão WebSocket fechada. Total: {len(CONNECTIONS)}")

    return ws

async def index(request):
    """Serve o arquivo principal index.html."""
    return web.FileResponse('./index.html')

# Configuração da aplicação web
app = web.Application()
app.add_routes([
    web.get('/', index),
    web.get('/ws', websocket_handler)
])

if __name__ == '__main__':
    # CORREÇÃO: Em produção (Docker), o servidor deve correr em HTTP.
    # O proxy reverso do Dokploy (Traefik) irá gerir o HTTPS.
    port = 8080
    logging.info(f"A iniciar servidor em http://0.0.0.0:{port}")
    web.run_app(app, host='0.0.0.0', port=port)
