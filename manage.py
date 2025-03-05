import asyncio
import websockets

from app.routers.main import router

if __name__ == "__main__":
    # Start the WebSocket server on 0.0.0.0 port 5000
    server = websockets.serve(router, '0.0.0.0', 5000)

    # Run the event loop for the WebSocket server
    asyncio.get_event_loop().run_until_complete(server)
    asyncio.get_event_loop().run_forever()
