from app.crossfile.routers import AuditAPIRouter

router = AuditAPIRouter(tags=["audits"])


@router.get("/daily")  # GET /api/v1/audits/daily: the class fixes the prefix
def daily_audit(): ...
