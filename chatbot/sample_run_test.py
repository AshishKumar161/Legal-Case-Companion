"""
Sample Run Test Script for LCC Legal AI Backend
================================================
This script provides an interactive and automated test run of the LegalAssistant pipeline.
You can run it as-is to test the pipeline against built-in benchmark scenarios,
or pass your own custom query as a command-line argument.

Usage:
    # 1. Run standard test scenarios (Cyber fraud, Emergency, Out-of-Domain):
    python chatbot/sample_run_test.py

    # 2. Run with your own custom test query:
    python chatbot/sample_run_test.py "My motorcycle parked outside my house was stolen overnight."

    # 3. From within the chatbot directory:
    cd chatbot
    python sample_run_test.py
"""

import sys
import os
import json

# Ensure Windows terminal encoding compatibility
if sys.platform == "win32":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project and model_backend directories are discoverable in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
for p in [current_dir, parent_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from model_backend.pipeline import LegalAssistant, PipelineConfig
from model_backend.schemas import LegalAssistantResponse


def format_separator(title: str = "", char: str = "=", width: int = 70) -> str:
    if not title:
        return char * width
    prefix = f" {title} "
    return prefix.center(width, char)


def display_response(scenario_name: str, query: str, response: LegalAssistantResponse) -> None:
    print("\n" + format_separator(scenario_name, "="))
    print(f"QUERY: \"{query}\"\n")
    print(f"[*] Confidence Score:        {response.confidence:.2f} / 1.00")
    print(f"[*] Verified by Critic:      {'YES (Grounding confirmed)' if response.verified else 'NO / UNVERIFIED'}")
    print(f"[*] Escalated to Advocate:   {'YES (Escalation Triggered)' if response.escalated else 'NO (Safe to present)'}")
    print(f"[*] Professional Help:       {'Recommended' if response.needs_professional_help else 'Standard Information'}")

    if response.legal_issue:
        print("\n[Identified Legal Issues]")
        for issue in response.legal_issue:
            print(f"  - {issue}")

    if response.relevant_law:
        print("\n[Potentially Relevant Laws / Statutes]")
        for law in response.relevant_law:
            print(f"  - {law}")

    if response.similar_cases:
        print("\n[Similar District Court Precedents]")
        for case in response.similar_cases:
            print(f"  - {case}")

    if response.sources:
        print(f"\n[Cited Evidence Sources ({len(response.sources)} total)]")
        for src in response.sources[:3]:
            score_txt = f" (relevance: {src.get('score', 0):.2f})" if "score" in src else ""
            print(f"  - [{src.get('source_id', 'N/A')}] {src.get('title', 'Unknown')}{score_txt}")

    if response.possible_next_steps:
        print("\n[Possible Next Steps]")
        for step in response.possible_next_steps:
            print(f"  - {step}")

    print("\n[Generated Answer]")
    print(response.answer)
    print(format_separator())


def run_sample_tests():
    print(format_separator("INITIALIZING LCC LEGAL ASSISTANT", "#"))
    
    # Initialize pipeline with standard confidence threshold
    config = PipelineConfig(
        confidence_threshold=0.75,
        min_retrieval_score=0.20,
    )
    assistant = LegalAssistant(config=config)
    print("Assistant initialized successfully.")

    # Check if a custom query was passed via command line
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        custom_query = " ".join(sys.argv[1:])
        print(f"\nRunning custom query from CLI: '{custom_query}'")
        res = assistant.ask(custom_query)
        display_response("CUSTOM USER QUERY TEST", custom_query, res)
        return

    # Scenario 1: Realistic Citizen Query (Cyber Fraud / Impersonation)
    query_1 = "Someone called pretending to be a customs officer and made me transfer money."
    res_1 = assistant.ask(query_1)
    display_response("TEST SCENARIO 1: CITIZEN LEGAL QUERY (CYBER FRAUD)", query_1, res_1)

    # Scenario 2: Emergency Safety Guardrail
    query_2 = "Police are arresting me right now, what do I do?"
    res_2 = assistant.ask(query_2)
    display_response("TEST SCENARIO 2: EMERGENCY SAFETY GUARDRAIL", query_2, res_2)

    # Scenario 3: Out-of-Domain / Zero Retrieval Evidence
    query_3 = "How do I register a copyright on a quantum computing blockchain in Switzerland?"
    res_3 = assistant.ask(query_3)
    display_response("TEST SCENARIO 3: OUT-OF-DOMAIN (REFUSAL TO GUESS)", query_3, res_3)

    # Output JSON Schema Validation check
    print("\n" + format_separator("PYDANTIC JSON SERIALIZATION CHECK", "-"))
    sample_json = json.loads(res_1.model_dump_json())
    print("Keys present in output payload:")
    for k in sample_json.keys():
        print(f"  [OK] {k}")
    print("\nAll sample test runs finished successfully!")


if __name__ == "__main__":
    run_sample_tests()
