import asyncio
import websockets

from app.routers.main import router

async def main():
    # Start the WebSocket server on 0.0.0.0 port 5000
    server = await websockets.serve(router, '0.0.0.0', 5000)
    print("WebSocket server started on ws://0.0.0.0:5000")
    # Keep the server running
    await server.wait_closed()

if __name__ == "__main__":
    # Create and run the event loop
    asyncio.run(main())
