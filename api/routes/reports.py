from fastapi import APIRouter
router=APIRouter()
@router.get("/{report_id}")
def get_report(report_id:int): return {"report_id":report_id,"status":"report retrieval planned for a later milestone"}
