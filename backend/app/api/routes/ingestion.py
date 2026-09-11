"""Platform ingestion routes (CLAUDE.md §17.1, §69, §33 Phase 1->2): a
creator pastes a link to their own public channel instead of hand-typing
their content history."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator, SocialAccount
from app.domain.ingestion.service import import_youtube_channel
from app.domain.ingestion.youtube import YoutubeResolutionError
from app.schemas.ingestion import SocialAccountRead, YoutubeImportRequest, YoutubeImportResponse

router = APIRouter(prefix="/creators/{creator_id}/import", tags=["ingestion"])
accounts_router = APIRouter(prefix="/creators/{creator_id}/social-accounts", tags=["ingestion"])


@router.post("/youtube", response_model=YoutubeImportResponse)
async def import_youtube(
    payload: YoutubeImportRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> YoutubeImportResponse:
    try:
        result = await import_youtube_channel(db, creator_id=creator.id, url=payload.url)
    except YoutubeResolutionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await db.commit()
    return YoutubeImportResponse(**result)


@accounts_router.get("", response_model=list[SocialAccountRead])
async def list_social_accounts(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> list[SocialAccount]:
    result = await db.execute(select(SocialAccount).where(SocialAccount.creator_id == creator.id))
    return list(result.scalars().all())
