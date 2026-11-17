"""Exact figures in a question: extraction, matching and ranking (RAG Phase 3)."""
from types import SimpleNamespace

import pytest

from services.policy_retrieval import EXACT_TERM_BOOST, _rank_by_exact_terms, _term_pattern, exact_terms


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What does clause 2.3 say?", ["2.3"]),
        ("Net 30", ["30"]),
        ("Is $1,000 the limit, or 5% of $500?", ["1,000", "5%", "500"]),
        ("Leave on 12/05 or 12/06.", ["12/05", "12/06"]),
        ("It ended. 30. Then 30 again", ["30"]),  # sentence punctuation is not part of the figure
        ("How many days of leave?", []),
        ("", []),
    ],
)
def test_figures_are_extracted_without_surrounding_punctuation(question, expected):
    assert exact_terms(question) == expected


@pytest.mark.parametrize(
    ("term", "text", "matches"),
    [
        ("2.3", "2. Expense Claims: 2.3 Any single claim", True),
        ("2.3", "see clause 12.3", False),  # inside another number
        ("2.3", "clause 2.30 applies", False),
        ("2.3", "as stated in 2.3.", True),  # end of sentence
        ("30", "Net 30 days", True),
        ("30", "about 2030", False),
        ("500", "above $500 requires approval", True),
        ("1,000", "purchase above $1,000.", True),
        ("5%", "a late fee of 5% applies", True),
    ],
)
def test_a_figure_only_matches_as_a_whole_token(term, text, matches):
    assert bool(_term_pattern(term).search(text)) is matches


def row(score: float, text: str):
    return (None, None, SimpleNamespace(content=text), score, None)


def test_chunks_containing_the_question_figures_are_ranked_above_closer_but_figureless_ones():
    figureless = row(0.70, "General expense rules apply to everyone.")
    exact = row(0.64, "2.3 Claims above $500 need approval.")
    assert _rank_by_exact_terms([figureless, exact], ["2.3"]) == [exact, figureless]


def test_similarity_still_orders_chunks_that_match_the_same_figures():
    better, worse = row(0.72, "Net 30 terms"), row(0.60, "30 days notice")
    assert _rank_by_exact_terms([worse, better], ["30"]) == [better, worse]


def test_the_boost_is_capped_so_figures_cannot_outweigh_a_much_closer_chunk():
    closest = row(0.90, "Unrelated wording entirely.")
    stuffed = row(0.60, "1 2 3 4 5 6 7 8 9")
    ranked = _rank_by_exact_terms([stuffed, closest], ["1", "2", "3", "4", "5"])
    assert ranked[0] is closest and 0.60 + 2 * EXACT_TERM_BOOST < 0.90
