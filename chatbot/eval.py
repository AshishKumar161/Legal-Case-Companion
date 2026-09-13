"""
LCC Eval Harness — starter skeleton
====================================
Turns "our AI is accurate" into an actual number you can defend live:
faithfulness (are claims grounded in retrieved context?), answer
relevance, and context precision/recall, scored with RAGAS.

Install:
    pip install ragas datasets --break-system-packages

Usage:
    1. Fill in `test_cases` below with 20-100 real query/answer/context
       examples (start small, grow it as you build).
    2. Run: python eval.py
    3. Put the resulting scores on a slide/dashboard for judging —
       this is what makes the "verified, not just claimed" pitch real.
"""

from datasets import Dataset

# TODO: swap these imports for whichever RAGAS metrics you use.
# API surface has shifted across ragas versions — check your installed
# version's docs if this import fails.
from ragas import evaluate
from ragas.metrics import (
    faithfulness,        # does the answer only claim what's in the context?
    answer_relevancy,    # does the answer actually address the question?
    context_precision,   # are the retrieved chunks relevant?
    context_recall,      # did retrieval find the chunks needed to answer?
)


# ---------------------------------------------------------------------------
# Build your test set here.
#
# `question`         -> the user query
# `answer`            -> what YOUR pipeline actually produced (run pipeline.py
#                        over each question first, then paste the outputs in,
#                        or wire this up to call build_graph() directly)
# `contexts`          -> the retrieved chunks your pipeline used
# `ground_truth`      -> the correct answer, written/checked by a human
#                        (ideally someone with legal knowledge, e.g. your
#                        law-student/advocate collaborator)
# ---------------------------------------------------------------------------

test_cases = [
    {
        "question": "Someone called claiming to be from customs and scared me into transferring money. What should I do?",
        "answer": "PLACEHOLDER — replace with real pipeline output",
        "contexts": ["PLACEHOLDER — replace with real retrieved chunk text"],
        "ground_truth": "PLACEHOLDER — replace with a human-verified correct answer",
    },
    # TODO: add 20-100 more rows, ideally covering all 5 shortlisted
    # crime categories (cyber fraud, crimes against women, cheating/
    # forgery, theft/burglary, crimes against senior citizens) so your
    # eval numbers aren't skewed toward one easy category.
]


def run_eval():
    dataset = Dataset.from_list(test_cases)

    results = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )

    print("=== LCC Eval Results ===")
    print(results)
    # results is dict-like; e.g. results["faithfulness"] gives you the
    # number to put on your "94% citation-faithfulness" slide.
    return results


if __name__ == "__main__":
    run_eval()
