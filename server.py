import asyncio
import json
import logging
import os
import uuid
import ssl

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

# Configura o logging para um nível mais detalhado, útil para depuração.
logging.basicConfig(level=logging.INFO)

# Define o diretório raiz para encontrar o arquivo index.html
ROOT = os.path.dirname(__file__)

# O MediaRelay é a mágica que nos permite retransmitir um stream de mídia para múltiplos destinos.
relay = MediaRelay()
# Mantém o controle de todas as conexões de pares (clientes) ativas.
pcs = set()

async def offer(request):
    """
    Esta função é chamada quando um novo cliente se conecta.
    Ele envia uma "oferta" para iniciar a comunicação WebRTC.
    """
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    # Cria uma nova conexão de par (RTCPeerConnection) para este cliente.
    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    def log_info(msg, *args):
        """Função auxiliar para logging com o ID do par."""
        logging.info(pc_id + " " + msg, *args)

    log_info("Conexão criada")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        """Monitora o estado da conexão e limpa quando um par se desconecta."""
        log_info("Estado da conexão: %s", pc.connectionState)
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)
            log_info("Conexão fechada")

    @pc.on("track")
    def on_track(track):
        """
        Quando uma track (áudio ou vídeo) é recebida de um cliente,
        nós a adicionamos ao relay para que outros clientes possam recebê-la.
        """
        log_info("Track %s recebida", track.kind)
        # O relay.subscribe(track) cria uma nova track que é uma cópia da original.
        # Esta é a maneira correta de retransmitir a mídia.
        for p in pcs:
            if p is not pc:
                p.addTrack(relay.subscribe(track))

    # Define a oferta recebida do cliente.
    await pc.setRemoteDescription(offer)

    # Cria uma "resposta" para enviar de volta ao cliente, completando a negociação.
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app):
    """Função para limpar as conexões quando o servidor é desligado."""
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


async def index(request):
    """Serve o arquivo principal da aplicação (index.html)."""
    try:
        with open(os.path.join(ROOT, "index.html"), "r") as f:
            content = f.read()
        return web.Response(content_type="text/html", text=content)
    except FileNotFoundError:
        return web.Response(status=404, text="index.html não encontrado")

async def favicon(request):
    """Serve uma resposta vazia para o favicon para evitar erros 404 no console."""
    return web.Response(status=200)


if __name__ == "__main__":
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/favicon.ico", favicon) # Adiciona a rota do favicon
    app.router.add_post("/offer", offer)
    
    # Para produção, você deve usar SSL/TLS. WebRTC requer conexões seguras (HTTPS)
    # quando não está rodando em localhost.
    # ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # try:
    #     ssl_context.load_cert_chain("server.crt", "server.key")
    #     print("Certificados SSL carregados. Rodando em HTTPS.")
    # except FileNotFoundError:
    #     print("Aviso: Certificados SSL (server.crt, server.key) não encontrados. Rodando em HTTP.")
    #     print("WebRTC pode não funcionar em navegadores que não sejam localhost.")
    #     ssl_context = None
    
    print("Servidor iniciado em http://localhost:8080")
    web.run_app(app, access_log=None, host="0.0.0.0", port=8080, ssl_context=None)
