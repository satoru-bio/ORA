"""
Satoru / ORA - fixed seed corpus for compound-specific delta-13C extraction.

British and Irish Neolithic single-compound stable carbon isotope papers.
This is the authoritative extraction set. The --all flag MUST iterate
SEED_DOIS, never a folder glob, so stray PDFs in the data dir (e.g. the
deferred Dudd file 1-s2.0-S0305440398904344-main.pdf) cannot enter a run.

DOIs verified against publisher and citation records, 2026-06-26.

NB list length: the corpus is SIX papers. A prior pipeline note referenced a
five-DOI list. Confirm whether Copley 2003 (PNAS, open) was being ingested by
a separate path before relying on --all across all six. If not, this is the
full set and the five-DOI note is stale.

Keying route splits on access: Cramp and Hammann are open with deposited
machine-readable isotope data (deposit-pull). The three paywalled papers are
the table/figure digitisation jobs.
"""

# Canonical DOIs - the array --all iterates. Order is fetch order.
SEED_DOIS = [
    "10.1073/pnas.0335955100",         # Copley et al. 2003,        PNAS 100:1524-1529
    "10.1016/j.jas.2004.08.006",       # Copley et al. 2005 (III),  JAS 32:523-546 (Neolithic)
    "10.1016/j.jas.2008.01.010",       # Mukherjee et al. 2008,     JAS 35:2059-2073
    "10.1098/rspb.2013.2372",          # Cramp et al. 2014,         PRSB 281(1780):20132372
    "10.1038/s41467-022-32286-0",      # Hammann et al. 2022,       Nat Commun 13:5045
    "10.1179/1749631414Y.0000000045",  # Smyth & Evershed 2016,     Environ Archaeol 21(3):214-229
]

# Full provenance, for per-record attribution and for sanity-checking the fetch
# resolved to the intended paper (guards against silently keying a trap twin).
SEED_CORPUS = [
    {
        "doi": "10.1073/pnas.0335955100",
        "ref": "Copley et al. 2003",
        "title": "Direct chemical evidence for widespread dairying in prehistoric Britain",
        "journal": "PNAS",
        "locator": "100:1524-1529",
        "access": "open",
        "data": "in-text tables/figures",
    },
    {
        "doi": "10.1016/j.jas.2004.08.006",
        "ref": "Copley et al. 2005 (III)",
        "title": "Dairying in antiquity. III. Evidence from absorbed lipid residues dating to the British Neolithic",
        "journal": "Journal of Archaeological Science",
        "locator": "32:523-546",
        "access": "paywalled",
        "data": "tables/figures",
    },
    {
        "doi": "10.1016/j.jas.2008.01.010",
        "ref": "Mukherjee et al. 2008",
        "title": "Trends in pig product processing at British Neolithic Grooved Ware sites traced through organic residues in potsherds",
        "journal": "Journal of Archaeological Science",
        "locator": "35:2059-2073",
        "access": "paywalled",
        "data": "tables/figures",
    },
    {
        "doi": "10.1098/rspb.2013.2372",
        "ref": "Cramp et al. 2014",
        "title": "Immediate replacement of fishing with dairying by the earliest farmers of the northeast Atlantic archipelagos",
        "journal": "Proceedings of the Royal Society B",
        "locator": "281(1780):20132372",
        "access": "open (CC-BY)",
        "data": "single-compound stable isotope data deposited at Bristol RDR "
                "(doi:10.5523/bris.upjtf9o..., confirm full id from the paper's "
                "data-accessibility statement); deposit-pull, not figure work",
    },
    {
        "doi": "10.1038/s41467-022-32286-0",
        "ref": "Hammann et al. 2022",
        "title": "Neolithic culinary traditions revealed by cereal, milk and meat lipids in pottery from Scottish crannogs",
        "journal": "Nature Communications",
        "locator": "13:5045",
        "access": "open (CC-BY)",
        "data": "source data deposited with article; confirm single-compound "
                "delta-13C present before treating as deposit-pull",
    },
    {
        "doi": "10.1179/1749631414Y.0000000045",
        "ref": "Smyth & Evershed 2016",
        "title": "Milking the megafauna: Using organic residue analysis to understand early farming practice",
        "journal": "Environmental Archaeology",
        "locator": "21(3):214-229",
        "access": "paywalled",
        "data": "tables/figures",
    },
]

# Hard-exclude guard. Each is a near-twin of a seed paper. If any of these
# surfaces via citation-following, a folder glob, or a fetch, drop it. Do not
# re-add without an explicit logged decision.
EXCLUDED_DOIS = {
    # Bad DOI originally logged for Copley III; superseded above.
    "10.1016/j.jas.2004.05.003":
        "Incorrect DOI first logged for Copley III; superseded by 10.1016/j.jas.2004.08.006",
    # Cramp Finland twin - wrong region, same year/volume.
    "10.1098/rspb.2014.0819":
        "Cramp et al. 2014 Finland twin (Neolithic dairy farming at the extreme "
        "of agriculture in northern Europe), PRSB 281 art.20140819 - NOT the "
        "British/Irish paper",
    # Smyth & Evershed 2015 - different paper, different journal.
    "10.1353/ria.2015.0011":
        "Smyth & Evershed 2015 (The molecules of meals), PRIA Section C "
        "115:27-46 - different paper, not in corpus",
    # Mukherjee 2007 Antiquity precursor - dropped by decision.
    "10.1017/S0003598X00095703":
        "Mukherjee et al. 2007 Antiquity precursor - dropped by decision; "
        "resolves and is obtainable if ever reinstated",
    # Stale Mukherjee 2008 DOI used in early pipeline draft; superseded above.
    "10.1016/j.jas.2008.01.005":
        "Old/incorrect Mukherjee 2008 DOI; superseded by 10.1016/j.jas.2008.01.010",
    # Stale Smyth & Evershed 2016 DOI used in early pipeline draft; superseded above.
    "10.1080/14614103.2016.1164345":
        "Old/incorrect Smyth & Evershed 2016 DOI; superseded by 10.1179/1749631414Y.0000000045",
}

# Copley siblings in the same JAS volume are excluded by period rather than by
# DOI (they are not in SEED_DOIS so will not be fetched; this note is for any
# maintainer tempted to add them): Iron Age (I) = JAS 32:485-503;
# Bronze Age (II) = JAS 32:505-521. Only the Neolithic (III, 523-546) is in scope.

if __name__ == "__main__":
    assert len(SEED_DOIS) == len(SEED_CORPUS) == 6
    assert {c["doi"] for c in SEED_CORPUS} == set(SEED_DOIS)
    assert not (set(SEED_DOIS) & set(EXCLUDED_DOIS)), "seed/exclude overlap"
    print(f"{len(SEED_DOIS)} seed DOIs, {len(EXCLUDED_DOIS)} excluded\n")
    for c in SEED_CORPUS:
        print(f"  {c['doi']:34} {c['ref']:26} {c['access']}")
