from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SavedView, Tag
from ..schemas import PeopleFilter, SavedViewIn, SavedViewOut, TagIn, TagOut
from .deps import DB

router = APIRouter(tags=["views"])


def view_out(v: SavedView) -> SavedViewOut:
    return SavedViewOut(id=v.id, name=v.name, filter=PeopleFilter.model_validate(v.filter), created_at=v.created_at)


@router.get("/views", response_model=list[SavedViewOut])
def list_views(session: Session = DB):
    return [view_out(v) for v in session.execute(select(SavedView).order_by(SavedView.name)).scalars()]


@router.post("/views", response_model=SavedViewOut, status_code=201)
def create_view(body: SavedViewIn, session: Session = DB):
    v = session.execute(select(SavedView).where(SavedView.name == body.name)).scalar_one_or_none()
    if v is None:
        v = SavedView(name=body.name, filter=body.filter.model_dump(mode="json", exclude_none=True))
        session.add(v)
    else:
        v.filter = body.filter.model_dump(mode="json", exclude_none=True)
    session.commit()
    return view_out(v)


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: int, session: Session = DB):
    v = session.get(SavedView, view_id)
    if v is None:
        raise HTTPException(404, "view not found")
    session.delete(v)
    session.commit()


@router.get("/tags", response_model=list[TagOut])
def list_tags(session: Session = DB):
    return [TagOut(id=t.id, name=t.name, color=t.color) for t in session.execute(select(Tag).order_by(Tag.name)).scalars()]


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(body: TagIn, session: Session = DB):
    t = session.execute(select(Tag).where(Tag.name == body.name)).scalar_one_or_none()
    if t is None:
        t = Tag(name=body.name, color=body.color)
        session.add(t)
    elif body.color:
        t.color = body.color
    session.commit()
    return TagOut(id=t.id, name=t.name, color=t.color)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, session: Session = DB):
    t = session.get(Tag, tag_id)
    if t is None:
        raise HTTPException(404, "tag not found")
    session.delete(t)
    session.commit()
