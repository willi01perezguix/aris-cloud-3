from fastapi import APIRouter, Response

from app.aris3.core.metrics import metrics

router = APIRouter()


@router.get(
    "/aris3/ops/metrics",
    summary="Operations metrics (internal)",
    description="Operational Prometheus metrics endpoint for infrastructure/observability tooling. Not a product workflow endpoint.",
)
def get_metrics():
    snapshot = metrics.render()
    return Response(content=snapshot.content, media_type=snapshot.content_type)

