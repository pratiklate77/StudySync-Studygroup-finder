from uuid import UUID

from fastapi import APIRouter, Query, WebSocket

from app.core.security import decode_token

router = APIRouter()


@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=4001)
        return

    try:
        user_id = UUID(str(payload["sub"]))
    except Exception:
        await websocket.close(code=4001)
        return

    ws_manager = getattr(websocket.app.state, "ws_manager", None)
    if ws_manager is None:
        await websocket.close(code=4000)
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        ws_manager.disconnect(user_id, websocket)
