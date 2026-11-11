from fastapi import APIRouter
router=APIRouter()
@router.get("/status")
def status(): return {"status":"authentication is not implemented in milestone 1"}
