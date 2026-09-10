import datetime

from app.models.legal_authority import (
    AuthorityLevel,
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSourceStatus,
)
from app.schemas.legal_authority import (
    LegalAuthorityIngestProvision,
    LegalAuthorityIngestRequest,
)

CURATED_STATUTES: list[LegalAuthorityIngestRequest] = [
    # 1. Negotiable Instruments Act 1881
    LegalAuthorityIngestRequest(
        canonical_identifier="IN-ACT-1881-26",
        name="Negotiable Instruments Act 1881",
        short_title="NI Act",
        year=1881,
        source_type=LegalAuthorityType.PRIMARY_LEGISLATION,
        authority_level=AuthorityLevel.PRIMARY_STATUTE.value,
        jurisdiction=LegalJurisdiction.INDIA_CENTRAL.value,
        issuing_body="Parliament of India",
        publication_date=datetime.date(1881, 12, 9),
        effective_from=datetime.date(1882, 3, 1),
        status=LegalSourceStatus.PUBLISHED,
        citation_standard="Act No. 26 of 1881",
        canonical_url="https://indiacode.nic.in/handle/123456789/2189",
        provisions=[
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-ACT-1881-26-SEC-138-ORIG",
                section_number="138",
                version_label="1988 Original Provision",
                chapter_number="XVII",
                title="Dishonour of cheque for insufficiency, etc., of funds in the account",
                content=(
                    "Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money "
                    "to another person from out of that account for the discharge, in whole or in part, of any debt or other liability, "
                    "is returned by the bank unpaid, either because of the amount of money standing to the credit of that account is insufficient "
                    "or that it exceeds the amount arranged to be paid from that account, such person shall be deemed to have committed an offence "
                    "and shall be punished with imprisonment for a term which may extend to one year, or with fine which may extend to twice the amount of the cheque, or with both."
                ),
                effective_from=datetime.date(1989, 4, 1),
                effective_to=datetime.date(2002, 12, 5),
                is_current=False,
            ),
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-ACT-1881-26-SEC-138-V2018",
                section_number="138",
                version_label="2018 Amended Provision",
                chapter_number="XVII",
                title="Dishonour of cheque for insufficiency, etc., of funds in the account (Amended)",
                content=(
                    "Where any cheque drawn by a person on an account maintained by him with a banker for payment of any amount of money "
                    "to another person from out of that account for the discharge of any debt or other liability is returned unpaid, "
                    "such person shall be punished with imprisonment for a term which may be extended to two years, or with fine which may extend "
                    "to twice the amount of the cheque, or with both. Provided that the cheque was presented within three months and notice demanding "
                    "payment was made within thirty days of the receipt of information from the bank."
                ),
                effective_from=datetime.date(2018, 9, 1),
                effective_to=None,
                is_current=True,
            ),
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-ACT-1881-26-SEC-143A-V2018",
                section_number="143A",
                version_label="2018 Interim Compensation Provision",
                chapter_number="XVII",
                title="Power to direct interim compensation",
                content=(
                    "Notwithstanding anything contained in the Code of Criminal Procedure 1973, the Court trying an offence under section 138 "
                    "may order the drawer of the cheque to pay interim compensation to the complainant not exceeding twenty per cent of the amount of the cheque."
                ),
                effective_from=datetime.date(2018, 9, 1),
                effective_to=None,
                is_current=True,
            ),
        ],
    ),
    # 2. Indian Contract Act 1872
    LegalAuthorityIngestRequest(
        canonical_identifier="IN-ACT-1872-9",
        name="Indian Contract Act 1872",
        short_title="Contract Act",
        year=1872,
        source_type=LegalAuthorityType.PRIMARY_LEGISLATION,
        authority_level=AuthorityLevel.PRIMARY_STATUTE.value,
        jurisdiction=LegalJurisdiction.INDIA_CENTRAL.value,
        issuing_body="Imperial Legislative Council / Parliament of India",
        publication_date=datetime.date(1872, 4, 25),
        effective_from=datetime.date(1872, 9, 1),
        status=LegalSourceStatus.PUBLISHED,
        citation_standard="Act No. 9 of 1872",
        canonical_url="https://indiacode.nic.in/handle/123456789/2187",
        provisions=[
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-ACT-1872-9-SEC-27-CURR",
                section_number="27",
                version_label="Current",
                chapter_number="II",
                title="Agreement in restraint of trade, void",
                content=(
                    "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind, "
                    "is to that extent void. Exception 1: One who sells the goodwill of a business may agree with the buyer to refrain from carrying on "
                    "a similar business within specified local limits, so long as the buyer carries on a like business."
                ),
                effective_from=datetime.date(1872, 9, 1),
                effective_to=None,
                is_current=True,
            ),
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-ACT-1872-9-SEC-73-CURR",
                section_number="73",
                version_label="Current",
                chapter_number="VI",
                title="Compensation for loss or damage caused by breach of contract",
                content=(
                    "When a contract has been broken, the party who suffers by such breach is entitled to receive, from the party who has broken the contract, "
                    "compensation for any loss or damage caused to him thereby, which naturally arose in the usual course of things from such breach, "
                    "or which the parties knew, when they made the contract, to be likely to result from the breach of it. "
                    "Such compensation is not to be given for any remote and indirect loss or damage sustained by reason of the breach."
                ),
                effective_from=datetime.date(1872, 9, 1),
                effective_to=None,
                is_current=True,
            ),
        ],
    ),
    # 3. Supreme Court Binding Precedent
    LegalAuthorityIngestRequest(
        canonical_identifier="IN-SC-2020-20-SCC-760",
        name="Perkins Eastman Architects DPC v. HSCC (India) Ltd",
        short_title="Perkins Eastman Case",
        year=2020,
        source_type=LegalAuthorityType.JUDICIAL_DECISION,
        authority_level=AuthorityLevel.APEX_JUDICIAL.value,
        jurisdiction=LegalJurisdiction.SUPREME_COURT_OF_INDIA.value,
        issuing_body="Supreme Court of India",
        publication_date=datetime.date(2019, 11, 26),
        effective_from=datetime.date(2019, 11, 26),
        status=LegalSourceStatus.PUBLISHED,
        citation_standard="(2020) 20 SCC 760",
        canonical_url="https://main.sci.gov.in/supremecourt/2019/33580/33580_2019_12_1501_18804_Judgement_26-Nov-2019.pdf",
        provisions=[
            LegalAuthorityIngestProvision(
                canonical_provision_id="IN-SC-2020-20-SCC-760-PARA-21",
                section_number="Para 21",
                version_label="Binding Ruling",
                chapter_number="Ratio Decidendi",
                title="Ineligibility of interested party to appoint sole arbitrator",
                content=(
                    "A person who has an interest in the outcome or decision of the dispute must not have the power to appoint a sole arbitrator. "
                    "The independence and impartiality of the arbitrator being the hallmark of arbitration, a person who is ineligible to act as an arbitrator "
                    "under Section 12(5) read with the Seventh Schedule of the Arbitration and Conciliation Act 1996 cannot unilaterally nominate an arbitrator."
                ),
                effective_from=datetime.date(2019, 11, 26),
                effective_to=None,
                is_current=True,
            ),
        ],
    ),
]
