from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.analyze import router as analyze_router
from app.api.v1.remediate import router as remediate_router
from app.api.v1.variants import router as variants_router
from app.api.v1.profile import router as profile_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.career import router as career_router
from app.api.v1.roadmaps import router as roadmaps_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(health_router)
api_v1_router.include_router(analyze_router)
api_v1_router.include_router(remediate_router)
api_v1_router.include_router(variants_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(ingest_router)
api_v1_router.include_router(career_router)
api_v1_router.include_router(roadmaps_router)
