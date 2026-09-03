"""Database cleanup script to remove non-existent test accounts and ensure clean demo personas."""

from app.db.session import SessionLocal
from app.models.user import User, UserRole, AccountStatus, LawyerProfile, ClientProfile
from scripts.seed_pilot_demo import seed_demo_users

def cleanup_database():
    db = SessionLocal()
    try:
        # Find all test users created with @example.com or names like 'Advocate Test QA'
        test_users = (
            db.query(User)
            .filter(
                (User.email.ilike("%@example.com"))
                | (User.email.ilike("%test%"))
            )
            .all()
        )
        
        # Exclude our canonical demo personas: admin@lcc.test, client@lcc.test, advocate@lcc.test
        keep_emails = {"admin@lcc.test", "client@lcc.test", "advocate@lcc.test"}
        
        deleted_count = 0
        for u in test_users:
            if u.email.lower() not in keep_emails and not u.email.startswith("akumarpandit"):
                print(f"Deleting test user: {u.email} ({u.role.value})")
                db.delete(u)
                deleted_count += 1
                
        db.commit()
        print(f"Purged {deleted_count} non-existent/test users from database.")
        
        # Also clean up any lawyer profiles whose names are 'Advocate Test QA'
        test_profiles = db.query(LawyerProfile).filter(LawyerProfile.full_name == "Advocate Test QA").all()
        for lp in test_profiles:
            print(f"Deleting orphan lawyer profile: {lp.full_name} ({lp.id})")
            db.delete(lp)
        db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
        raise
    finally:
        db.close()

    # Re-seed canonical pilot users to ensure advocate@lcc.test, client@lcc.test, admin@lcc.test are healthy
    print("\nEnsuring canonical demo personas are fresh and verified:")
    seed_demo_users()

if __name__ == "__main__":
    cleanup_database()
