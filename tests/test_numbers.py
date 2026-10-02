import pytest

from verimem.numbers import extract, missing_quantities


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        # cases from the independent review of the old gate
        ("The invoice total is 1,520 euros.",
         "The invoice total is 1,250 euros, due on March 3."),
        ("The API rate limit is 1000 requests per minute.",
         "The API rate limit is 100 requests per minute per key."),
        ("The migration reduced latency by 40%.",
         "We migrated the search index to OpenSearch last week."),
        ("The meeting is on 4 March.", "The meeting is on 3 March."),
        ("La riunione è a maggio.", "La riunione è ad aprile."),
        ("We hired five engineers.", "We hired 3 engineers."),
        ("The call is at 4 pm.", "La chiamata è alle 15."),
        ("The call is at 3 am.", "La chiamata è alle 15."),
        ("La consegna è alle 16.", "Delivery at 3 pm."),
    ],
)
def test_changed_or_invented_quantities_are_missing(claim, source):
    assert missing_quantities(claim, source)


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        ("The invoice total is 1250 euros.", "The invoice total is 1,250 euros."),
        ("Il totale è 1.250 euro.", "The invoice total is 1,250 euros."),
        ("Il totale è di 1.250,50 euro.", "Total: 1,250.50 EUR"),
        ("We hired three engineers.", "We hired 3 engineers."),
        ("Abbiamo assunto tre ingegneri.", "We hired 3 engineers."),
        ("Abbiamo assunto ventitré persone.", "We hired 23 people."),
        ("Revenue grew 12 percent.", "Revenue grew by 12% in Q3."),
        ("The round was 1.2 million dollars.", "They raised $1,200,000."),
        ("The budget is 3 mila euro.", "Il budget è di 3.000 euro."),
        ("The demo is on March 3.", "The demo was moved to 3 marzo."),
        ("Il volo parte alle 10:30.", "Flight at 10.30 from Linate."),
        ("The demo was moved to Thursday at 3 pm.", "la demo è spostata a giovedì alle 15"),
        ("La demo è alle 15.", "The demo is at 3 p.m."),
        ("The call is at 3:30pm.", "la chiamata è alle 15:30"),
        ("The call is at 3:30 PM.", "la chiamata è alle 15.30"),
        ("The train leaves at 9 am.", "Il treno parte alle 9."),
        ("The call is at 15:00.", "Ci sentiamo alle 3 del pomeriggio."),
        ("Lunch is at noon.", "Il pranzo è alle 12."),
        ("Il pranzo è alle 12.", "Lunch is at noon."),
        ("The backup runs at midnight.", "Il backup parte a mezzanotte."),
        ("The meeting is on 3/3/2026.", "We meet on 2026-03-03."),
        ("Sara leads payments.", "Sara leads the payments team."),
    ],
)
def test_same_quantities_in_other_forms_are_found(claim, source):
    assert missing_quantities(claim, source) == []


def test_articles_and_verbs_are_not_numbers():
    assert extract("Anna is a senior engineer and one of the leads.") == []
    assert extract("Tu sei il responsabile di una squadra.") == []


def test_english_month_names_need_a_capital():
    kinds = [q.kind for q in extract("You may join in May.")]
    assert kinds == ["month"]


def test_metres_are_not_millions():
    (q,) = extract("The cable is 5 m long.")
    assert q.values == {5.0}
    (q,) = extract("They raised 5M.")
    assert 5_000_000.0 in q.values


def test_ambiguous_thousands_keep_both_readings():
    (q,) = extract("1,250")
    assert q.values == {1.25, 1250.0}
    (q,) = extract("10.000")
    assert q.values == {10.0, 10000.0}
