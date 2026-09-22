"""
Satoru / ORA - fixed seed corpus for compound-specific delta-13C extraction.

British and Irish Neolithic single-compound stable carbon isotope papers.
This is the authoritative extraction set. The --all flag MUST iterate
SEED_DOIS, never a folder glob, so stray PDFs in the data dir (e.g. the
deferred Dudd file 1-s2.0-S0305440398904344-main.pdf) cannot enter a run.

DOIs verified against publisher and citation records, 2026-06-26.

NB list length: the corpus is THREE active papers. Three papers were removed:
- Copley et al. 2003 (PNAS): per-sherd values only in Figure 1 (Tier C); data
  subsumed by Copley et al. 2005 (III) which is in the active corpus.
- Mukherjee et al. 2008 (JAS): per-sherd values only in Figures 6-9 (Tier C);
  no SI or data deposit found; unique Grooved Ware data, reinstate if digitised.
- Cramp et al. 2014 (PRSB): ESM inaccessible (old RSB server gone, new domain
  403s); Bristol raw IRMS deposit (10.5523/bris.upjtf9os1dzr154phmgvrupib)
  exists but is 1.1 GiB replicate-level runs, not clean per-sample values.
See EXCLUDED_DOIS for full notes on all three.

Keying route: Hammann is open with deposited machine-readable isotope data
(Tier A). The two Tier B papers are table/appendix extractions.
"""

# Canonical DOIs - the array --all iterates. Order is fetch order.
SEED_DOIS = [
    "10.1016/j.jas.2004.08.006",       # Copley et al. 2005 (III),  JAS 32:523-546 (Neolithic)
    "10.1038/s41467-022-32286-0",      # Hammann et al. 2022,       Nat Commun 13:5045
    "10.1179/1749631414Y.0000000045",  # Smyth & Evershed 2016,     Environ Archaeol 21(3):214-229
]

# Full provenance, for per-record attribution and for sanity-checking the fetch
# resolved to the intended paper (guards against silently keying a trap twin).
SEED_CORPUS = [
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
    # Cramp 2014 (PRSB) - removed from active corpus 2026-08-14.
    # ESM inaccessible: old RSB server (rspb.royalsocietypublishing.org) gone; new domain
    # (royalsocietypublishing.org) returns 403. Bristol raw IRMS deposit exists
    # (10.5523/bris.upjtf9os1dzr154phmgvrupib, 1.1 GiB, replicate-level runs) but is not
    # a clean per-sample table and is not worth parsing for v1. Reinstate if ESM is
    # recovered from authors or if Bristol deposit is parsed in a future Tier A pass.
    "10.1098/rspb.2013.2372":
        "Cramp et al. 2014 PRSB 281(1780):20132372 - ESM inaccessible (old RSB server "
        "gone, new domain 403s). Bristol raw IRMS deposit "
        "(10.5523/bris.upjtf9os1dzr154phmgvrupib) exists but is replicate-level, not "
        "per-sample. Reinstate if ESM recovered or Bristol deposit parsed (Tier A).",
    # Mukherjee 2008 (JAS) - removed from active corpus 2026-08-14.
    # Per-sherd delta-13C values appear only in Figures 6-9 (scatter plots); no SI,
    # no data deposit found. Data is unique (222 Grooved Ware sherds, domestic vs
    # ceremonial sites) and not covered by any other paper in the corpus. Reinstate
    # if per-sherd values are recovered via Tier C digitisation (WebPlotDigitizer).
    "10.1016/j.jas.2008.01.010":
        "Mukherjee et al. 2008 JAS 35:2059-2073 - per-sherd values only in Figures "
        "6-9 (Tier C, scatter plots, no SI). Unique Grooved Ware data; reinstate with "
        "extraction_route=tierC_figure if digitised.",
    # Copley 2003 (PNAS) - removed from active corpus 2026-08-14.
    # Per-sherd delta-13C values appear only in Figure 1 (scatter plot); no SI, no data deposit.
    # The same Bristol research group published their formal Neolithic per-sherd dataset in
    # Copley et al. 2005 (III), JAS 32:523-546 (10.1016/j.jas.2004.08.006), which IS in the
    # active corpus (191 records). Including the 2003 PNAS figure values would risk duplicate
    # sample_ids and adds no data not already captured in the 2005 JAS series.
    "10.1073/pnas.0335955100":
        "Copley et al. 2003 PNAS 100:1524-1529 - per-sherd values only in Figure 1 (Tier C, "
        "scatter plot, no SI). Formal dataset published as Copley et al. 2005 (III), JAS "
        "32:523-546, which is in the active corpus. Excluded to avoid duplicate sample_ids.",
}

# Copley siblings in the same JAS volume are excluded by period rather than by
# DOI (they are not in SEED_DOIS so will not be fetched; this note is for any
# maintainer tempted to add them): Iron Age (I) = JAS 32:485-503;
# Bronze Age (II) = JAS 32:505-521. Only the Neolithic (III, 523-546) is in scope.

# Value-provenance annotations (D-008 schema change). Applied to records by
# common.apply_provenance(); a value already on a record always wins.
# "sites": None means every record from that DOI.
#
# provenance_of_value is defined by first NUMERIC report (tabulated or stated in
# text). A figure-only plot is not a numeric report, so all current records are
# "original"; earlier plots are recorded in prior_graphical_report instead.
COPLEY_2003_PNAS = "10.1073/pnas.0335955100"
PROVENANCE_ANNOTATIONS = [
    {
        "doi": "10.1016/j.jas.2004.08.006",
        "sites": ["Windmill Hill", "Hambledon Hill"],
        "prior_graphical_report": COPLEY_2003_PNAS,
    },
    {
        "doi": "10.1016/j.jas.2004.08.006",
        "sites": ["Eton Rowing Lake"],
        "prior_graphical_report": COPLEY_2003_PNAS,
        "provenance_note": (
            "Approximately 23 of the 37 Eton Rowing Lake values were plotted in "
            "Copley et al. 2003 (PNAS) Fig. 3; which ones cannot be determined."
        ),
    },
    {
        "doi": "10.1179/1749631414Y.0000000045",
        "sites": None,
        "provenance_note": (
            "Not verified against sibling publications (2014 book chapter; "
            "2015 PRIA paper)."
        ),
    },
]

if __name__ == "__main__":
    assert len(SEED_DOIS) == len(SEED_CORPUS) == 3
    assert {c["doi"] for c in SEED_CORPUS} == set(SEED_DOIS)
    assert not (set(SEED_DOIS) & set(EXCLUDED_DOIS)), "seed/exclude overlap"
    print(f"{len(SEED_DOIS)} seed DOIs, {len(EXCLUDED_DOIS)} excluded\n")
    for c in SEED_CORPUS:
        print(f"  {c['doi']:34} {c['ref']:26} {c['access']}")
