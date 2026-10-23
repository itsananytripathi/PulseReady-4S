from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import Tenant

def current_tenant(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Tenant:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key")
    tenant_id = settings.api_keys.get(x_api_key)
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid API key")
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=403, detail="API key tenant is not provisioned")
    return tenant
