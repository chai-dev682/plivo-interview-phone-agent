from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import Response
from plivo import plivoxml
from app.core.logger import logger
from app.services.Plivo import PlivoService
import starlette.websockets

router = APIRouter(
    prefix="/plivo",
    tags=["call"]
)

# @router.post("/inbound_call")
@router.get("/inbound_call")
async def inbound_call(request: Request):
    if request.method == "POST":
        form_data = await request.form()
        call_uuid = form_data.get("CallUUID", "Unknown")
        from_number = form_data.get("From", "Unknown")
    else:  # GET request
        query_params = request.query_params
        call_uuid = query_params.get("CallUUID", "Unknown")
        from_number = query_params.get("From", "Unknown")
    logger.info(f"Incoming call: CallUUID={call_uuid}, From={from_number}")

    response = plivoxml.ResponseElement().add(
        plivoxml.StreamElement(
            f"wss://{request.url.hostname}/plivo/stream?from_number={from_number}&call_uuid={call_uuid}",
            bidirectional=True,
            audioTrack="inbound",
            keepCallAlive=True,
            contentType="audio/x-mulaw;rate=8000"
        )
    )
    
    return Response(
        content=response.to_string(),
        media_type="application/xml"
    )

# WebSocket endpoint for Plivo
@router.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket, from_number: str = "Unknown", call_uuid: str = None):
    try:
        await websocket.accept()
        print('Plivo connection incoming')
        plivo_service = PlivoService()
        await plivo_service.plivo_receiver(websocket, from_number, call_uuid)
    except Exception as e:
        logger.error(f"Error in websocket endpoint: {e}")
        if websocket.client_state != starlette.websockets.WebSocketState.DISCONNECTED:
            await websocket.close()