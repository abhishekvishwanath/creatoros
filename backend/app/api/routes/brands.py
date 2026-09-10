"""Brand database (CLAUDE.md §68-69, Part II Phase 2).

Manual entry only — no company-database/enrichment API is wired in (see
CLAUDE.md §69 for why that's a deliberate MVP choice, not an oversight).
Every route below that touches a specific brand's sub-resources (contacts,
signals) re-verifies the brand belongs to this creator first — BrandContact/
BrandSignal aren't creator-scoped columns themselves, so that check is the
only thing standing between one creator and another creator's contacts.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, get_owned_creator
from app.domain.commercial.models import Brand, BrandContact, BrandSignal
from app.domain.commercial.service import (
    add_brand_contact,
    add_brand_signal,
    create_brand,
    get_brand,
    list_brand_contacts,
    list_brand_signals,
    list_brands,
)
from app.domain.creator.models import Creator
from app.schemas.commercial import (
    BrandContactCreate,
    BrandContactRead,
    BrandCreate,
    BrandRead,
    BrandSignalCreate,
    BrandSignalRead,
)

router = APIRouter(prefix="/creators/{creator_id}/brands", tags=["brands"])


async def _get_owned_brand(db: DbSession, creator: Creator, brand_id: str) -> Brand:
    brand = await get_brand(db, creator_id=creator.id, brand_id=brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.post("", response_model=BrandRead, status_code=201)
async def create_brand_route(
    payload: BrandCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Brand:
    brand = await create_brand(db, creator_id=creator.id, data=payload.model_dump())
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("", response_model=list[BrandRead])
async def list_brands_route(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[Brand]:
    return await list_brands(db, creator_id=creator.id)


@router.get("/{brand_id}", response_model=BrandRead)
async def get_brand_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Brand:
    return await _get_owned_brand(db, creator, brand_id)


@router.post("/{brand_id}/contacts", response_model=BrandContactRead, status_code=201)
async def add_brand_contact_route(
    brand_id: str,
    payload: BrandContactCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> BrandContact:
    await _get_owned_brand(db, creator, brand_id)
    contact = await add_brand_contact(db, brand_id=brand_id, data=payload.model_dump())
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/{brand_id}/contacts", response_model=list[BrandContactRead])
async def list_brand_contacts_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[BrandContact]:
    await _get_owned_brand(db, creator, brand_id)
    return await list_brand_contacts(db, brand_id=brand_id)


@router.post("/{brand_id}/signals", response_model=BrandSignalRead, status_code=201)
async def add_brand_signal_route(
    brand_id: str,
    payload: BrandSignalCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> BrandSignal:
    await _get_owned_brand(db, creator, brand_id)
    signal = await add_brand_signal(db, creator_id=creator.id, brand_id=brand_id, data=payload.model_dump())
    await db.commit()
    await db.refresh(signal)
    return signal


@router.get("/{brand_id}/signals", response_model=list[BrandSignalRead])
async def list_brand_signals_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[BrandSignal]:
    await _get_owned_brand(db, creator, brand_id)
    return await list_brand_signals(db, creator_id=creator.id, brand_id=brand_id)
