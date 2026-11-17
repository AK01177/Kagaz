"""Structure-aware policy chunking (RAG Phase 2)."""
from services.policy_chunking import MAX_CHARS, TARGET_CHARS, chunk_policy, chunk_text
from services.policy_text import SourcePage


def contents(text: str) -> list[str]:
    return [chunk.content for chunk in chunk_text(text)]


def test_each_numbered_clause_is_its_own_chunk_labelled_with_its_section():
    chunks = chunk_text(
        "## 2. Casual Leave\n"
        "2.1 Employees get 12 days of casual leave per year.\n"
        "2.2 Casual leave needs 7 days notice.\n"
    )
    assert [c.content for c in chunks] == [
        "2. Casual Leave: 2.1 Employees get 12 days of casual leave per year.",
        "2. Casual Leave: 2.2 Casual leave needs 7 days notice.",
    ]
    assert all(c.section == "2. Casual Leave" for c in chunks)


def test_wrapped_lines_and_sub_items_stay_inside_their_clause():
    chunks = contents(
        "4.1 Leave is of two kinds and the\n"
        "employee must pick one:\n"
        "(a) casual leave, paid.\n"
        "(b) sick leave, paid.\n"
        "4.2 Nothing else applies to this clause here.\n"
    )
    assert len(chunks) == 2
    assert "the employee must pick one:" in chunks[0]
    assert "(a) casual leave, paid.\n(b) sick leave, paid." in chunks[0]


def test_a_very_short_clause_is_merged_with_the_next_one_so_it_is_not_lost():
    chunks = contents("1.1 Scope.\n1.2 This policy applies to every employee of the company worldwide.\n")
    assert len(chunks) == 1
    assert "1.1 Scope." in chunks[0] and "1.2 This policy" in chunks[0]


def test_prose_is_packed_up_to_the_target_size_and_never_exceeds_the_maximum():
    sentences = [f"Sentence number {n} describes one rule of the policy." for n in range(120)]
    chunks = contents(" ".join(sentences))
    assert len(chunks) > 1
    assert all(len(chunk) <= MAX_CHARS for chunk in chunks)
    joined = " ".join(chunks)
    assert all(sentence in joined for sentence in sentences)  # nothing lost


def test_a_long_clause_is_split_on_sentence_boundaries_and_keeps_its_label():
    clause = "5.1 " + " ".join(f"Rule {n} must always be followed by staff." for n in range(80))
    chunks = chunk_text(f"## 5. Conduct\n{clause}\n")
    assert len(chunks) > 1
    assert all(len(c.content) <= MAX_CHARS and c.content.startswith("5. Conduct: ") for c in chunks)


def test_text_with_no_spaces_is_still_split_and_terminates():
    text = "".join(str(n) for n in range(1200))  # long, no spaces, no repeated pieces
    chunks = contents(text)
    assert len(chunks) > 1 and all(len(chunk) <= MAX_CHARS for chunk in chunks)
    assert "".join(chunks) == text


def test_prose_paragraphs_are_not_merged_across_headings():
    chunks = chunk_text("## Leave\nShort leave rule applies.\n\n## Travel\nShort travel rule applies.\n")
    assert [c.section for c in chunks] == ["Leave", "Travel"]
    assert TARGET_CHARS > len(chunks[0].content)


def test_repeated_page_headers_footers_and_page_numbers_are_removed_but_body_text_is_kept():
    pages = [
        SourcePage(n, f"Acme Corp Confidential\n{n}.1 Clause one for page {n} of this policy document.\nPage {n} of 4")
        for n in range(1, 5)
    ]
    text = " ".join(chunk.content for chunk in chunk_policy(pages))
    assert "Confidential" not in text and "Page 1 of 4" not in text
    assert all(f"{n}.1 Clause one for page {n}" in text for n in range(1, 5))


def test_body_lines_that_look_alike_across_pages_are_not_mistaken_for_footers():
    pages = [
        SourcePage(n, "\n".join(f"Clause {n}.{i}: Keep receipts for travel expenses." for i in (1, 2, 3, 30)))
        for n in range(1, 4)
    ]
    text = " ".join(chunk.content for chunk in chunk_policy(pages))
    assert all(f"Clause {n}.{i}:" in text for n in range(1, 4) for i in (1, 2, 3, 30))


def test_bare_numbers_are_kept_when_the_source_has_no_pages():
    assert any("10" in chunk for chunk in contents("Quantities\n10\n20\nare listed above."))


def test_a_clause_remembers_the_page_it_starts_on():
    chunks = chunk_policy([
        SourcePage(1, "1.1 First clause is long enough to stand on its own here."),
        SourcePage(2, "2.1 Second clause is long enough to stand on its own here."),
    ])
    assert [c.page_number for c in chunks] == [1, 2]


def test_an_uncertain_heading_with_no_body_is_kept_as_text_but_an_explicit_title_is_not():
    chunks = contents("# Acme Leave Policy\n3. Employees must submit the form")
    # The title only labels; the guessed heading is kept because it may be a real rule.
    assert chunks == ["Acme Leave Policy: 3. Employees must submit the form"]


def test_table_rows_stay_readable():
    chunks = contents("Leave type | Days | Notice\nCasual | 12 | 7 days\nSick | 10 | none\n")
    assert "Casual | 12 | 7 days" in " ".join(chunks)


def test_identical_chunks_are_stored_once():
    clause = "1.1 Keep every receipt for seven years after the claim is paid."
    assert len(chunk_text(f"{clause}\n\n{clause}\n")) == 1


def test_blank_input_gives_no_chunks():
    assert chunk_text("") == [] and chunk_text("  \n\n ") == []
