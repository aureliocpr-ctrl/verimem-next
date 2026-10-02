from verimem.text import content_tokens, guess_language, is_question, split_sentences


def texts(s: str) -> list[str]:
    return [sp.text for sp in split_sentences(s)]


def test_offsets_point_into_the_original_text():
    src = "  Maria moved to Milan.  She works at a bank!\nDone?"
    for sp in split_sentences(src):
        assert src[sp.start : sp.end] == sp.text


def test_basic_english_and_italian():
    assert texts("The demo moved to Friday. Anna confirmed it.") == [
        "The demo moved to Friday.",
        "Anna confirmed it.",
    ]
    assert texts("Il deploy è fallito. Il certificato era scaduto!") == [
        "Il deploy è fallito.",
        "Il certificato era scaduto!",
    ]


def test_abbreviations_and_initials_do_not_split():
    assert texts("Dr. Rossi met Mr. J. Smith at 5 p.m. on Monday.") == [
        "Dr. Rossi met Mr. J. Smith at 5 p.m. on Monday."
    ]
    assert texts("Ho parlato con il Dott. Bianchi, ecc. e poi sono uscito.") == [
        "Ho parlato con il Dott. Bianchi, ecc. e poi sono uscito."
    ]
    # titles and offices in Italian business chats
    assert texts("Lavoro in banca (sono il resp. IT). Il dir. Neri è d'accordo.") == [
        "Lavoro in banca (sono il resp. IT).", "Il dir. Neri è d'accordo."
    ]
    assert texts("Chiama l'uff. acquisti, tel. 02 1234, rif. ordine 7.") == [
        "Chiama l'uff. acquisti, tel. 02 1234, rif. ordine 7."
    ]


def test_decimals_and_versions_do_not_split():
    assert texts("The total is 1.250,50 euro. Version 2.3 shipped.") == [
        "The total is 1.250,50 euro.",
        "Version 2.3 shipped.",
    ]


def test_chat_lines_are_sentences_even_without_punctuation():
    src = "User: I moved to Bologna\nAssistant: noted\nUser: my daughter started school"
    assert texts(src) == [
        "User: I moved to Bologna",
        "Assistant: noted",
        "User: my daughter started school",
    ]


def test_hard_wrapped_paragraph_is_joined():
    src = (
        "The incident was resolved by restarting the cache nodes after the on-call\n"
        "engineer noticed the memory pressure alerts. Nobody lost data."
    )
    assert texts(src) == [
        "The incident was resolved by restarting the cache nodes after the on-call\n"
        "engineer noticed the memory pressure alerts.",
        "Nobody lost data.",
    ]


def test_bullets_are_separate():
    assert texts("Decisions:\n- use PostgreSQL 16\n- keep SQLite for tests") == [
        "Decisions:",
        "- use PostgreSQL 16",
        "- keep SQLite for tests",
    ]


def test_empty_text():
    assert split_sentences("") == []
    assert split_sentences("   \n ") == []


def test_language_guess():
    assert guess_language("Il cliente non ha rinnovato il contratto a settembre.") == "it"
    assert guess_language("The client did not renew the contract in September.") == "en"
    assert guess_language("PostgreSQL 16") == "und"


def test_content_tokens_drop_stopwords_keep_digits():
    toks = content_tokens("The API limit is 100 requests per minute for the key")
    assert {"api", "limit", "100", "requests", "minute", "key"} <= toks
    assert "the" not in toks and "is" not in toks


def test_questions_are_recognised():
    assert is_question("Did Maria move to Milan?")
    assert is_question('Luca asked: "Is it true?"')
    assert is_question("Davvero?!")
    assert not is_question("Maria moved to Milan.")
    assert not is_question("Is it 3? Yes.")
