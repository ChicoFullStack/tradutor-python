import asyncio
import json
import logging
import os
import uuid

from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

# Configuração
ROOT = os.path.dirname(__file__)
logging.basicConfig(level=logging.INFO)

# Globais para gerenciar conexões e mídia
relay = MediaRelay()
pcs = set()

async def handle_offer(pc, offer):
    """
    Processa a oferta SDP recebida de um cliente.
    """
    await pc.setRemoteDescription(offer)

    # Adiciona as tracks de mídia existentes ao novo par
    for track in relay.tracks:
        pc.addTrack(relay.subscribe(track))

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

async def websocket_handler(request):
    """
    Manipula a conexão WebSocket para sinalização WebRTC.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    pc = RTCPeerConnection()
    pc_id = f"PeerConnection({uuid.uuid4()})"
    pcs.add(pc)
    logging.info(f"{pc_id}: Conexão WebSocket aberta.")

    @pc.on("track")
    def on_track(track):
        """
        Quando uma track é recebida de um par, a adiciona ao relay
        e a retransmite para todos os outros pares.
        """
        logging.info(f"Track {track.kind} recebida de {pc_id}")
        # Adiciona a track ao relay para que futuros participantes a recebam
        relayed_track = relay.add_track(track)
        
        # Retransmite a nova track para todos os outros participantes já conectados
        for other_pc in pcs:
            if other_pc is not pc:
                other_pc.addTrack(relayed_track)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logging.info(f"Estado da conexão de {pc_id}: {pc.connectionState}")
        if pc.connectionState in ["failed", "disconnected", "closed"]:
            await ws.close()

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data["type"] == "offer":
                logging.info(f"Oferta recebida de {pc_id}")
                offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                answer = await handle_offer(pc, offer)
                await ws.send_json({"type": "answer", **answer})
        elif msg.type == web.WSMsgType.ERROR:
            logging.error(f"Erro na conexão WebSocket de {pc_id}: {ws.exception()}")

    # Limpeza quando a conexão é fechada
    logging.info(f"{pc_id}: Conexão WebSocket fechada.")
    pcs.discard(pc)
    await pc.close()
    return ws


async def index(request):
    """Serve o arquivo principal da aplicação (index.html)."""
    with open(os.path.join(ROOT, "index.html"), "r") as f:
        return web.Response(text=f.read(), content_type="text/html")

async def favicon(request):
    """Evita erros 404 para o favicon."""
    return web.Response(status=200)

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/favicon.ico", favicon)
app.router.add_get("/ws", websocket_handler)

if __name__ == "__main__":
    print("Servidor iniciado em http://localhost:8080")
    web.run_app(app, access_log=None, host="0.0.0.0", port=8080)
