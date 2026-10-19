from fastapi import APIRouter

router = APIRouter(tags=["sistema"])


@router.get("/salute", summary="Controllo di vita del back-end")
def salute() -> dict[str, str]:
    return {"stato": "ok"}
