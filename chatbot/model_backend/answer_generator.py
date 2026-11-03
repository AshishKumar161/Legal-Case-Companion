"""
Answer Generator (Drafter) Module for LCC AI/Model Backend.
Responsible for:
1. Drafting compassionate, structured legal-information responses using EXCLUSIVELY retrieved evidence.
2. Demystifying complex legal jargon into plain language.
3. Outlining possible next steps and key documentation to preserve.
4. Referencing similar district court case precedents with explicit outcome disclaimers.
5. Strict anti-hallucination: Never invents laws, section numbers, penalties, or case citations.
6. Attaching inline citations [source_id] to all substantive claims.
"""

from __future__ import annotations
import json
import re
import logging
from typing import List, Dict, Any, Optional

from .schemas import (
    RerankedCandidate,
    IntakeResult,
    LegalReasoningResult,
    GeneratedAnswer,
)
from .llama_model import LLaMAModel
from .prompts import ANSWER_GENERATOR_PROMPT, LEGAL_DISCLAIMER

logger = logging.getLogger("lcc.answer_generator")


class AnswerGenerator:
    """
    Generates structured, plain-language legal responses strictly grounded in retrieved evidence.
    """

    def __init__(self, llama_model: LLaMAModel):
        self.llm = llama_model

    def generate(
        self,
        intake_result: IntakeResult,
        reasoning_result: LegalReasoningResult,
        reranked_candidates: List[RerankedCandidate],
    ) -> GeneratedAnswer:
        """
        Drafts a response based exclusively on reranked candidate evidence chunks.
        """
        # Build evidence context block
        evidence_lines = []
        valid_source_ids = []

        for cand in reranked_candidates:
            src = cand.source
            valid_source_ids.append(src.source_id)
            source_header = f"[{src.source_id}] {src.citation} ({src.source_type.upper()}):"
            source_content = f"Title: {src.title}\nContent: {src.text}"
            if src.source_type == "case":
                url = src.metadata.get("url")
                if url:
                    source_content += f"\nIndian Kanoon Precedent URL: {url}"
                if "outcome" in src.metadata and src.metadata.get("outcome"):
                    outcome = src.metadata.get("outcome", {})
                    source_content += f"\nRecorded Outcome: {outcome.get('disposal_type')} - {outcome.get('sentence_or_relief')}"
            evidence_lines.append(f"{source_header}\n{source_content}\n")

        evidence_text = "\n".join(evidence_lines) if evidence_lines else "NO RETRIEVED EVIDENCE AVAILABLE."

        prompt = f"""FACT PATTERN REPORTED BY USER:
"{intake_result.clarified_facts}"

IDENTIFIED POSSIBLE ISSUES:
{json.dumps([i.model_dump() for i in reasoning_result.possible_issues], indent=2)}

AVAILABLE RETRIEVED EVIDENCE CHUNKS (ONLY USE INFORMATION FROM HERE):
{evidence_text}

VALID CITATION IDS: {valid_source_ids}

Draft a structured legal information response in JSON format adhering strictly to this schema:
{{
  "plain_summary": "Plain-language, empathetic summary explaining what happened in simple terms.",
  "legal_issue_explanations": [
    "Explanation of each possible legal issue in simple language, citing the specific source chunk e.g. [stat:IT-66D]."
  ],
  "relevant_laws_identified": [
    "Specific statutes and sections identified in the evidence with citation e.g. Section 66D IT Act [stat:IT-66D]"
  ],
  "possible_next_steps": [
    "Practical procedural options (e.g. reporting to 1930 / cybercrime.gov.in, notifying bank ombudsman, seeking an advocate)"
  ],
  "documents_or_information": [
    "Concrete documents and digital evidence to preserve (transaction logs, call records, messages)"
  ],
  "similar_cases_mentioned": [
    {{
      "case_id": "e.g. DC-HP-2024-000123",
      "court_and_year": "Court name and year",
      "fact_comparison": "How facts compare",
      "recorded_outcome": "Outcome recorded in evidence",
      "disclaimer": "Note: Past court outcomes reflect specific evidentiary records and do not guarantee identical results."
    }}
  ],
  "cited_source_ids": ["List of all source IDs cited in your draft, e.g. stat:IT-66D, case:DC-HP-2024-000123"],
  "raw_answer_text": "A complete, beautifully formatted cohesive text response incorporating all sections, inline citations, and the mandatory legal disclaimer."
}}
"""

        raw_output = self.llm.generate(
            prompt=prompt,
            system_prompt=ANSWER_GENERATOR_PROMPT,
            temperature=0.1,
            json_mode=True,
        )

        try:
            cleaned = self._clean_json(raw_output)
            data = json.loads(cleaned)

            cited_ids = data.get("cited_source_ids", [])
            # Also scan raw text for citation tags e.g. [stat:...] or [case:...]
            plain_summary = data.get("plain_summary", "")
            legal_issues = data.get("legal_issue_explanations", [])
            relevant_laws = data.get("relevant_laws_identified", [])
            possible_steps = data.get("possible_next_steps", [])
            documents = data.get("documents_or_information", [])

            # Fallback to candidate statutes if laws list is empty
            if not relevant_laws:
                relevant_laws = [
                    f"{c.source.citation}: {c.source.title} [{c.source.source_id}]"
                    for c in reranked_candidates if c.source.source_type == "statute"
                ]

            # Map available sources
            case_sources = {c.source.source_id: c.source for c in reranked_candidates if c.source.source_type == "case"}
            stat_sources = [c.source for c in reranked_candidates if c.source.source_type == "statute"]
            valid_source_id_set = {c.source.source_id for c in reranked_candidates}
            valid_case_list = list(case_sources.values())

            # Enrich and sanitize existing similar_cases
            raw_similar_cases = data.get("similar_cases_mentioned", [])
            sanitized_similar_cases = []
            for idx, sc in enumerate(raw_similar_cases):
                cid = sc.get("case_id", "")
                clean_cid = cid if cid.startswith("case:") else f"case:{cid}"
                matched_src = case_sources.get(cid) or case_sources.get(clean_cid)

                # If LLM cited a case ID not in retrieved candidates, remap to an actual candidate
                if not matched_src and valid_case_list:
                    matched_src = valid_case_list[idx % len(valid_case_list)]

                if matched_src:
                    sc["case_id"] = matched_src.source_id
                    sc["title"] = matched_src.title or matched_src.metadata.get("case_id", matched_src.source_id)
                    sc["url"] = matched_src.metadata.get("url")
                    sanitized_similar_cases.append(sc)
                elif "IK-" in cid or cid.startswith("IK-"):
                    tid = re.sub(r"[^\d]", "", cid)
                    if tid:
                        sc["case_id"] = f"case:IK-{tid}"
                        sc["title"] = sc.get("title") or f"Indian Kanoon Precedent #{tid}"
                        sc["url"] = f"https://indiankanoon.org/doc/{tid}/"
                        sanitized_similar_cases.append(sc)

            similar_cases = sanitized_similar_cases

            # If LLM returned empty similar_cases, populate directly from top retrieved case candidates
            if not similar_cases and valid_case_list:
                for src in valid_case_list[:3]:
                    case_title = src.title or src.metadata.get("case_id", src.source_id)
                    case_url = src.metadata.get("url")
                    court_str = src.metadata.get("court_name", "Indian Court Precedent")
                    year_str = f" ({src.metadata.get('year')})" if src.metadata.get("year") else ""
                    similar_cases.append({
                        "case_id": src.source_id,
                        "title": case_title,
                        "url": case_url,
                        "court_and_year": f"{court_str}{year_str}",
                        "fact_comparison": src.text[:180] + ("..." if len(src.text) > 180 else ""),
                        "recorded_outcome": str(src.metadata.get("outcome", {}).get("sentence_or_relief", "See full judgment on Indian Kanoon") if isinstance(src.metadata.get("outcome"), dict) else src.metadata.get("outcome", "Precedent on record")),
                        "disclaimer": "Past outcomes depend on specific evidentiary records and do not guarantee identical results.",
                    })

            # ALWAYS assemble rich markdown answer if raw_text is missing, too short, or lacks sections
            raw_text = data.get("raw_answer_text", "").strip()
            if not raw_text or len(raw_text) < 150 or "###" not in raw_text:
                raw_text = self._assemble_markdown_answer(
                    plain_summary=plain_summary or intake_result.clarified_facts,
                    legal_issues=legal_issues,
                    relevant_laws=relevant_laws,
                    possible_steps=possible_steps,
                    documents=documents,
                    similar_cases=similar_cases,
                )
            else:
                # Sanitize any hallucinated inline citations in raw_text
                def _replace_invalid_tag(match):
                    tag = match.group(1)
                    if tag in valid_source_id_set:
                        return f"[{tag}]"
                    if tag.startswith("case:") and valid_case_list:
                        return f"[{valid_case_list[0].source_id}]"
                    if tag.startswith("stat:") and stat_sources:
                        return f"[{stat_sources[0].source_id}]"
                    return ""

                raw_text = re.sub(r"\[(stat:[^\]]+|case:[^\]]+|doc-[^\]]+)\]", _replace_invalid_tag, raw_text)
                if LEGAL_DISCLAIMER not in raw_text:
                    raw_text += f"\n\n{LEGAL_DISCLAIMER}"

            # Aggregate all citation tags found in the generated text
            found_tags = re.findall(r"\[(stat:[^\]]+|case:[^\]]+|doc-[^\]]+)\]", raw_text)
            all_cited = list(set(cited_ids + found_tags))

            return GeneratedAnswer(
                plain_summary=plain_summary or intake_result.clarified_facts,
                legal_issue_explanations=legal_issues,
                relevant_laws_identified=relevant_laws,
                possible_next_steps=possible_steps,
                documents_or_information=documents,
                similar_cases_mentioned=similar_cases,
                raw_answer_text=raw_text,
                cited_source_ids=all_cited,
            )

        except Exception as e:
            logger.warning(f"Could not parse Answer Generator output ({e}). Generating grounded deterministic draft.")
            return self._grounded_fallback(intake_result, reasoning_result, reranked_candidates)

    def _clean_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def _assemble_markdown_answer(
        self,
        plain_summary: str,
        legal_issues: List[str],
        relevant_laws: List[str],
        possible_steps: List[str],
        documents: List[str],
        similar_cases: List[Dict[str, Any]],
    ) -> str:
        """Assembles a beautiful, comprehensive markdown response from verified structured sections."""
        parts = []
        if plain_summary:
            parts.append(f"### Overview\n{plain_summary}\n")

        if legal_issues:
            parts.append("### Key Legal Issues & Implications\n" + "\n".join(f"- {i}" for i in legal_issues) + "\n")

        if relevant_laws:
            parts.append("### Relevant Legal Provisions\n" + "\n".join(f"- {l}" for l in relevant_laws) + "\n")

        if possible_steps:
            parts.append("### Recommended Next Steps\n" + "\n".join(f"- {s}" for s in possible_steps) + "\n")

        if documents:
            parts.append("### Key Documents & Evidence to Preserve\n" + "\n".join(f"- {d}" for d in documents) + "\n")

        if similar_cases:
            parts.append("### Similar Precedents & Judgments (For Information Only)\n")
            for c in similar_cases:
                title = c.get("title") or c.get("case_id", "Precedent")
                court = c.get("court_and_year", "Court Precedent")
                url = c.get("url")
                link_line = f"\n  *Indian Kanoon Link*: [{title}]({url})" if url else ""
                summary = c.get("fact_comparison", "Factual similarity identified in repository records.")
                outcome = c.get("recorded_outcome", "Disposed according to law.")
                disclaimer = c.get("disclaimer", "Past court outcomes reflect specific evidentiary records and do not guarantee identical results.")
                parts.append(
                    f"- **{title}** [{c.get('case_id', '')}]: {court}{link_line}\n"
                    f"  *Facts / Summary*: {summary}\n"
                    f"  *Outcome / Relief*: {outcome}\n"
                    f"  *{disclaimer}*"
                )
            parts.append("\n")

        parts.append(f"---\n{LEGAL_DISCLAIMER}")
        return "\n".join(parts)

    def _grounded_fallback(
        self,
        intake_result: IntakeResult,
        reasoning_result: LegalReasoningResult,
        candidates: List[RerankedCandidate],
    ) -> GeneratedAnswer:
        """Deterministic grounded fallback constructed strictly from retrieved candidates."""
        laws = []
        similar_cases = []
        cited_ids = []

        for cand in candidates:
            src = cand.source
            cited_ids.append(src.source_id)
            if src.source_type == "statute":
                laws.append(f"{src.citation}: {src.title} [{src.source_id}]")
            elif src.source_type == "case":
                case_title = src.title or src.metadata.get("case_id", src.source_id)
                case_url = src.metadata.get("url")
                year_str = f" ({src.metadata.get('year')})" if src.metadata.get("year") else ""
                court_str = src.metadata.get("court_name", "Indian Court Precedent")
                similar_cases.append({
                    "case_id": src.metadata.get("case_id", src.source_id),
                    "title": case_title,
                    "url": case_url,
                    "court_and_year": f"{court_str}{year_str}",
                    "fact_comparison": src.text[:180] + ("..." if len(src.text) > 180 else ""),
                    "recorded_outcome": str(src.metadata.get("outcome", {}).get("sentence_or_relief", "See full judgment on Indian Kanoon") if isinstance(src.metadata.get("outcome"), dict) else src.metadata.get("outcome", "")),
                    "disclaimer": "Past outcomes depend on specific evidentiary records and do not guarantee identical results.",
                })

        plain_summary = (
            f"Based on your statement: '{intake_result.clarified_facts}', "
            "this matter appears to involve actions that may have legal implications under Indian criminal law."
        )

        category = intake_result.detected_category

        default_steps = [
            "Document all relevant events, timelines, dates, and communications in writing.",
            "Gather and preserve all primary records, agreements, receipts, and correspondence.",
            "Approach the local police station or appropriate grievance forum if an offence is suspected.",
            "Consult a qualified advocate to review the legal merits and determine appropriate procedural steps."
        ]

        default_docs = [
            "Written summary and timeline of the dispute or incident",
            "Copies of relevant identification and proof of residence",
            "Any correspondence, notices, agreements, or receipts related to the matter",
            "Copies of any complaints or official acknowledgments already filed"
        ]

        steps_by_category = {
            "criminal": [
                "Report the incident immediately to the nearest police station to lodge an FIR.",
                "Request police inspection of the scene and preservation of any available CCTV footage or physical evidence.",
                "Provide details such as vehicle registration/engine number or serial numbers of stolen articles to investigating officers.",
                "Consult an advocate regarding bail opposition, property release (superdari), or tracking the investigation."
            ],
            "civil": [
                "Issue a formal legal notice through an advocate calling upon the opposing party to rectify the breach or refund the amount.",
                "Preserve all original agreements, communications, and payment receipts.",
                "Attempt mediation or negotiation if an arbitration or dispute resolution clause exists.",
                "Consult a civil advocate to file a recovery suit or seek an injunction."
            ],
            "family_matrimonial": [
                "Consider mediation or counseling through Family Court mediation centers or authorized legal services authorities.",
                "If seeking mutual consent divorce, discuss and formulate mutually agreed terms regarding permanent alimony, stridhan, and child custody.",
                "File appropriate petitions before the Family Court or District Court under personal marriage laws or maintenance under Section 125 CrPC.",
                "Consult a matrimonial lawyer to draft settlement agreements, petition documentation, and advise on legal rights."
            ],
            "property_land": [
                "Gather all title deeds, registration documents, and previous ownership records.",
                "Obtain the latest encumbrance certificate and revenue records (Khata/Pahani) for the property.",
                "Issue a legal notice to the encroacher or opposing party to vacate or cease interference.",
                "Consult a property lawyer to file a suit for injunction or declaration of title."
            ],
            "consumer": [
                "Send a formal written complaint or legal notice to the seller/service provider seeking replacement or refund.",
                "Keep all invoices, warranty cards, and records of communication with customer care.",
                "File a complaint on the National Consumer Helpline (NCH) or via e-Daakhil portal.",
                "Approach the District Consumer Disputes Redressal Commission if the grievance is not resolved."
            ],
            "cheque_bounce": [
                "Send a formal legal notice under Section 138 of the Negotiable Instruments Act within 30 days of receiving the return memo.",
                "Preserve the original bounced cheque and the bank return memo.",
                "If no payment is received within 15 days of notice delivery, file a criminal complaint before the Magistrate within the next 30 days.",
                "Consult a legal professional to ensure all statutory timelines are strictly met."
            ],
            "labour_employment": [
                "Review your employment contract, HR policies, and any termination letters.",
                "Send a formal grievance email or legal notice to the employer demanding unpaid dues or addressing harassment.",
                "Approach the labor commissioner or labor court for conciliation under the Industrial Disputes Act.",
                "Consult an employment lawyer to understand your rights regarding gratuity, PF, and wrongful termination."
            ],
            "cybercrime": [
                "Report immediately to the National Cyber Crime Helpline (1930) or cybercrime.gov.in if online fraud occurred.",
                "Contact your banking institution to request immediate freezing of beneficiary accounts.",
                "Preserve all transaction IDs, SMS alerts, call history, and message screenshots.",
                "Consult a qualified advocate to review your case and represent your interests before law enforcement or court."
            ],
            "motor_accident": [
                "Seek immediate medical attention and retain all medical bills and the Medico-Legal Certificate (MLC).",
                "Ensure an FIR is registered at the local police station.",
                "Inform your insurance company immediately to initiate a claim.",
                "File a petition before the Motor Accident Claims Tribunal (MACT) for compensation."
            ],
            "constitutional_administrative": [
                "Obtain a certified copy of the government order or administrative decision in question.",
                "Submit a formal representation or appeal to the higher administrative authority.",
                "Consult an advocate to file a Writ Petition (under Article 226 or 32) before the High Court or Supreme Court if fundamental rights are violated.",
                "Preserve all correspondence and proof of the rights violation."
            ],
        }

        docs_by_category = {
            "criminal": [
                "Copy of FIR or police acknowledgment receipt",
                "Medical records if physical injuries were sustained",
                "CCTV camera recordings or names of witnesses present at the scene",
                "Any correspondence or threats received from the accused"
            ],
            "civil": [
                "Original or copies of disputed agreements, contracts, or deeds",
                "Bank statements, payment vouchers, RTGS/NEFT receipts",
                "Copy of legal notices exchanged and postal delivery receipts",
                "Emails, WhatsApp messages, or other written correspondence"
            ],
            "family_matrimonial": [
                "Marriage certificate and proof of joint residence / separation date",
                "Income tax returns, salary slips, and bank statements of both parties",
                "Children's birth certificates and school records if custody is involved",
                "Communications or recordings reflecting the nature of the dispute"
            ],
            "property_land": [
                "Original Sale Deed, Title Deed, or Gift Deed",
                "Encumbrance Certificate and recent tax paid receipts",
                "Approved building plans or survey sketches",
                "Photos of the property and boundaries"
            ],
            "consumer": [
                "Original invoice, bill, or cash memo",
                "Warranty or guarantee card",
                "Proof of payment (credit card statement, UPI receipt)",
                "Emails or chat logs with customer support"
            ],
            "cheque_bounce": [
                "Original dishonoured cheque",
                "Bank return memo indicating reason for bounce",
                "Copy of the legal notice sent to the drawer and postal receipt",
                "Invoices or agreements proving the debt or liability"
            ],
            "labour_employment": [
                "Appointment letter, employment contract, or offer letter",
                "Recent salary slips and bank statements",
                "Termination letter or resignation acceptance",
                "Emails or communications with HR or management"
            ],
            "cybercrime": [
                "Bank account statements showing debit entries and transaction IDs",
                "Call records, phone numbers, and time logs of the interaction",
                "Screenshots of UPI confirmations or chat history",
                "Copy of any police complaint or cyber acknowledgment receipt"
            ],
            "motor_accident": [
                "Copy of the FIR and police panchnama",
                "Medico-Legal Certificate (MLC) and all medical bills",
                "Driving license and vehicle registration (RC)",
                "Insurance policy document and claim forms"
            ],
            "constitutional_administrative": [
                "Certified copy of the impugned government order or notification",
                "Proof of identity and locus standi (right to sue)",
                "Previous representations made to the department",
                "Any prior show-cause notices or responses"
            ],
        }

        steps = steps_by_category.get(category, default_steps)
        docs = docs_by_category.get(category, default_docs)

        text_parts = [
            f"### Overview\n{plain_summary}\n",
            "### Potentially Relevant Legal Provisions\n" + "\n".join(f"- {law}" for law in laws) if laws else "No specific statutory chunks were matched in the corpus.",
            "\n### Possible Next Steps\n" + "\n".join(f"- {s}" for s in steps),
            "\n### Key Documents to Preserve\n" + "\n".join(f"- {d}" for d in docs),
        ]

        if similar_cases:
            text_parts.append("\n### Similar Precedents & Judgments (For Information Only)\n")
            for c in similar_cases:
                title = c.get("title") or c.get("case_id", "Precedent")
                url_str = f"\n  *Reference*: [{title}]({c['url']})" if c.get("url") else ""
                text_parts.append(
                    f"- **{title}** [{c['case_id']}]: {c['court_and_year']}{url_str}\n"
                    f"  *Facts / Summary*: {c['fact_comparison']}\n"
                    f"  *Outcome / Relief*: {c['recorded_outcome']}\n"
                    f"  *{c['disclaimer']}*"
                )

        text_parts.append(f"\n\n---\n{LEGAL_DISCLAIMER}")
        raw_text = "\n".join(text_parts)

        return GeneratedAnswer(
            plain_summary=plain_summary,
            legal_issue_explanations=[i.description for i in reasoning_result.possible_issues],
            relevant_laws_identified=laws,
            possible_next_steps=steps,
            documents_or_information=docs,
            similar_cases_mentioned=similar_cases,
            raw_answer_text=raw_text,
            cited_source_ids=cited_ids,
        )
