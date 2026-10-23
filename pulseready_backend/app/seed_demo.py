from sqlalchemy import select
from app.db import Base, engine, SessionLocal
from app.models import Tenant, Facility

DEMO_TENANT_ID = "11111111-1111-4111-8111-111111111111"

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, DEMO_TENANT_ID)
        if tenant is None:
            tenant = Tenant(id=DEMO_TENANT_ID, name="PulseReady Synthetic Demo Tenant")
            db.add(tenant)
            db.flush()
        existing = db.scalar(select(Facility).where(
            Facility.tenant_id == tenant.id, Facility.facility_code == "DEMO-HOSP-01"
        ))
        if existing is None:
            db.add(Facility(
                tenant_id=tenant.id, facility_code="DEMO-HOSP-01",
                name="Synthetic Demonstration Hospital",
                total_beds=120, staffed_beds=84, staff_available=72, staff_required=90,
                supply_on_hand=420, daily_supply_consumption=100,
                isolation_capacity=12, system_status_score=90
            ))
        db.commit()
        print(f"Seeded tenant {DEMO_TENANT_ID} and DEMO-HOSP-01")
    finally:
        db.close()

if __name__ == "__main__":
    main()
