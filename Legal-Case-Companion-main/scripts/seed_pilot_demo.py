"""Seed script for local interactive pilot demonstration.
Creates 3 canonical personas with password: 'Password123!'
  1. Client:   client@lcc.test (Vikram Sharma)
  2. Lawyer:   advocate@lcc.test (Advocate Ananya Roy - Delhi Bar Council Verified)
  3. Admin:    admin@lcc.test (LCC Platform Administrator)
"""

from datetime import time
from app.core.identifiers import generate_uuid7
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.availability import DayOfWeek, LawyerAvailability
from app.models.user import (
    AccountStatus,
    ClientProfile,
    LawyerProfile,
    LawyerVerification,
    User,
    UserRole,
    VerificationStatus,
)


def seed_demo_users(db_session=None):
    close_db = False
    if db_session is not None:
        db = db_session
    else:
        db = SessionLocal()
        close_db = True
    try:
        common_password = hash_password("Password123!")

        # 1. Admin Persona
        admin_user = db.query(User).filter(User.email == "admin@lcc.test").first()
        if not admin_user:
            admin_user = User(
                id=generate_uuid7(),
                email="admin@lcc.test",
                password_hash=common_password,
                role=UserRole.ADMIN,
                account_status=AccountStatus.ACTIVE,
            )
            db.add(admin_user)
            print("Created Admin: admin@lcc.test / Password123!")
        else:
            admin_user.password_hash = common_password
            admin_user.account_status = AccountStatus.ACTIVE
            print("Updated Admin: admin@lcc.test")

        # 2. Client Persona
        client_user = db.query(User).filter(User.email == "client@lcc.test").first()
        if not client_user:
            client_user = User(
                id=generate_uuid7(),
                email="client@lcc.test",
                password_hash=common_password,
                role=UserRole.CLIENT,
                account_status=AccountStatus.ACTIVE,
            )
            db.add(client_user)
            client_profile = ClientProfile(
                id=generate_uuid7(),
                user_id=client_user.id,
                full_name="Vikram Sharma",
                location="New Delhi, India",
            )
            db.add(client_profile)
            print("Created Client: client@lcc.test / Password123! (Vikram Sharma)")
        else:
            client_user.password_hash = common_password
            client_user.account_status = AccountStatus.ACTIVE
            print("Updated Client: client@lcc.test")

        # 3. Lawyer Persona
        lawyer_user = db.query(User).filter(User.email == "advocate@lcc.test").first()
        if not lawyer_user:
            lawyer_user = User(
                id=generate_uuid7(),
                email="advocate@lcc.test",
                password_hash=common_password,
                role=UserRole.LAWYER,
                account_status=AccountStatus.ACTIVE,
            )
            db.add(lawyer_user)
            lawyer_profile = LawyerProfile(
                id=generate_uuid7(),
                user_id=lawyer_user.id,
                full_name="Advocate Ananya Roy",
                bio="Senior Counsel specializing in Commercial Law, Civil Litigation, and Technology Contracts with 12+ years at the Delhi High Court.",
                location="Delhi / New Delhi",
                consultation_fee=2500.0,
                experience_years=12,
                languages=["English", "Hindi", "Bengali"],
                practice_areas=["Commercial Law", "Corporate & Contracts", "Civil Litigation"],
                court_jurisdictions=["Delhi High Court", "Supreme Court of India", "Tis Hazari Court"],
            )
            db.add(lawyer_profile)

            # Verification record
            verification = LawyerVerification(
                id=generate_uuid7(),
                lawyer_profile_id=lawyer_profile.id,
                enrollment_number="D/1842/2012",
                state_bar_council="Bar Council of Delhi",
                status=VerificationStatus.APPROVED,
            )
            db.add(verification)

            # Add Mon-Fri availability (10:00 to 18:00)
            for day in [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY]:
                avail = LawyerAvailability(
                    id=generate_uuid7(),
                    lawyer_profile_id=lawyer_profile.id,
                    day_of_week=day.value,
                    start_time=time(10, 0),
                    end_time=time(18, 0),
                    slot_duration_minutes=30,
                    is_active=True,
                )
                db.add(avail)
            print("Created Lawyer: advocate@lcc.test / Password123! (Advocate Ananya Roy)")
        else:
            lawyer_user.password_hash = common_password
            lawyer_user.account_status = AccountStatus.ACTIVE
            print("Updated Lawyer: advocate@lcc.test")

        db.commit()
        print("\nAll Pilot Demo personas provisioned successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding demo users: {e}")
        raise
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_demo_users()
