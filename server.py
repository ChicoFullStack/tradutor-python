import asyncio
import json
import logging
import os
import uuid

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

# Configura o logging para depuração
logging.basicConfig(level=logging.INFO)

# Diretório onde o arquivo HTML está localizado
ROOT = os.path.dirname(__file__)

# Cria um relay de mídia para distribuir os streams
relay = MediaRelay()
# Mantém o controle das conexões de pares (clientes)
pcs = set()

async def offer(request):
    """
    Manipula a oferta de SDP de um cliente para iniciar uma conexão WebRTC.
    """
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Cria uma nova conexão de par (RTCPeerConnection)
    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    def log_info(msg, *args):
        logging.info(pc_id + " " + msg, *args)

    log_info("Conexão criada")

    @pc.on("datachannel")
    def on_datachannel(channel):
        @channel.on("message")
        def on_message(message):
            log_info(f"Mensagem do DataChannel: {message}")
            # Aqui você pode adicionar lógica de chat de texto

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        log_info("Estado da conexão: %s", pc.connectionState)
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
            log_info("Conexão fechada")

    @pc.on("track")
    def on_track(track):
        log_info("Track %s recebida", track.kind)
        # Encaminha a track de mídia para outros pares
        relay.add_track(track)

        @track.on("ended")
        async def on_ended():
            log_info("Track %s encerrada", track.kind)
            # Você pode adicionar lógica aqui se necessário

    # Define a descrição remota com a oferta recebida
    await pc.setRemoteDescription(offer)

    # Cria uma resposta SDP para enviar de volta ao cliente
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    log_info("Enviando resposta para o cliente")
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    """
    Fecha todas as conexões de pares ao desligar o servidor.
    """
    # Fecha todas as conexões RTCPeerConnection
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


async def index(request):
    """
    Serve o arquivo principal da aplicação (index.html).
    """
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


if __name__ == "__main__":
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)
    
    # Inicia o servidor web
    # Para produção, você deve usar SSL/TLS.
    # ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # ssl_context.load_cert_chain("server.crt", "server.key")
    # web.run_app(app, access_log=None, host="0.0.0.0", port=8080, ssl_context=ssl_context)
    
    print("Servidor iniciado em http://localhost:8080")
    web.run_app(app, access_log=None, host="0.0.0.0", port=8080)

