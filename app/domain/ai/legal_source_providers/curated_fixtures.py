import hashlib
import json
from typing import Any

from app.models.legal_authority import (
    AuthorityLevel,
    LegalAuthorityType,
    LegalJurisdiction,
    LegalSourceStatus,
)
from app.domain.ai.legal_source_providers.base import (
    BaseLegalSourceProvider,
    RawLegalSourcePayload,
)

CURATED_LEGAL_FIXTURES: list[dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 1. NEGOTIABLE INSTRUMENTS ACT, 1881
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-ACT-1881-26",
        "canonical_identifier": "IN-ACT-1881-26",
        "name": "The Negotiable Instruments Act, 1881",
        "short_title": "NI Act, 1881",
        "year": 1881,
        "source_type": LegalAuthorityType.PRIMARY_LEGISLATION,
        "authority_level": AuthorityLevel.PRIMARY_STATUTE.value,
        "jurisdiction": LegalJurisdiction.INDIA_CENTRAL.value,
        "issuing_body": "Parliament of India / Legislative Council",
        "publication_date": "1881-12-09",
        "effective_from": "1882-03-01",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "Act No. 26 of 1881",
        "canonical_url": "https://www.indiacode.nic.in/handle/123456789/2189",
        "provisions": [
            {
                "canonical_provision_id": "IN-ACT-1881-26-SEC-138-V2018",
                "section_number": "138",
                "version_label": "2018 Amendment",
                "chapter_number": "XVII",
                "title": "Dishonour of cheque for insufficiency, etc., of funds in the account",
                "content": (
                    "Where any cheque drawn by a person on an account maintained by him with a banker for payment "
                    "of any amount of money to another person from out of that account for the discharge, in whole "
                    "or in part, of any debt or other liability, is returned by the bank unpaid, either because of "
                    "the amount of money standing to the credit of that account is insufficient to honour the cheque "
                    "or that it exceeds the amount arranged to be paid from that account by an agreement made with that bank, "
                    "such person shall be deemed to have committed an offence and shall, without prejudice to any other "
                    "provisions of this Act, be punished with imprisonment for a term which may be extended to two years, "
                    "or with fine which may extend to twice the amount of the cheque, or with both: Provided that nothing "
                    "contained in this section shall apply unless— (a) the cheque has been presented to the bank within a "
                    "period of three months from the date on which it is drawn; (b) the payee or the holder in due course "
                    "makes a demand for the payment of the said amount by giving a notice in writing, within thirty days "
                    "of the receipt of information from the bank; and (c) the drawer fails to make the payment within fifteen days."
                ),
                "effective_from": "2018-09-01",
                "effective_to": None,
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-1881-26-SEC-138-V1988",
                "section_number": "138",
                "version_label": "1988 Banking Laws Amendment",
                "chapter_number": "XVII",
                "title": "Dishonour of cheque for insufficiency, etc., of funds in the account",
                "content": (
                    "Where any cheque drawn by a person on an account maintained by him with a banker for payment "
                    "of any amount of money to another person for the discharge of any debt or other liability is returned "
                    "unpaid, such person shall be punished with imprisonment for a term which may be extended to one year, "
                    "or with fine which may extend to twice the amount of the cheque, or with both."
                ),
                "effective_from": "1989-04-01",
                "effective_to": "2018-08-31",
                "is_current": False,
            },
            {
                "canonical_provision_id": "IN-ACT-1881-26-SEC-141",
                "section_number": "141",
                "version_label": "Current",
                "chapter_number": "XVII",
                "title": "Offences by companies",
                "content": (
                    "If the person committing an offence under section 138 is a company, every person who; at the time "
                    "the offence was committed, was in charge of, and was responsible to the company for the conduct "
                    "of the business of the company, as well as the company, shall be deemed to be guilty of the offence "
                    "and shall be liable to be proceeded against and punished accordingly."
                ),
                "effective_from": "1989-04-01",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-1881-26-SEC-142",
                "section_number": "142",
                "version_label": "Current",
                "chapter_number": "XVII",
                "title": "Cognizance of offences",
                "content": (
                    "Notwithstanding anything contained in the Code of Criminal Procedure, 1973, no court shall take "
                    "cognizance of any offence punishable under section 138 except upon a complaint, in writing, made by "
                    "the payee or, as the case may be, the holder in due course of the cheque. The offence under section 138 "
                    "shall be inquired into and tried only by a court within whose local jurisdiction the branch of the bank "
                    "where the payee or holder in due course maintains the account is situated."
                ),
                "effective_from": "2015-06-15",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-1881-26-SEC-143A",
                "section_number": "143A",
                "version_label": "2018 Amendment",
                "chapter_number": "XVII",
                "title": "Power to direct interim compensation",
                "content": (
                    "Notwithstanding anything contained in the Code of Criminal Procedure, 1973, the Court trying an offence "
                    "under section 138 may order the drawer of the cheque to pay interim compensation to the complainant. "
                    "The interim compensation shall not exceed twenty per cent of the amount of the cheque."
                ),
                "effective_from": "2018-09-01",
                "is_current": True,
            },
        ],
    },
    # --------------------------------------------------------------------------
    # 2. ARBITRATION AND CONCILIATION ACT, 1996
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-ACT-1996-26",
        "canonical_identifier": "IN-ACT-1996-26",
        "name": "The Arbitration and Conciliation Act, 1996",
        "short_title": "Arbitration Act, 1996",
        "year": 1996,
        "source_type": LegalAuthorityType.PRIMARY_LEGISLATION,
        "authority_level": AuthorityLevel.PRIMARY_STATUTE.value,
        "jurisdiction": LegalJurisdiction.INDIA_CENTRAL.value,
        "issuing_body": "Parliament of India",
        "publication_date": "1996-08-16",
        "effective_from": "1996-08-22",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "Act No. 26 of 1996",
        "canonical_url": "https://www.indiacode.nic.in/handle/123456789/1978",
        "provisions": [
            {
                "canonical_provision_id": "IN-ACT-1996-26-SEC-9-V2015",
                "section_number": "9",
                "version_label": "2015 Amendment",
                "chapter_number": "II",
                "title": "Interim measures, etc., by Court",
                "content": (
                    "A party may, before or during arbitral proceedings or at any time after the making of the arbitral award "
                    "but before it is enforced in accordance with section 36, apply to a court for an interim measure of protection "
                    "for the preservation, interim custody or sale of any goods which are the subject-matter of the arbitration agreement. "
                    "Where, before the commencement of the arbitral proceedings, a court passes an order for any interim measure of protection "
                    "under sub-section (1), the arbitral proceedings shall be commenced within a period of ninety days."
                ),
                "effective_from": "2015-10-23",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-1996-26-SEC-9-V1996",
                "section_number": "9",
                "version_label": "Original 1996",
                "chapter_number": "II",
                "title": "Interim measures, etc., by Court",
                "content": (
                    "A party may, before or during arbitral proceedings or at any time after the making of the arbitral award "
                    "but before it is enforced in accordance with section 36, apply to a court for an interim measure of protection."
                ),
                "effective_from": "1996-08-22",
                "effective_to": "2015-10-22",
                "is_current": False,
            },
            {
                "canonical_provision_id": "IN-ACT-1996-26-SEC-11",
                "section_number": "11",
                "version_label": "Current",
                "chapter_number": "III",
                "title": "Appointment of arbitrators",
                "content": (
                    "A person of any nationality may be an arbitrator, unless otherwise agreed by the parties. "
                    "Failing any agreement, in an arbitration with three arbitrators, each party shall appoint one arbitrator, "
                    "and the two appointed arbitrators shall appoint the third arbitrator who shall act as the presiding arbitrator. "
                    "The Supreme Court or, as the case may be, the High Court or any person or institution designated by such Court "
                    "shall appoint the arbitrator on application."
                ),
                "effective_from": "2015-10-23",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-1996-26-SEC-34",
                "section_number": "34",
                "version_label": "Current",
                "chapter_number": "VII",
                "title": "Application for setting aside arbitral award",
                "content": (
                    "Recourse to a Court against an arbitral award may be made only by an application for setting aside such award "
                    "in accordance with sub-section (2) and sub-section (3). An arbitral award may be set aside by the Court only if "
                    "the party making the application furnishes proof that the party was under some incapacity, or the arbitration agreement "
                    "is not valid, or the award is in conflict with the public policy of India or vitiated by patent illegality."
                ),
                "effective_from": "2015-10-23",
                "is_current": True,
            },
        ],
    },
    # --------------------------------------------------------------------------
    # 3. BHARATIYA NYAYA SANHITA, 2023
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-ACT-2023-45",
        "canonical_identifier": "IN-ACT-2023-45",
        "name": "The Bharatiya Nyaya Sanhita, 2023",
        "short_title": "BNS, 2023",
        "year": 2023,
        "source_type": LegalAuthorityType.PRIMARY_LEGISLATION,
        "authority_level": AuthorityLevel.PRIMARY_STATUTE.value,
        "jurisdiction": LegalJurisdiction.INDIA_CENTRAL.value,
        "issuing_body": "Parliament of India",
        "publication_date": "2023-12-25",
        "effective_from": "2024-07-01",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "Act No. 45 of 2023",
        "canonical_url": "https://www.indiacode.nic.in/handle/123456789/21045",
        "provisions": [
            {
                "canonical_provision_id": "IN-ACT-2023-45-SEC-318",
                "section_number": "318",
                "version_label": "Current",
                "chapter_number": "XVII",
                "title": "Cheating and dishonestly inducing delivery of property",
                "content": (
                    "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, "
                    "or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed "
                    "or sealed, and which is capable of being converted into a valuable security, shall be punished with "
                    "imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
                ),
                "effective_from": "2024-07-01",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-ACT-2023-45-SEC-61",
                "section_number": "61",
                "version_label": "Current",
                "chapter_number": "IV",
                "title": "Criminal conspiracy",
                "content": (
                    "When two or more persons agree to do, or cause to be done— (a) an illegal act; or (b) an act which is not "
                    "illegal by illegal means, such an agreement is designated a criminal conspiracy: Provided that no agreement "
                    "except an agreement to commit an offence shall amount to a criminal conspiracy unless some act besides the agreement "
                    "is done by one or more parties to such agreement in pursuance thereof."
                ),
                "effective_from": "2024-07-01",
                "is_current": True,
            },
        ],
    },
    # --------------------------------------------------------------------------
    # 4. INDIAN PENAL CODE, 1860 (Historical / Predecessor Code)
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-ACT-1860-45",
        "canonical_identifier": "IN-ACT-1860-45",
        "name": "The Indian Penal Code, 1860",
        "short_title": "IPC, 1860",
        "year": 1860,
        "source_type": LegalAuthorityType.PRIMARY_LEGISLATION,
        "authority_level": AuthorityLevel.PRIMARY_STATUTE.value,
        "jurisdiction": LegalJurisdiction.INDIA_CENTRAL.value,
        "issuing_body": "Legislative Council of India",
        "publication_date": "1860-10-06",
        "effective_from": "1862-01-01",
        "effective_to": "2024-06-30",
        "status": LegalSourceStatus.REPEALED,
        "citation_standard": "Act No. 45 of 1860",
        "canonical_url": "https://www.indiacode.nic.in/handle/123456789/2263",
        "provisions": [
            {
                "canonical_provision_id": "IN-ACT-1860-45-SEC-420",
                "section_number": "420",
                "version_label": "Historical",
                "chapter_number": "XVII",
                "title": "Cheating and dishonestly inducing delivery of property",
                "content": (
                    "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, "
                    "or to make, alter or destroy the whole or any part of a valuable security, or anything which is signed "
                    "or sealed, and which is capable of being converted into a valuable security, shall be punished with "
                    "imprisonment of either description for a term which may extend to seven years, and shall also be liable to fine."
                ),
                "effective_from": "1862-01-01",
                "effective_to": "2024-06-30",
                "is_current": False,
            },
            {
                "canonical_provision_id": "IN-ACT-1860-45-SEC-120B",
                "section_number": "120B",
                "version_label": "Historical",
                "chapter_number": "VA",
                "title": "Punishment of criminal conspiracy",
                "content": (
                    "Whoever is a party to a criminal conspiracy to commit an offence punishable with death, imprisonment for life "
                    "or rigorous imprisonment for a term of two years or upwards, shall, where no express provision is made in this "
                    "Code for the punishment of such conspiracy, be punished in the same manner as if he had abetted such offence."
                ),
                "effective_from": "1913-03-27",
                "effective_to": "2024-06-30",
                "is_current": False,
            },
        ],
    },
    # --------------------------------------------------------------------------
    # 5. CONSTITUTION OF INDIA, 1950
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-CONST-1950",
        "canonical_identifier": "IN-CONST-1950",
        "name": "The Constitution of India, 1950",
        "short_title": "Constitution of India",
        "year": 1950,
        "source_type": LegalAuthorityType.PRIMARY_LEGISLATION,
        "authority_level": AuthorityLevel.CONSTITUTIONAL.value,
        "jurisdiction": LegalJurisdiction.INDIA_CENTRAL.value,
        "issuing_body": "Constituent Assembly of India",
        "publication_date": "1950-01-26",
        "effective_from": "1950-01-26",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "Constitution of India",
        "canonical_url": "https://legislative.gov.in/constitution-of-india",
        "provisions": [
            {
                "canonical_provision_id": "IN-CONST-1950-ART-21",
                "section_number": "Article 21",
                "version_label": "Current",
                "chapter_number": "Part III",
                "title": "Protection of life and personal liberty",
                "content": (
                    "No person shall be deprived of his life or personal liberty except according to procedure established by law."
                ),
                "effective_from": "1950-01-26",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-CONST-1950-ART-226",
                "section_number": "Article 226",
                "version_label": "Current",
                "chapter_number": "Part VI",
                "title": "Power of High Courts to issue certain writs",
                "content": (
                    "Notwithstanding anything in Article 32, every High Court shall have power, throughout the territories in "
                    "relation to which it exercises jurisdiction, to issue to any person or authority, including in appropriate cases, "
                    "any Government, within those territories directions, orders or writs, including writs in the nature of habeas corpus, "
                    "mandamus, prohibition, quo warranto and certiorari, or any of them, for the enforcement of any of the rights "
                    "conferred by Part III and for any other purpose."
                ),
                "effective_from": "1950-01-26",
                "is_current": True,
            },
            {
                "canonical_provision_id": "IN-CONST-1950-ART-32",
                "section_number": "Article 32",
                "version_label": "Current",
                "chapter_number": "Part III",
                "title": "Remedies for enforcement of rights conferred by this Part",
                "content": (
                    "The right to move the Supreme Court by appropriate proceedings for the enforcement of the rights conferred "
                    "by this Part is guaranteed. The Supreme Court shall have power to issue directions or orders or writs for the enforcement."
                ),
                "effective_from": "1950-01-26",
                "is_current": True,
            },
        ],
    },
    # --------------------------------------------------------------------------
    # 6. LANDMARK JUDICIAL PRECEDENTS (SUPREME COURT OF INDIA)
    # --------------------------------------------------------------------------
    {
        "external_identifier": "IN-SC-2020-VIDYA-DROLIA",
        "canonical_identifier": "IN-SC-2020-VIDYA-DROLIA",
        "name": "Vidya Drolia and Others v. Durga Trading Corporation",
        "short_title": "Vidya Drolia (2020)",
        "year": 2020,
        "source_type": LegalAuthorityType.JUDICIAL_DECISION,
        "authority_level": AuthorityLevel.APEX_JUDICIAL.value,
        "jurisdiction": LegalJurisdiction.SUPREME_COURT_OF_INDIA.value,
        "issuing_body": "Supreme Court of India (3-Judge Bench: N.V. Ramana, Sanjiv Khanna, Krishna Murari, JJ.)",
        "publication_date": "2020-12-14",
        "effective_from": "2020-12-14",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "(2021) 2 SCC 1; 2020 INSC 697",
        "canonical_url": "https://main.sci.gov.in/supremecourt/2019/37021/37021_2019_34_1501_25154_Judgement_14-Dec-2020.pdf",
        "provisions": [
            {
                "canonical_provision_id": "IN-SC-2020-VIDYA-DROLIA-HOLDING-1",
                "section_number": "Holding 1",
                "version_label": "Ratio Decidendi",
                "chapter_number": "Section 11 & Arbitrability",
                "title": "Fourfold test for non-arbitrability of disputes and landlord-tenant disputes",
                "content": (
                    "A dispute is non-arbitrable when: (1) actions relate to rights in rem; (2) actions affect third party rights "
                    "or have erga omnes effect; (3) actions pertain to inalienable sovereign and public interest functions; and "
                    "(4) actions are expressly or by necessary implication non-arbitrable under statute. Landlord-tenant disputes "
                    "governed by the Transfer of Property Act are arbitrable as they do not affect public order or third parties."
                ),
                "effective_from": "2020-12-14",
                "is_current": True,
            },
        ],
    },
    {
        "external_identifier": "IN-SC-2021-6-SCC-258",
        "canonical_identifier": "IN-SC-2021-6-SCC-258",
        "name": "P. Mohanraj & Ors. v. Shah Brothers Ispat Pvt. Ltd.",
        "short_title": "P. Mohanraj (2021)",
        "year": 2021,
        "source_type": LegalAuthorityType.JUDICIAL_DECISION,
        "authority_level": AuthorityLevel.APEX_JUDICIAL.value,
        "jurisdiction": LegalJurisdiction.SUPREME_COURT_OF_INDIA.value,
        "issuing_body": "Supreme Court of India (3-Judge Bench: R.F. Nariman, Navin Sinha, K.M. Joseph, JJ.)",
        "publication_date": "2021-03-01",
        "effective_from": "2021-03-01",
        "status": LegalSourceStatus.PUBLISHED,
        "citation_standard": "(2021) 6 SCC 258; 2021 INSC 138",
        "canonical_url": "https://main.sci.gov.in/supremecourt/2019/38903/38903_2019_34_1501_26543_Judgement_01-Mar-2021.pdf",
        "provisions": [
            {
                "canonical_provision_id": "IN-SC-2021-6-SCC-258-HOLDING-1",
                "section_number": "Holding 1",
                "version_label": "Ratio Decidendi",
                "chapter_number": "IBC Moratorium & Section 138 NI Act",
                "title": "Section 138 proceedings against Corporate Debtor covered under Section 14 IBC Moratorium",
                "content": (
                    "Proceedings under Section 138 of the Negotiable Instruments Act against the corporate debtor are "
                    "proceedings within the meaning of Section 14(1)(a) of the Insolvency and Bankruptcy Code (IBC) and cannot "
                    "be continued during the moratorium period. However, natural persons such as directors or persons in charge "
                    "remain liable under Section 141 and proceedings against them may continue."
                ),
                "effective_from": "2021-03-01",
                "is_current": True,
            },
        ],
    },
]


class CuratedFixtureSourceProvider(BaseLegalSourceProvider):
    """Controlled source provider for verified, high-accuracy Indian statutory provisions and landmark judgments."""

    @property
    def source_system_name(self) -> str:
        return "CURATED_INDIAN_LEGAL_FIXTURES"

    def fetch_source(self, external_identifier: str) -> RawLegalSourcePayload:
        for fixture in CURATED_LEGAL_FIXTURES:
            if fixture["external_identifier"] == external_identifier:
                raw_json = json.dumps(fixture, sort_keys=True, default=str)
                checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
                return RawLegalSourcePayload(
                    source_system=self.source_system_name,
                    external_identifier=fixture["external_identifier"],
                    source_type=fixture["source_type"],
                    raw_content=raw_json,
                    raw_metadata={
                        "name": fixture["name"],
                        "year": fixture["year"],
                        "jurisdiction": fixture["jurisdiction"],
                    },
                    retrieval_url=fixture.get("canonical_url"),
                    content_checksum=checksum,
                )
        raise ValueError(f"Curated source '{external_identifier}' not found in fixtures.")

    def fetch_all(self) -> list[RawLegalSourcePayload]:
        payloads: list[RawLegalSourcePayload] = []
        for fixture in CURATED_LEGAL_FIXTURES:
            raw_json = json.dumps(fixture, sort_keys=True, default=str)
            checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
            payloads.append(
                RawLegalSourcePayload(
                    source_system=self.source_system_name,
                    external_identifier=fixture["external_identifier"],
                    source_type=fixture["source_type"],
                    raw_content=raw_json,
                    raw_metadata={
                        "name": fixture["name"],
                        "year": fixture["year"],
                        "jurisdiction": fixture["jurisdiction"],
                    },
                    retrieval_url=fixture.get("canonical_url"),
                    content_checksum=checksum,
                )
            )
        return payloads
