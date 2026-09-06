import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal, engine
from app.models.base import Base
from app.models.court_case import CourtCase
from app.core.identifiers import generate_uuid7

def seed_court_cases():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(CourtCase).filter(CourtCase.cnr == "DLHC010041202025").first()
        if existing:
            print("Court cases already seeded.")
            return

        cases = [
            CourtCase(
                id=generate_uuid7(),
                cnr="DLHC010041202025",
                case_number="CS(COMM) 412/2025",
                case_type="CS(COMM) - Commercial Suit",
                filing_number="18942/2025",
                filing_date="14 Jan 2025",
                registration_date="16 Jan 2025",
                court_name="High Court of Delhi at New Delhi",
                bench="Hon'ble Mr. Justice Sanjeev Narula (Court Room 4)",
                court_room="Court Room 4",
                item_number="Item 14",
                petitioner="M/s Sharma Estates Pvt. Ltd.",
                petitioner_advocate="Adv. Vikramaditya Sen (D/1429/2012)",
                respondent="Mehta Trading Corporation & 2 Ors.",
                respondent_advocate="Adv. Ananya Roy (D/2890/2016)",
                acts_and_sections="Commercial Courts Act, 2015 · Sec. 12A · Specific Relief Act, 1963",
                technical_status="Judgment Reserved",
                human_status="All oral arguments have concluded. The judge is writing the final judgment.",
                next_hearing_date=datetime(2026, 9, 18, 10, 30, tzinfo=UTC),
                next_hearing_purpose="Pronouncement of Judgment",
                source_provenance="OFFICIAL COURT DATA",
                last_synchronized_at=datetime.now(UTC),
                sync_status="SYNCED",
                history_json=[
                    {
                        "date": "04 Sep 2026",
                        "judge": "Hon'ble Mr. Justice Sanjeev Narula",
                        "business": "Final arguments concluded by both sides. Matter reserved for judgment.",
                        "next_date": "18 Sep 2026",
                    },
                    {
                        "date": "14 Aug 2026",
                        "judge": "Hon'ble Mr. Justice Sanjeev Narula",
                        "business": "Plaintiff evidence concluded. Defendant arguments addressed in part.",
                        "next_date": "04 Sep 2026",
                    },
                    {
                        "date": "02 Jul 2026",
                        "judge": "Joint Registrar (Judicial)",
                        "business": "Admission and denial of original documents completed on affidavit.",
                        "next_date": "14 Aug 2026",
                    },
                    {
                        "date": "12 May 2026",
                        "judge": "Hon'ble Mr. Justice Sanjeev Narula",
                        "business": "Framing of issues completed. List of witnesses filed.",
                        "next_date": "02 Jul 2026",
                    },
                ],
                cause_list_json={
                    "court_room": "Court Room 4",
                    "item_number": "Item 14",
                    "cause_list_date": "18 Sep 2026 (Daily Board)",
                    "bench": "Hon'ble Mr. Justice Sanjeev Narula",
                    "board_status": "Listed for Pronouncement of Judgment (Morning Session 10:30 AM)",
                },
                orders_json=[
                    {
                        "title": "Interim Order & Hearing Proceedings",
                        "order_date": "04 Sep 2026",
                        "pages": 4,
                        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    },
                    {
                        "title": "Admission & Denial Compliance Order",
                        "order_date": "02 Jul 2026",
                        "pages": 6,
                        "sha256": "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
                    },
                    {
                        "title": "Summons & Interim Injunction Order",
                        "order_date": "16 Jan 2025",
                        "pages": 8,
                        "sha256": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
                    },
                ],
            ),
            CourtCase(
                id=generate_uuid7(),
                cnr="DLHC0100882026",
                case_number="OMP(I)(COMM) 88/2026",
                case_type="OMP(I)(COMM) - Arbitration Petition",
                filing_number="4521/2026",
                filing_date="02 Feb 2026",
                registration_date="05 Feb 2026",
                court_name="High Court of Delhi at New Delhi",
                bench="Hon'ble Ms. Justice Rekha Palli (Court Room 12)",
                court_room="Court Room 12",
                item_number="Item 28",
                petitioner="M/s Apex Infrastructure",
                petitioner_advocate="Adv. Ananya Roy (D/2890/2016)",
                respondent="Union of India & Anr.",
                respondent_advocate="Central Government Standing Counsel",
                acts_and_sections="Arbitration and Conciliation Act, 1996 · Section 9",
                technical_status="Admission & Denial",
                human_status="The court is verifying authentic original contracts and receipts submitted by both sides.",
                next_hearing_date=datetime(2026, 9, 22, 14, 15, tzinfo=UTC),
                next_hearing_purpose="Admission and Denial of Documents",
                source_provenance="OFFICIAL COURT DATA",
                last_synchronized_at=datetime.now(UTC),
                sync_status="SYNCED",
                history_json=[
                    {
                        "date": "14 Aug 2026",
                        "judge": "Court of Joint Registrar (Judicial)",
                        "business": "Opposite party filed reply affidavit. Next date fixed for admission & denial.",
                        "next_date": "22 Sep 2026",
                    },
                    {
                        "date": "12 Jun 2026",
                        "judge": "Hon'ble Ms. Justice Rekha Palli",
                        "business": "Notice accepted by respondent standing counsel.",
                        "next_date": "14 Aug 2026",
                    },
                ],
                cause_list_json={
                    "court_room": "Court Room 12",
                    "item_number": "Item 28",
                    "cause_list_date": "22 Sep 2026",
                    "bench": "Hon'ble Ms. Justice Rekha Palli",
                    "board_status": "Listed for Admission & Denial of Documents (Afternoon Session 02:15 PM)",
                },
                orders_json=[
                    {
                        "title": "Notice & Direction for Pleadings",
                        "order_date": "14 Aug 2026",
                        "pages": 3,
                        "sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
                    }
                ],
            ),
            CourtCase(
                id=generate_uuid7(),
                cnr="DLCT010023402026",
                case_number="CC/234/2026",
                case_type="Consumer Complaint",
                filing_number="1120/2026",
                filing_date="10 May 2026",
                registration_date="12 May 2026",
                court_name="District Consumer Disputes Redressal Commission (Tis Hazari, Delhi)",
                bench="Bench I · Tis Hazari",
                court_room="Room 3",
                item_number="Item 08",
                petitioner="Rajesh Kumar",
                petitioner_advocate="Adv. Rajesh Gupta",
                respondent="Star Logistics & E-Commerce Services",
                respondent_advocate="Adv. Priya Sharma",
                acts_and_sections="Consumer Protection Act, 2019 · Section 35",
                technical_status="Notice Issued",
                human_status="Formal court summons has been issued to the opposite party.",
                next_hearing_date=datetime(2026, 9, 25, 11, 0, tzinfo=UTC),
                next_hearing_purpose="Filing of Written Statement by Opposite Party",
                source_provenance="OFFICIAL COURT DATA",
                last_synchronized_at=datetime.now(UTC),
                sync_status="SYNCED",
                history_json=[
                    {
                        "date": "15 Jul 2026",
                        "judge": "President, District Commission",
                        "business": "Summons issued via speed post. Awaiting tracking report.",
                        "next_date": "25 Sep 2026",
                    }
                ],
                cause_list_json={
                    "court_room": "Room 3",
                    "item_number": "Item 08",
                    "cause_list_date": "25 Sep 2026",
                    "bench": "Bench I (Tis Hazari)",
                    "board_status": "Listed for Appearance & Written Statement",
                },
                orders_json=[
                    {
                        "title": "Summons Order & Proof of Service Notice",
                        "order_date": "15 Jul 2026",
                        "pages": 2,
                        "sha256": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
                    }
                ],
            ),
        ]

        for c in cases:
            db.add(c)
        db.commit()
        print(f"Successfully seeded {len(cases)} court cases.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_court_cases()
