"""
Dataset Loader Module for LCC AI/Model Backend.
Responsible for:
1. Loading raw District Court cases (from raw_cases/ or built-in prototype records).
2. Covering all 6 shortlisted crime categories:
   - cyber_fraud
   - crimes_against_women
   - matrimonial_disputes
   - cheating_forgery
   - theft_burglary
   - crimes_against_senior_citizens
3. Providing statutory knowledge chunks (IT Act, BNS, IPC, Senior Citizens Act).
4. Generating standardized embedding_text matching dataset_pipeline.py.
5. Ingesting both cases and statutes into the vector store.
"""

from __future__ import annotations
import glob
import json
import os
import logging
from typing import List, Dict, Any, Optional

from .schemas import LegalCaseRecord, StatuteRecord
from .vector_store import BaseVectorStore

logger = logging.getLogger("lcc.dataset_loader")


# ---------------------------------------------------------------------------
# Core Statutory Knowledge Base (District Court Scope)
# ---------------------------------------------------------------------------

DEFAULT_STATUTE_RECORDS: List[Dict[str, Any]] = [
    {
        "source_id": "stat:IT-66D",
        "source_type": "statute",
        "act": "Information Technology Act, 2000",
        "section": "66D",
        "title": "Punishment for cheating by personation by using computer resource",
        "text": (
            "Whoever, by means of any communication device or computer resource, cheats by personation, "
            "shall be punished with imprisonment of either description for a term which may extend to three years "
            "and shall also be liable to fine which may extend to one lakh rupees."
        ),
        "explanation": (
            "Applies when an individual pretends to be someone else (e.g. a customs official, bank manager, police officer) "
            "via phone, SMS, email, or online computer resource to cheat the victim into transferring funds or sharing credentials."
        ),
        "crime_category": "cyber_fraud",
        "keywords": ["impersonation", "customs officer", "digital arrest", "UPI scam", "computer resource", "phone fraud", "cheating"],
    },
    {
        "source_id": "stat:BNS-318",
        "source_type": "statute",
        "act": "Bharatiya Nyaya Sanhita (BNS), 2023",
        "section": "318",
        "title": "Cheating and dishonestly inducing delivery of property",
        "text": (
            "Section 318 BNS defines cheating as deceiving any person and fraudulently or dishonestly inducing "
            "the person so deceived to deliver any property to any person, or to consent that any person shall retain "
            "any property. Equivalent to prior Section 420 IPC."
        ),
        "explanation": (
            "Core criminal offence for fraudulent inducement. Punishable with imprisonment up to 7 years and fine "
            "where delivery of money or valuable security is dishonestly induced."
        ),
        "crime_category": "cheating_forgery",
        "keywords": ["cheating", "fraudulent inducement", "BNS 318", "IPC 420", "delivery of property", "financial fraud"],
    },
    {
        "source_id": "stat:IPC-420",
        "source_type": "statute",
        "act": "Indian Penal Code (IPC), 1860",
        "section": "420",
        "title": "Cheating and dishonestly inducing delivery of property (Pre-BNS Regime)",
        "text": (
            "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person... "
            "shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
        ),
        "explanation": (
            "Applies to offenses committed prior to July 1, 2024. For cyber frauds involving fake officials or false pretenses, "
            "this section was standardly applied along with Section 66D of the IT Act."
        ),
        "crime_category": "cheating_forgery",
        "keywords": ["IPC 420", "cheating", "pre-BNS", "delivery of property"],
    },
    {
        "source_id": "stat:IPC-354",
        "source_type": "statute",
        "act": "Indian Penal Code (IPC) / BNS 74",
        "section": "354",
        "title": "Assault or criminal force to woman with intent to outrage her modesty",
        "text": (
            "Whoever assaults or uses criminal force to any woman, intending to outrage or knowing it to be likely "
            "that he will thereby outrage her modesty, shall be punished with imprisonment of not less than one year "
            "which may extend to five years, and shall also be liable to fine."
        ),
        "explanation": (
            "Protects women from physical or criminal force intended to outrage dignity or modesty. Cognizable and non-bailable."
        ),
        "crime_category": "crimes_against_women",
        "keywords": ["outraging modesty", "assault on woman", "Section 354 IPC", "BNS Section 74", "harassment"],
    },
    {
        "source_id": "stat:IPC-498A",
        "source_type": "statute",
        "act": "Indian Penal Code (IPC) / BNS 85",
        "section": "498A",
        "title": "Husband or relative of husband of a woman subjecting her to cruelty",
        "text": (
            "Whoever, being the husband or the relative of the husband of a woman, subjects such woman to cruelty "
            "shall be punished with imprisonment for a term which may extend to three years and shall also be liable to fine. "
            "Cruelty includes willful conduct driving woman to suicide, danger to life/limb, or harassment with a view to coercing unlawful property or dowry demands."
        ),
        "explanation": (
            "Penal provision dealing with matrimonial cruelty, harassment, and dowry demands by husband or in-laws. Cognizable and non-bailable."
        ),
        "crime_category": "crimes_against_women",
        "keywords": ["cruelty", "Section 498A", "dowry harassment", "domestic abuse", "in-laws cruelty", "BNS 85"],
    },
    {
        "source_id": "stat:DV-3",
        "source_type": "statute",
        "act": "Protection of Women from Domestic Violence Act, 2005",
        "section": "3",
        "title": "Definition of domestic violence",
        "text": (
            "Any act, omission or commission or conduct of the respondent shall constitute domestic violence in case it "
            "harms or injures or endangers the health, safety, life, limb or well-being, whether mental or physical, of the aggrieved person "
            "or tends to do so and includes physical abuse, sexual abuse, verbal and emotional abuse and economic abuse."
        ),
        "explanation": (
            "Provides civil and quasi-criminal remedies including protection orders, residence orders, and monetary relief for women facing domestic abuse."
        ),
        "crime_category": "crimes_against_women",
        "keywords": ["domestic violence", "DV Act", "physical abuse", "protection order", "emotional abuse", "economic abuse", "Section 3 DV Act"],
    },
    {
        "source_id": "stat:CrPC-125",
        "source_type": "statute",
        "act": "Code of Criminal Procedure, 1973 (CrPC) / BNSS 144",
        "section": "125",
        "title": "Order for maintenance of wives, children and parents",
        "text": (
            "If any person having sufficient means neglects or refuses to maintain his wife, unable to maintain herself, "
            "or his legitimate or illegitimate minor child, a Magistrate of the first class may order such person to make a monthly allowance "
            "for the maintenance of his wife or child at such monthly rate as such Magistrate thinks fit."
        ),
        "explanation": (
            "Summary remedy to prevent destitution and vagrancy by securing monthly maintenance and interim maintenance for wife and dependent children."
        ),
        "crime_category": "matrimonial_disputes",
        "keywords": ["maintenance", "Section 125 CrPC", "alimony", "interim maintenance", "support allowance", "BNSS 144"],
    },
    {
        "source_id": "stat:HMA-13B",
        "source_type": "statute",
        "act": "Hindu Marriage Act, 1955",
        "section": "13B",
        "title": "Divorce by mutual consent",
        "text": (
            "A petition for dissolution of marriage by a decree of divorce may be presented to the district court by both the parties to a marriage together, "
            "on the ground that they have been living separately for a period of one year or more, that they have not been able to live together "
            "and that they have mutually agreed that the marriage should be dissolved."
        ),
        "explanation": (
            "Provides the legal framework for dissolution of marriage by mutual consent with statutory motion periods, subject to court satisfaction."
        ),
        "crime_category": "matrimonial_disputes",
        "keywords": ["mutual consent divorce", "Section 13B", "HMA", "dissolution of marriage", "separation", "cooling-off period"],
    },
    {
        "source_id": "stat:BNS-305",
        "source_type": "statute",
        "act": "Bharatiya Nyaya Sanhita (BNS), 2023",
        "section": "305",
        "title": "Theft in dwelling house, etc.",
        "text": (
            "Whoever commits theft in any building, tent or vessel, which building, tent or vessel is used as a human dwelling, "
            "or used for the custody of property, shall be punished with imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
        ),
        "explanation": (
            "Aggravated form of theft committed inside residential houses or storage buildings (burglary/house theft). Corresponds to prior Section 380 IPC."
        ),
        "crime_category": "theft_burglary",
        "keywords": ["burglary", "dwelling theft", "house theft", "Section 305 BNS", "Section 380 IPC", "theft in house"],
    },
    {
        "source_id": "stat:BNS-303",
        "source_type": "statute",
        "act": "Bharatiya Nyaya Sanhita (BNS), 2023",
        "section": "303",
        "title": "Theft",
        "text": (
            "Whoever, intending to take dishonestly any movable property out of the possession of any person "
            "without that person's consent, moves that property in order to such taking, is said to commit theft. "
            "Punishable with imprisonment up to three years or fine, or both. (Corresponds to prior Section 379 IPC)."
        ),
        "explanation": (
            "Applies to unauthorized taking of vehicles, wallets, electronic gadgets, or household goods without consent."
        ),
        "crime_category": "theft_burglary",
        "keywords": ["theft", "vehicle theft", "burglary", "stolen property", "Section 303 BNS", "Section 379 IPC"],
    },
    {
        "source_id": "stat:SENIOR-23",
        "source_type": "statute",
        "act": "Maintenance and Welfare of Parents and Senior Citizens Act, 2007",
        "section": "23",
        "title": "Transfer of property to be void in certain circumstances",
        "text": (
            "Where any senior citizen who has transferred by way of gift or otherwise his property, subject to the condition "
            "that the transferee shall provide the basic amenities and physical needs, and such transferee refuses or fails to "
            "provide such amenities, the said transfer of property shall be deemed to have been made by fraud or coercion or undue influence "
            "and can at the option of the transferor be declared void by the Maintenance Tribunal."
        ),
        "explanation": (
            "Protects elderly citizens who deeded home or property to children or relatives who subsequently neglect or abandon them. "
            "Enables senior citizens to have the property transfer cancelled through a summary proceeding before the Sub-Divisional Magistrate."
        ),
        "crime_category": "crimes_against_senior_citizens",
        "keywords": ["senior citizens act", "elder abuse", "property transfer void", "maintenance tribunal", "neglect of parents"],
    },
]


# ---------------------------------------------------------------------------
# Seed District Court Cases (2023 - 2025 Prototype Set)
# ---------------------------------------------------------------------------

DEFAULT_CASE_RECORDS: List[Dict[str, Any]] = [
    {
        "case_id": "DC-HP-2024-000123",
        "court_name": "District & Sessions Court, Solan",
        "state": "Himachal Pradesh",
        "district": "Solan",
        "court_level": "district",
        "year": 2024,
        "crime_category": "cyber_fraud",
        "statute_sections": [{"act": "IT Act", "section": "66D", "label": "Cheating by personation using computer resource"}],
        "fact_summary": "Victim received a phone call from an individual impersonating a customs official alleging parcel seizure and coerced transferring INR 1,50,000 via UPI. Accused was traced via beneficiary account and phone IMEI.",
        "outcome": {"disposal_type": "convicted", "sentence_or_relief": "1 year imprisonment + fine of INR 25,000"},
        "keywords": ["digital arrest scam", "customs impersonation", "UPI fraud", "phone scam"],
    },
    {
        "case_id": "DC-HP-2023-000045",
        "court_name": "District Court, Shimla",
        "state": "Himachal Pradesh",
        "district": "Shimla",
        "court_level": "district",
        "year": 2023,
        "crime_category": "theft_burglary",
        "statute_sections": [{"act": "IPC", "section": "379", "label": "Theft"}],
        "fact_summary": "Two-wheeler parked outside complainant's residence was stolen overnight. Accused was apprehended during vehicle checking a week later with the vehicle bearing fake number plates.",
        "outcome": {"disposal_type": "convicted", "sentence_or_relief": "6 months simple imprisonment"},
        "keywords": ["vehicle theft", "two-wheeler", "motorcycle stolen", "recovery"],
    },
    {
        "case_id": "DC-DL-2024-000889",
        "court_name": "District Court, Saket",
        "state": "Delhi",
        "district": "South Delhi",
        "court_level": "district",
        "year": 2024,
        "crime_category": "cheating_forgery",
        "statute_sections": [
            {"act": "BNS", "section": "318", "label": "Cheating"},
            {"act": "IPC", "section": "468", "label": "Forgery for purpose of cheating"}
        ],
        "fact_summary": "Accused created forged appointment letters pretending to be a recruitment director for government railway employment, taking advance cash payments from multiple job seekers.",
        "outcome": {"disposal_type": "convicted", "sentence_or_relief": "2 years rigorous imprisonment + fine of INR 50,000"},
        "keywords": ["job racket", "forged appointment letter", "cheating", "fake government stamp"],
    },
    {
        "case_id": "DC-MH-2023-001244",
        "court_name": "District & Sessions Court, Pune",
        "state": "Maharashtra",
        "district": "Pune",
        "court_level": "district",
        "year": 2023,
        "crime_category": "crimes_against_women",
        "statute_sections": [
            {"act": "IPC", "section": "354", "label": "Assault on woman with intent to outrage modesty"},
            {"act": "IPC", "section": "354D", "label": "Stalking"}
        ],
        "fact_summary": "Accused repeatedly followed complainant on her daily commute and used abusive force when confronted. Witness testimony and CCTV footage corroborated the incident.",
        "outcome": {"disposal_type": "convicted", "sentence_or_relief": "1 year rigorous imprisonment"},
        "keywords": ["stalking", "outraging modesty", "cctv footage", "commute harassment"],
    },
    {
        "case_id": "DC-KA-2024-000412",
        "court_name": "District Court, Bengaluru Rural",
        "state": "Karnataka",
        "district": "Bengaluru Rural",
        "court_level": "district",
        "year": 2024,
        "crime_category": "crimes_against_senior_citizens",
        "statute_sections": [
            {"act": "Senior Citizens Act", "section": "23", "label": "Transfer of property declared void"}
        ],
        "fact_summary": "76-year-old retired complainant gifted his residential house to his son on the express promise of maintenance and medical care. Son abandoned parent and evicted him. Tribunal declared gift deed void and restored possession.",
        "outcome": {"disposal_type": "settled", "sentence_or_relief": "Gift deed declared void; property possession restored to senior citizen"},
        "keywords": ["elder abuse", "gift deed void", "senior citizens maintenance", "eviction"],
    },
    {
        "case_id": "DC-UP-2024-000671",
        "court_name": "District & Sessions Court, Noida (Gautam Buddha Nagar)",
        "state": "Uttar Pradesh",
        "district": "Gautam Buddha Nagar",
        "court_level": "district",
        "year": 2024,
        "crime_category": "cyber_fraud",
        "statute_sections": [
            {"act": "IT Act", "section": "66D", "label": "Cheating by personation"},
            {"act": "BNS", "section": "318", "label": "Cheating"}
        ],
        "fact_summary": "Victim subjected to 'digital arrest' video call by perpetrators displaying fake police emblems and CBI badges, demanding RTGS transfer of INR 4,00,000 into a mule account.",
        "outcome": {"disposal_type": "convicted", "sentence_or_relief": "2 years imprisonment; mule account funds frozen and restitution ordered"},
        "keywords": ["digital arrest", "CBI impersonation", "fake police badge", "mule account", "restitution"],
    },
    {
        "case_id": "DC-DL-2024-001042",
        "court_name": "District Court, Tis Hazari",
        "state": "Delhi",
        "district": "Central Delhi",
        "court_level": "district",
        "year": 2024,
        "crime_category": "crimes_against_women",
        "statute_sections": [
            {"act": "IPC", "section": "498A", "label": "Cruelty by husband or in-laws"},
            {"act": "DV Act", "section": "3", "label": "Domestic violence definition and protection relief"},
            {"act": "DV Act", "section": "18", "label": "Protection orders"}
        ],
        "fact_summary": "Complainant was subjected to persistent mental and physical cruelty and demands for dowry by husband and in-laws, leading to expulsion from the shared matrimonial home. Magistrate court passed an interim protection order prohibiting respondent entry and granted interim maintenance.",
        "outcome": {"disposal_type": "protection_order_granted", "sentence_or_relief": "Protection order granted under DV Act Section 18; monthly interim maintenance awarded"},
        "keywords": ["domestic violence", "498A cruelty", "protection order", "shared household", "interim maintenance", "dowry harassment"],
    },
    {
        "case_id": "DC-KA-2024-000781",
        "court_name": "Family Court / District Court, Bengaluru",
        "state": "Karnataka",
        "district": "Bengaluru Urban",
        "court_level": "district",
        "year": 2024,
        "crime_category": "matrimonial_disputes",
        "statute_sections": [
            {"act": "Hindu Marriage Act", "section": "13B", "label": "Divorce by mutual consent"},
            {"act": "CrPC", "section": "125", "label": "Order for maintenance"}
        ],
        "fact_summary": "Spouses living separately for over 18 months filed a joint petition for mutual consent divorce under Section 13B of the Hindu Marriage Act. Parties executed a settlement agreement resolving permanent alimony and child custody amicably. Court waived remaining waiting period and dissolved the marriage.",
        "outcome": {"disposal_type": "divorce_decree_granted", "sentence_or_relief": "Decree of divorce granted by mutual consent; settlement terms recorded"},
        "keywords": ["mutual consent divorce", "13B HMA", "permanent alimony", "settlement agreement", "child custody", "cooling-off waiver"],
    }
]


def build_embedding_text(doc: Dict[str, Any]) -> str:
    """
    Standardized embedding text representation matching dataset_pipeline.py.
    Concatenates: crime category + statute labels + fact summary + keywords + outcome.
    """
    if doc.get("source_type") == "statute":
        parts = [
            f"Statute: {doc.get('act', '')} Section {doc.get('section', '')}.",
            f"Title: {doc.get('title', '')}.",
            f"Explanation: {doc.get('explanation', '')}.",
            f"Category: {doc.get('crime_category', '')}.",
            f"Keywords: {', '.join(doc.get('keywords', []))}.",
        ]
    else:
        statute_labels = ", ".join(
            f"{s.get('act', '')} {s.get('section', '')} ({s.get('label', '')})"
            for s in doc.get("statute_sections", [])
        )
        parts = [
            f"Crime category: {doc.get('crime_category', '')}.",
            f"Relevant sections: {statute_labels}.",
            f"Facts: {doc.get('fact_summary', '')}.",
            f"Keywords: {', '.join(doc.get('keywords', []))}.",
            f"Outcome: {doc.get('outcome', {}).get('disposal_type', '')}.",
        ]
    return " ".join(p for p in parts if p.strip() != ".")


def load_raw_cases_from_disk(raw_dir: str) -> List[Dict[str, Any]]:
    """Loads JSON files from a specified raw_cases directory."""
    cases: List[Dict[str, Any]] = []
    if not os.path.isdir(raw_dir):
        return cases

    for path in glob.glob(f"{raw_dir}/*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("case_id"):
                    data["source_type"] = "case"
                    data["source_id"] = f"case:{data['case_id']}"
                    if not data.get("crime_category"):
                        sections = [s.get("section") for s in data.get("statute_sections", [])]
                        for sec in sections:
                            if sec in {"66D", "66C"}:
                                data["crime_category"] = "cyber_fraud"
                                break
                            elif sec in {"303", "305", "379"}:
                                data["crime_category"] = "theft_burglary"
                                break
                            elif sec in {"23"}:
                                data["crime_category"] = "crimes_against_senior_citizens"
                                break
                            elif sec in {"354", "354D", "74"}:
                                data["crime_category"] = "crimes_against_women"
                                break
                            elif sec in {"318", "420", "468"}:
                                data["crime_category"] = "cheating_forgery"
                                break
                    cases.append(data)
        except Exception as e:
            logger.warning(f"Error reading case file {path}: {e}")
    return cases


def load_indian_kanoon_cases(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Loads compiled Indian Kanoon cases from JSON (default: chatbot/data/indian_cases_100.json or indian_cases_100.json).
    Normalizes category names and structures records for vector store indexing.
    """
    candidates = [
        file_path,
        os.path.join(os.path.dirname(__file__), "..", "data", "indian_cases_100.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "indian_cases_100.json"),
        "chatbot/data/indian_cases_100.json",
        "indian_cases_100.json",
    ]
    target_path = None
    for c in candidates:
        if c and os.path.isfile(c):
            target_path = c
            break

    if not target_path:
        return []

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except Exception as e:
        logger.warning(f"Failed reading Indian Kanoon cases from {target_path}: {e}")
        return []

    cases: List[Dict[str, Any]] = []
    category_map = {
        "senior_citizens": "crimes_against_senior_citizens",
    }

    for item in raw_data:
        tid = item.get("tid") or item.get("id")
        raw_cat = item.get("category", "other")
        category = category_map.get(raw_cat, raw_cat)
        title = item.get("title", f"Indian Kanoon Case {tid}")
        headline = item.get("headline", "")
        doc_url = item.get("doc_url") or (f"https://indiankanoon.org/doc/{tid}/" if tid else "")

        case_id = f"IK-{tid}" if tid else f"IK-{len(cases)+1}"
        record: Dict[str, Any] = {
            "case_id": case_id,
            "court_name": "Indian Kanoon Precedent",
            "court_level": "precedent",
            "title": title,
            "crime_category": category,
            "fact_summary": headline or title,
            "statute_sections": [],
            "keywords": [w.strip() for w in title.lower().split() if len(w) > 3],
            "outcome": {"disposal_type": "judgment", "sentence_or_relief": "See full judgment on Indian Kanoon"},
            "tid": tid,
            "url": doc_url,
            "source_type": "case",
            "source_id": f"case:{case_id}",
            "embedding_text": f"Precedent: {title}. Category: {category}. Facts and Headline: {headline}. Source: Indian Kanoon ({doc_url}).",
        }
        cases.append(record)

    logger.info(f"Loaded {len(cases)} Indian Kanoon precedent cases from {target_path}.")
    return cases


def load_and_index_default_data(
    vector_store: BaseVectorStore,
    raw_dir: Optional[str] = None,
):
    """
    Loads default statutes, raw cases from disk, and Indian Kanoon precedent records,
    attaches standard embedding_text, and populates the vector store.
    """
    docs_to_index: List[Dict[str, Any]] = []

    # 1. Ingest Statutes
    for stat in DEFAULT_STATUTE_RECORDS:
        stat["embedding_text"] = build_embedding_text(stat)
        docs_to_index.append(stat)

    # 2. Ingest Cases from raw_cases directory if present
    disk_cases = []
    if raw_dir:
        disk_cases = load_raw_cases_from_disk(raw_dir)
        logger.info(f"Loaded {len(disk_cases)} raw cases from directory: {raw_dir}")

    # 3. Ingest Indian Kanoon precedent cases (from indian_cases_100.json)
    kanoon_cases = load_indian_kanoon_cases()

    # Combine disk cases, Indian Kanoon cases, and prototype seed cases (avoid duplicate case_ids)
    seen_ids = set()
    for c in disk_cases + kanoon_cases + DEFAULT_CASE_RECORDS:
        case_id = c.get("case_id")
        if case_id in seen_ids:
            continue
        seen_ids.add(case_id)
        c["source_type"] = "case"
        c["source_id"] = f"case:{case_id}"
        if not c.get("embedding_text"):
            c["embedding_text"] = build_embedding_text(c)
        docs_to_index.append(c)

    # Push to vector store
    vector_store.add_documents(docs_to_index)
    logger.info(f"Successfully populated vector store with {len(docs_to_index)} legal documents.")
