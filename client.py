# server.py
#
# INSTRUÇÕES PARA O SERVIDOR WEB:
# 1. Certifique-se de que o Python está instalado.
# 2. Ative seu ambiente virtual (venv).
# 3. Instale as bibliotecas necessárias:
#    pip install aiohttp googletrans==4.0.0-rc1
#
# 4. Salve o arquivo 'index.html' (o código do cliente) na mesma pasta que este servidor.
# 5. Execute este script: python server.py
# 6. Abra um navegador e acesse http://localhost:8080

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

                    # Envia a mensagem para todos, exceto o remetente
                    async def broadcast(message):
                        for conn in CONNECTIONS:
                            if conn != ws:
                                await conn.send_json(message)
                    
                    if msg_type == 'join':
                        user_id = data['user_id']
                        USERS[user_id] = ws
                        logging.info(f"Usuário {user_id} entrou. Usuários online: {list(USERS.keys())}")
                        # Notifica outros usuários sobre o novo participante
                        await broadcast({'type': 'user-joined', 'user_id': user_id})
                        # Envia a lista de usuários atuais para o novo participante
                        await ws.send_json({'type': 'existing-users', 'user_ids': list(USERS.keys())})

                    elif msg_type == 'offer' or msg_type == 'answer' or msg_type == 'candidate':
                        # Retransmite mensagens de sinalização WebRTC para o usuário alvo
                        target_id = data['target_id']
                        if target_id in USERS:
                            target_ws = USERS[target_id]
                            await target_ws.send_json(data)
                        else:
                            logging.warning(f"Sinalização: Usuário alvo {target_id} não encontrado.")

                    elif msg_type == 'translate':
                        # Lida com a tradução
                        translated_text = await handle_translation(data)
                        if translated_text:
                            # Envia a tradução para todos
                            response = {
                                'type': 'translation', 
                                'user_id': data.get('user_id'),
                                'original': data.get('text'),
                                'translated': translated_text
                            }
                            for conn in CONNECTIONS:
                                await conn.send_json(response)

                except json.JSONDecodeError:
                    logging.error(f"Mensagem JSON inválida recebida: {msg.data}")
                except Exception as e:
                    logging.error(f"Erro ao processar mensagem: {e}")

            elif msg.type == web.WSMsgType.ERROR:
                logging.error(f'Conexão WebSocket fechada com exceção {ws.exception()}')

    finally:
        CONNECTIONS.remove(ws)
        if user_id and user_id in USERS:
            del USERS[user_id]
            # Notifica outros que o usuário saiu
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
    web.run_app(app, host='0.0.0.0', port=8080)
