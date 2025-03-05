from app.services.Plivo import PlivoService

plivo_service = PlivoService()

async def plivo_handler(plivo_ws):
    await plivo_service.plivo_receiver(plivo_ws)

# Router to handle incoming WebSocket connections and routes them to plivo_handler
async def router(websocket, path):
    if path == '/stream':
        print('Plivo connection incoming')
        await plivo_handler(websocket)
