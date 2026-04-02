from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Networking
from app.schemas.networking import NetworkingRead

router = APIRouter()


@router.get("/networking", response_model=list[NetworkingRead])
def list_networking(vendor: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Networking)
    if vendor:
        query = query.filter(Networking.vendor.ilike(vendor))
    return query.order_by(Networking.vendor, Networking.name).all()
