"""
Indian Kanoon Case Ingestion Utility for Legal Case Companion.
Fetches high-relevance court judgments across the 6 target categories from Indian Kanoon API:
- cyber_fraud
- cheating_forgery
- theft_burglary
- crimes_against_women
- matrimonial_disputes
- crimes_against_senior_citizens (senior_citizens)

Outputs: chatbot/data/indian_cases_100.json
"""

import os
import sys
import json
import time
import argparse
import logging
from typing import List, Dict, Any

try:
    import requests
except ImportError:
    print("Requests library not found. Install via 'pip install requests'")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("indian_kanoon_fetcher")

DEFAULT_BASE_URL = "https://api.indiankanoon.org/search/"

KEYWORD_CATEGORIES = {
    "cyber_fraud": "OTP OR phishing OR scam OR hacking AND '66D'",
    "cheating_forgery": "cheating OR forgery OR '420 IPC' OR counterfeit",
    "theft_burglary": "theft OR robbery OR snatched OR '379 IPC'",
    "crimes_against_women": "cruelty OR dowry OR '498A' OR 'domestic violence'",
    "matrimonial_disputes": "divorce OR desertion OR annulment OR maintenance",
    "senior_citizens": "Senior Citizens Act 2007 OR 'elder neglect' OR 'Section 23'",
}


def get_api_token(cli_token: str | None = None) -> str:
    """Retrieves Indian Kanoon API key from CLI argument, environment variable, or .env file."""
    if cli_token and cli_token != "YOUR_INDIAN_KANOON_API_KEY":
        return cli_token

    env_token = os.environ.get("INDIAN_KANOON_API_KEY")
    if env_token and env_token != "YOUR_INDIAN_KANOON_API_KEY":
        return env_token

    # Check .env in parent directories
    for search_dir in [".", "..", "../.."]:
        env_path = os.path.join(search_dir, ".env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("INDIAN_KANOON_API_KEY="):
                        val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
                        if val and val != "YOUR_INDIAN_KANOON_API_KEY":
                            return val

    return ""


def fetch_cases_per_category(
    category: str,
    query: str,
    target_count: int = 17,
    api_token: str = "",
    base_url: str = DEFAULT_BASE_URL,
) -> List[Dict[str, Any]]:
    """Fetches up to target_count judgments for a legal category from Indian Kanoon."""
    headers = {"Authorization": f"Token {api_token}"}
    cases: List[Dict[str, Any]] = []
    page = 0

    logger.info(f"Querying Indian Kanoon for '{category}' (query: '{query}')...")

    while len(cases) < target_count:
        params = {"formInput": query, "pagenum": page}
        try:
            res = requests.post(base_url, headers=headers, data=params, timeout=15)
        except Exception as e:
            logger.error(f"Network error querying Indian Kanoon ({category}, page {page}): {e}")
            break

        if res.status_code != 200:
            logger.warning(f"Indian Kanoon responded with status {res.status_code} for '{category}': {res.text[:120]}")
            break

        try:
            data = res.json()
        except Exception as e:
            logger.warning(f"Could not parse Indian Kanoon JSON response: {e}")
            break

        docs = data.get("docs", [])
        if not docs:
            logger.info(f"No further documents returned for '{category}' at page {page}.")
            break

        for doc in docs:
            tid = doc.get("tid")
            cases.append({
                "category": category,
                "title": doc.get("title", f"Case {tid}"),
                "tid": tid,
                "headline": doc.get("headline", ""),
                "doc_url": f"https://indiankanoon.org/doc/{tid}/",
            })
            if len(cases) >= target_count:
                break

        page += 1
        time.sleep(1)  # Respect API rate limits

    logger.info(f"Retrieved {len(cases)} cases for category '{category}'.")
    return cases


def compile_indian_kanoon_dataset(
    api_token: str,
    output_file: str,
    target_per_category: int = 17,
    max_total: int = 100,
) -> List[Dict[str, Any]]:
    """Fetches across all 6 categories and saves the compiled dataset to output_file."""
    all_cases: List[Dict[str, Any]] = []

    for category, query in KEYWORD_CATEGORIES.items():
        cat_cases = fetch_cases_per_category(
            category=category,
            query=query,
            target_count=target_per_category,
            api_token=api_token,
        )
        all_cases.extend(cat_cases)

    final_cases = all_cases[:max_total]

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(final_cases, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully compiled and saved {len(final_cases)} cases to '{output_file}'.")
    return final_cases


def main():
    parser = argparse.ArgumentParser(description="Fetch Indian Kanoon legal cases for LCC chatbot.")
    parser.add_argument("--api-key", default=None, help="Indian Kanoon API Token")
    parser.add_argument(
        "--output",
        default="chatbot/data/indian_cases_100.json",
        help="Path to output JSON file (default: chatbot/data/indian_cases_100.json)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=17,
        help="Target cases per category (default: 17, total ~100)",
    )
    args = parser.parse_args()

    token = get_api_token(args.api_key)
    if not token:
        logger.error(
            "Missing Indian Kanoon API key. Set INDIAN_KANOON_API_KEY environment variable or pass --api-key <token>."
        )
        sys.exit(1)

    compile_indian_kanoon_dataset(
        api_token=token,
        output_file=args.output,
        target_per_category=args.count,
    )


if __name__ == "__main__":
    main()
