from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Process liveness endpoint; it deliberately does not query the database."""
    return {"status": "ok", "service": "soar-lite"}
