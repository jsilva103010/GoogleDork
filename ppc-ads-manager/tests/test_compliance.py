from app.data.compliance import scan_text


def test_flags_outcome_guarantees():
    assert scan_text("We guarantee you'll win your case")


def test_flags_superlative_claims():
    assert scan_text("Voted the best lawyer in Portland")
    assert scan_text("The #1 rated law firm in Oregon")


def test_allows_clean_copy():
    assert scan_text("30+ years of estate planning experience") == []
    assert scan_text("Flat-fee wills and trusts packages") == []
