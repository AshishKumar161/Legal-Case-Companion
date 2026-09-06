"""Bundle PDF Compilation Engine.

Generates court-ready PDF bundles, Bates-numbered pages, exhibit indexes,
and statutory certificates under Section 63 BSA 2023 without third-party C libraries.
"""

import io
from datetime import datetime
from typing import Any

import pypdf


def _escape_pdf_text(text: str) -> str:
    """Escapes parenthesis and backslashes for PDF string literals."""
    if not text:
        return ""
    # Strip or replace unprintable characters, keep ASCII/latin-1
    cleaned = text.encode("latin-1", "replace").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _create_single_page_pdf(
    commands: list[str],
    width: float = 595.0,
    height: float = 842.0,
) -> pypdf.PageObject:
    """Creates a standalone A4 PDF page from raw PDF text stream commands."""
    stream_content = "\n".join(commands)
    stream_bytes = stream_content.encode("latin-1")

    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
        + f"{width:.1f} {height:.1f}".encode("ascii")
        + b"] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj\n"
    )
    obj4 = (
        b"4 0 obj\n<< /Length "
        + str(len(stream_bytes)).encode("ascii")
        + b" >>\nstream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj6 = b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n"

    pos1 = len(header)
    pos2 = pos1 + len(obj1)
    pos3 = pos2 + len(obj2)
    pos4 = pos3 + len(obj3)
    pos5 = pos4 + len(obj4)
    pos6 = pos5 + len(obj5)
    xref_pos = pos6 + len(obj6)

    xref = (
        f"xref\n0 7\n0000000000 65535 f \n"
        f"{pos1:010d} 00000 n \n"
        f"{pos2:010d} 00000 n \n"
        f"{pos3:010d} 00000 n \n"
        f"{pos4:010d} 00000 n \n"
        f"{pos5:010d} 00000 n \n"
        f"{pos6:010d} 00000 n \n"
    ).encode("ascii")

    trailer = f"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")

    pdf_text = header + obj1 + obj2 + obj3 + obj4 + obj5 + obj6 + xref + trailer
    reader = pypdf.PdfReader(io.BytesIO(pdf_text))
    return reader.pages[0]


class BundlePdfEngine:
    """Pure-python PDF compiler for court evidentiary bundles."""

    @staticmethod
    def create_cover_page(
        bundle_title: str,
        case_title: str,
        case_id: str,
        court_name: str | None,
        hearing_info: str | None,
        bates_range: str,
        total_items: int,
        finalized_at: datetime,
    ) -> pypdf.PageObject:
        """Renders the official cover page for the court bundle."""
        safe_title = _escape_pdf_text(bundle_title.upper())
        safe_case = _escape_pdf_text(case_title)
        safe_court = _escape_pdf_text(court_name or "Official Court of Record")
        safe_hearing = _escape_pdf_text(hearing_info or "General Matter Record")
        date_str = finalized_at.strftime("%d %B %Y, %H:%M:%S UTC")

        cmds = [
            # Top Banner Border
            "0.2 w 50 800 m 545 800 l S",
            "0.2 w 50 796 m 545 796 l S",
            # Header
            "BT /F2 10 Tf 50 780 Td (IN THE COURT OF:) Tj ET",
            f"BT /F2 13 Tf 50 762 Td ({safe_court}) Tj ET",
            "0.5 w 50 745 m 545 745 l S",
            # Matter Details
            "BT /F2 10 Tf 50 720 Td (MATTER / CASE TITLE:) Tj ET",
            f"BT /F1 12 Tf 50 702 Td ({safe_case}) Tj ET",
            f"BT /F1 9 Tf 50 686 Td (Matter ID: {_escape_pdf_text(case_id)}) Tj ET",
            # Main Title Box
            "0.8 w 50 560 495 100 re S",
            "BT /F2 18 Tf 70 625 Td (COURT EVIDENTIARY BUNDLE) Tj ET",
            f"BT /F2 12 Tf 70 595 Td ({safe_title}) Tj ET",
            # Hearing & Preparation Info
            "BT /F2 10 Tf 50 520 Td (SCHEDULED COURT PROCEEDING:) Tj ET",
            f"BT /F1 11 Tf 50 502 Td ({safe_hearing}) Tj ET",
            # Bundle Metadata Box
            "0.5 w 50 370 495 100 re S",
            "BT /F2 10 Tf 70 445 Td (BATES NUMBERING RANGE:) Tj ET",
            f"BT /F2 14 Tf 70 425 Td ({_escape_pdf_text(bates_range)}) Tj ET",
            f"BT /F1 10 Tf 70 400 Td (Total Included Exhibits/Evidence: {total_items}) Tj ET",
            f"BT /F1 9 Tf 70 382 Td (Compiled At: {date_str}) Tj ET",
            # Legal Preservation Statement
            "0.5 w 50 200 495 130 re S",
            "BT /F2 9 Tf 70 305 Td (AUTHORITATIVE RECORD & INTEGRITY VERIFICATION NOTICE) Tj ET",
            "BT /F1 8.5 Tf 70 285 Td (This evidentiary bundle contains version-pinned digital assets from the LCC Evidence Locker.) Tj ET",
            "BT /F1 8.5 Tf 70 270 Td (Every included document is cryptographically verified via SHA-256 digest at ingestion.) Tj ET",
            "BT /F1 8.5 Tf 70 255 Td (Original authoritative objects remain unchanged in private secure storage.) Tj ET",
            "BT /F1 8.5 Tf 70 240 Td (Subject to Section 63 of the Bharatiya Sakshya Adhiniyam, 2023.) Tj ET",
            "BT /F2 8 Tf 70 215 Td (LEGAL CASE COMPANION -- SECURE EVIDENTIARY REPOSITORY) Tj ET",
            # Footer Line
            "0.5 w 50 50 m 545 50 l S",
            "BT /F1 8 Tf 50 38 Td (CONFIDENTIAL COURT FILING -- AUTHORIZED RECIPIENTS ONLY) Tj ET",
        ]
        return _create_single_page_pdf(cmds)

    @staticmethod
    def create_index_page(
        bundle_title: str,
        items: list[dict[str, Any]],
    ) -> pypdf.PageObject:
        """Renders an exhibit table of contents / index page."""
        safe_title = _escape_pdf_text(bundle_title)
        cmds = [
            "BT /F2 15 Tf 50 790 Td (EXHIBIT INDEX & TABLE OF CONTENTS) Tj ET",
            f"BT /F1 10 Tf 50 772 Td (Bundle: {safe_title}) Tj ET",
            "0.8 w 50 760 m 545 760 l S",
            # Table Header
            "BT /F2 9 Tf 50 745 Td (EXHIBIT) Tj ET",
            "BT /F2 9 Tf 120 745 Td (DOCUMENT TITLE) Tj ET",
            "BT /F2 9 Tf 360 745 Td (BATES RANGE) Tj ET",
            "BT /F2 9 Tf 460 745 Td (INTEGRITY HASH) Tj ET",
            "0.4 w 50 737 m 545 737 l S",
        ]

        y = 720
        for item in items[:18]:  # Bounded entries per index page
            exhibit_label = _escape_pdf_text(item.get("exhibit_number") or "---")
            title = _escape_pdf_text(item.get("title") or item.get("filename") or "Evidence Item")
            if len(title) > 36:
                title = title[:33] + "..."
            bates_label = _escape_pdf_text(
                f"{item.get('bates_start', '')} - {item.get('bates_end', '')}"
            )
            hash_snip = _escape_pdf_text((item.get("sha256") or "")[:12] + "...")

            cmds.extend([
                f"BT /F2 9 Tf 50 {y} Td ({exhibit_label}) Tj ET",
                f"BT /F1 9 Tf 120 {y} Td ({title}) Tj ET",
                f"BT /F1 9 Tf 360 {y} Td ({bates_label}) Tj ET",
                f"BT /F1 8 Tf 460 {y} Td ({hash_snip}) Tj ET",
                f"0.1 w 50 {y - 4} m 545 {y - 4} l S",
            ])
            y -= 22

        cmds.extend([
            "0.5 w 50 60 m 545 60 l S",
            "BT /F1 8 Tf 50 48 Td (Detailed SHA-256 hash manifest follows each exhibit.) Tj ET",
        ])
        return _create_single_page_pdf(cmds)

    @staticmethod
    def create_placeholder_page(
        exhibit_number: str | None,
        title: str,
        original_filename: str,
        mime_type: str,
        sha256_hash: str,
        bates_label: str,
    ) -> pypdf.PageObject:
        """Renders an official divider/placeholder for non-PDF digital evidence (audio, video, etc.)."""
        exhibit_tag = _escape_pdf_text(exhibit_number or "EVIDENCE ITEM")
        safe_title = _escape_pdf_text(title)
        safe_file = _escape_pdf_text(original_filename)
        safe_mime = _escape_pdf_text(mime_type)
        safe_bates = _escape_pdf_text(bates_label)

        cmds = [
            # Top Banner
            "0.5 w 50 790 m 545 790 l S",
            f"BT /F2 16 Tf 50 750 Td ({exhibit_tag}) Tj ET",
            f"BT /F1 12 Tf 50 730 Td ({safe_title}) Tj ET",
            "0.5 w 50 715 m 545 715 l S",
            # Notice Box
            "0.8 w 50 520 495 160 re S",
            "BT /F2 11 Tf 70 650 Td (MEDIA / NON-DOCUMENTARY EXHIBIT RECORD) Tj ET",
            f"BT /F1 10 Tf 70 625 Td (Original Filename: {safe_file}) Tj ET",
            f"BT /F1 10 Tf 70 605 Td (File MIME Format: {safe_mime}) Tj ET",
            "BT /F1 10 Tf 70 585 Td (Cryptographic SHA-256 Digest:) Tj ET",
            f"BT /F2 9 Tf 70 568 Td ({sha256_hash}) Tj ET",
            "BT /F1 9 Tf 70 540 Td (Notice: This exhibit is a native binary/media object.) Tj ET",
            "BT /F1 9 Tf 70 528 Td (The authoritative file is preserved in private cloud storage.) Tj ET",
            # Bates Number Stamp
            f"BT /F2 10 Tf 430 35 Td ({safe_bates}) Tj ET",
            "0.5 w 50 50 m 545 50 l S",
        ]
        return _create_single_page_pdf(cmds)

    @staticmethod
    def create_manifest_summary_page(
        bundle_title: str,
        bundle_hash: str,
        items: list[dict[str, Any]],
    ) -> pypdf.PageObject:
        """Renders the comprehensive SHA-256 manifest summary page."""
        safe_title = _escape_pdf_text(bundle_title)
        cmds = [
            "BT /F2 14 Tf 50 790 Td (CRYPTOGRAPHIC HASH MANIFEST) Tj ET",
            f"BT /F1 10 Tf 50 772 Td (Bundle: {safe_title}) Tj ET",
            "0.8 w 50 760 m 545 760 l S",
            "BT /F2 9 Tf 50 745 Td (OVERALL BUNDLE SHA-256 DIGEST:) Tj ET",
            f"BT /F2 9.5 Tf 50 730 Td ({bundle_hash}) Tj ET",
            "0.4 w 50 715 m 545 715 l S",
            "BT /F2 9 Tf 50 698 Td (EXHIBIT) Tj ET",
            "BT /F2 9 Tf 130 698 Td (FILENAME / TITLE) Tj ET",
            "BT /F2 9 Tf 290 698 Td (SHA-256 DIGEST) Tj ET",
            "0.2 w 50 690 m 545 690 l S",
        ]

        y = 672
        for item in items[:15]:
            exhibit = _escape_pdf_text(item.get("exhibit_number") or "---")
            title = _escape_pdf_text(item.get("filename") or "evidence")[:22]
            sha = _escape_pdf_text(item.get("sha256") or "")
            cmds.extend([
                f"BT /F2 8.5 Tf 50 {y} Td ({exhibit}) Tj ET",
                f"BT /F1 8.5 Tf 130 {y} Td ({title}) Tj ET",
                f"BT /F1 7.5 Tf 290 {y} Td ({sha}) Tj ET",
            ])
            y -= 20

        cmds.extend([
            "0.5 w 50 50 m 545 50 l S",
            "BT /F1 8 Tf 50 38 Td (All digests calculated via standard SHA-256 algorithm at ingestion.) Tj ET",
        ])
        return _create_single_page_pdf(cmds)

    @staticmethod
    def create_bates_stamp_overlay(
        bates_label: str,
        bundle_header: str | None = None,
        width: float = 595.0,
        height: float = 842.0,
    ) -> pypdf.PageObject:
        """Creates a transparent single-page overlay containing Bates stamp and header."""
        safe_label = _escape_pdf_text(bates_label)
        cmds = []
        if bundle_header:
            safe_hdr = _escape_pdf_text(bundle_header)
            cmds.append(f"BT /F1 8 Tf 50 {height - 25:.1f} Td ({safe_hdr}) Tj ET")
            cmds.append(f"0.1 w 50 {height - 30:.1f} m {width - 50:.1f} {height - 30:.1f} l S")

        # Bottom right Bates stamp
        cmds.append(f"BT /F2 9.5 Tf {width - 140:.1f} 25 Td ({safe_label}) Tj ET")
        cmds.append(f"0.2 w {width - 145:.1f} 20 m {width - 50:.1f} 20 l S")

        return _create_single_page_pdf(cmds, width=width, height=height)

    @staticmethod
    def create_bsa_certificate_pdf(
        cert_data: dict[str, Any],
    ) -> bytes:
        """Compiles a complete statutory Section 63 BSA 2023 draft certificate PDF."""
        rec_id = _escape_pdf_text(cert_data.get("record_identification") or "")
        dev_type = _escape_pdf_text(cert_data.get("source_device_type") or "Cloud Digital Storage")
        dev_details = _escape_pdf_text(cert_data.get("source_device_details") or "Standard Cloud Infrastructure")
        lawful = _escape_pdf_text(cert_data.get("lawful_control_statement") or "")
        operational = _escape_pdf_text(cert_data.get("operational_condition_statement") or "")
        name = _escape_pdf_text(cert_data.get("declarant_name") or "")
        designation = _escape_pdf_text(cert_data.get("declarant_designation") or "")
        org = _escape_pdf_text(cert_data.get("declarant_organization") or "")
        place = _escape_pdf_text(cert_data.get("place") or "")
        decl_date = cert_data.get("declaration_date")
        date_str = decl_date.strftime("%d %B %Y") if isinstance(decl_date, datetime) else str(decl_date)
        sha_hash = cert_data.get("hash_value") or ""

        cmds = [
            # Top Banner
            "0.5 w 50 800 m 545 800 l S",
            "BT /F2 13 Tf 50 778 Td (CERTIFICATE UNDER SECTION 63(4)) Tj ET",
            "BT /F2 13 Tf 50 762 Td (BHARATIYA SAKSHYA ADHINIYAM, 2023) Tj ET",
            "0.5 w 50 750 m 545 750 l S",
            # Warning Banner
            "0.8 w 50 685 495 50 re S",
            "BT /F2 9.5 Tf 70 718 Td (PREPARED DRAFT FORM -- REQUIRES STATUTORY DECLARANT CONFIRMATION) Tj ET",
            "BT /F1 8.5 Tf 70 700 Td (This certificate draft organizes technical metadata. Judicial admissibility is not guaranteed.) Tj ET",
            # Section 1: Identification
            "BT /F2 10 Tf 50 660 Td (PART A: IDENTIFICATION OF ELECTRONIC RECORD) Tj ET",
            "0.2 w 50 652 m 545 652 l S",
            f"BT /F1 9 Tf 50 635 Td (Record Description: {rec_id[:80]}) Tj ET",
            f"BT /F1 8.5 Tf 50 618 Td (Cryptographic SHA-256 Digest: {sha_hash}) Tj ET",
            # Section 2: Device Information
            "BT /F2 10 Tf 50 585 Td (PART B: PARTICULARS OF DEVICE / STORAGE MEDIUM) Tj ET",
            "0.2 w 50 577 m 545 577 l S",
            f"BT /F1 9 Tf 50 560 Td (Source Device Category: {dev_type}) Tj ET",
            f"BT /F1 9 Tf 50 542 Td (Device / System Particulars: {dev_details[:80]}) Tj ET",
            # Section 3: Lawful Control
            "BT /F2 10 Tf 50 508 Td (PART C: LAWFUL CONTROL & OPERATIONAL INTEGRITY) Tj ET",
            "0.2 w 50 500 m 545 500 l S",
            "BT /F1 8.5 Tf 50 482 Td (1. Statement of Lawful Control:) Tj ET",
            f"BT /F1 8 Tf 60 466 Td ({lawful[:95]}) Tj ET",
            "BT /F1 8.5 Tf 50 440 Td (2. Statement of Normal Operation:) Tj ET",
            f"BT /F1 8 Tf 60 424 Td ({operational[:95]}) Tj ET",
            # Section 4: Declarant Attestation
            "BT /F2 10 Tf 50 380 Td (PART D: DECLARANT DETAILS & ATTESTATION) Tj ET",
            "0.2 w 50 372 m 545 372 l S",
            f"BT /F1 9 Tf 50 350 Td (Name: {name}) Tj ET",
            f"BT /F1 9 Tf 50 332 Td (Designation: {designation}) Tj ET",
            f"BT /F1 9 Tf 50 314 Td (Organization: {org or 'N/A'}) Tj ET",
            f"BT /F1 9 Tf 50 296 Td (Place: {place}) Tj ET",
            f"BT /F1 9 Tf 50 278 Td (Date of Declaration: {date_str}) Tj ET",
            # Signature Box
            "0.5 w 350 180 195 70 re S",
            "BT /F2 8.5 Tf 360 235 Td (Signature / Digital Attestation) Tj ET",
            "BT /F1 7.5 Tf 360 195 Td (Confirmed by authorized declarant) Tj ET",
            # Statutory Disclaimer Footer
            "0.5 w 50 60 m 545 60 l S",
            "BT /F1 7.5 Tf 50 48 Td (Prepared pursuant to Section 63(4) Schedule format of BSA, 2023. Not a judicial guarantee.) Tj ET",
        ]

        page = _create_single_page_pdf(cmds)
        writer = pypdf.PdfWriter()
        writer.add_page(page)

        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
