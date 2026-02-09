from fastapi import APIRouter, Response

from app.aris3.core.metrics import metrics

router = APIRouter()


@router.get("/aris3/ops/metrics")
def get_metrics():
    snapshot = metrics.render()
    return Response(content=snapshot.content, media_type=snapshot.content_type)

