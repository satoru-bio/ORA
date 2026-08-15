# ORA — Organic Residue Archive

Harmonised compound-specific δ¹³C dataset from published British and Irish Neolithic pottery lipid residue studies, paired with a web tool for contextualising new analyses against the published corpus.

**327 records · 3 studies · 13 sites · CC-BY 4.0 (data) · MIT (code)**

---

## Licence

| Component | Licence |
|---|---|
| Code (pipeline, frontend) | MIT — see `LICENSE` |
| Dataset (`data/exports/corpus.json`, `corpus.csv`) | **CC-BY 4.0** — see `LICENSE` |

Reuse of the dataset requires citation of (1) this repository and (2) the original study listed in each record's `source.citation` field. See `LICENSE` for the full per-record attribution requirement.

---

## Dataset provenance

Three papers are in the active corpus. All values are single-compound GC-C-IRMS measurements of C16:0 and C18:0 fatty acids extracted from Neolithic ceramic sherds.

| Paper | DOI | Records | Sites | Extraction |
|---|---|---|---|---|
| Copley et al. 2005 (III) — *Dairying in antiquity. III. Evidence from absorbed lipid residues dating to the British Neolithic*, JAS 32:523–546 | [10.1016/j.jas.2004.08.006](https://doi.org/10.1016/j.jas.2004.08.006) | 191 | 6 (Abingdon, Eton Rowing Lake, Hambledon Hill, Runnymede Bridge, Windmill Hill, Yarnton FP) | Tier B — LLM-assisted table extraction from paywalled PDF |
| Hammann et al. 2022 — *Neolithic culinary traditions revealed by cereal, milk and meat lipids in pottery from Scottish crannogs*, Nat Commun 13:5045 | [10.1038/s41467-022-32286-0](https://doi.org/10.1038/s41467-022-32286-0) | 29 | 5 crannog sites | Tier A — parsed from deposited source data (CC-BY) |
| Smyth & Evershed 2016 — *Milking the megafauna: Using organic residue analysis to understand early farming practice*, Environ Archaeol 21(3):214–229 | [10.1179/1749631414Y.0000000045](https://doi.org/10.1179/1749631414Y.0000000045) | 107 | 7 (Ballygalley, Donegore Hill, Haggardstown, Kilmainham 1C, Magheraboy, Monanny, Upper Campsie) | Tier B — LLM-assisted table extraction from paywalled PDF |

Extraction tiers: **Tier A** = deterministic parse of machine-readable deposit; **Tier B** = LLM-assisted extraction from PDF table/appendix, human-reviewed; **Tier C** = figure digitisation (not implemented in v1).

---

## Known data issues

**AB30** (Copley III, Abingdon): δ¹³C₁₈:₀ = −20.7‰ is confirmed verbatim from the published table but is physically implausible for a Neolithic ceramic context. Column order has been verified (not a column swap). Cause is undetermined (typographical error, production error, or unusual sample). The record is retained for citation integrity and carries the flag `value_verbatim_physically_implausible`. Do not use AB30 in quantitative analysis without verification against the authors' raw data.

---

## Reference-band methodology

The web tool's reference bands use the Δ¹³C thresholds −1.0‰ and −3.1‰ from Copley et al. 2003 and Evershed et al. 2008:

| Δ¹³C = δ¹³C₁₈:₀ − δ¹³C₁₆:₀ | Field |
|---|---|
| < −3.1‰ | Ruminant dairy |
| −3.1 to −1.0‰ | Ruminant adipose |
| > −1.0‰ | Non-ruminant adipose |

**These bands are a 1D projection.** The source papers classified samples using 2D reference ellipses in δ¹³C₁₆:₀ / δ¹³C₁₈:₀ space. A sample can plot within a Δ¹³C band while falling outside the corresponding reference ellipse, particularly at relatively high δ¹³C₁₆:₀. Samples near the −3.1‰ boundary should be assessed in the scatter view (δ¹³C₁₆:₀ vs δ¹³C₁₈:₀) rather than read from the band label alone. Rendering the actual 2D reference ellipses is a planned v2 feature.

The tool plots and contextualises. It does not classify. Field membership is context, not identification.

---

## Excluded papers

These papers were evaluated and excluded from v1. Each entry notes the reason and reinstatement path.

| Paper | DOI | Reason | Reinstatement |
|---|---|---|---|
| Copley et al. 2003 — *Direct chemical evidence for widespread dairying in prehistoric Britain*, PNAS 100:1524–1529 | [10.1073/pnas.0335955100](https://doi.org/10.1073/pnas.0335955100) | Per-sherd δ¹³C values appear only in Figure 1 (scatter plot); no SI or data deposit. Formal dataset published as Copley III (above), which is in the active corpus. Including 2003 values would risk duplicate sample IDs. | Tier C figure digitisation (WebPlotDigitizer) if data not covered by Copley III |
| Mukherjee et al. 2008 — *Lipid residues in pottery from the British Neolithic*, JAS 35:2059–2073 | [10.1016/j.jas.2008.01.010](https://doi.org/10.1016/j.jas.2008.01.010) | Per-sherd values only in Figures 6–9 (scatter plots); no SI or data deposit found. Unique dataset: 222 Grooved Ware sherds from domestic vs ceremonial sites, not covered by any other corpus paper. | Tier C figure digitisation; reinstate with `extraction_route=tierC_figure` |
| Cramp et al. 2014 — *Immediate replacement of fishing with dairying by the earliest farmers of the NE Atlantic archipelagos*, PRSB 281:20132372 | [10.1098/rspb.2013.2372](https://doi.org/10.1098/rspb.2013.2372) | ESM inaccessible: old RSB server gone, new domain returns 403. Bristol raw IRMS deposit ([10.5523/bris.upjtf9os1dzr154phmgvrupib](https://doi.org/10.5523/bris.upjtf9os1dzr154phmgvrupib)) exists but is 1.1 GiB of replicate-level instrument runs, not a clean per-sample table. | Reinstate if ESM is recovered from authors, or if Bristol deposit is parsed (Tier A). Note: Δ¹³C alone cannot resolve aquatic/marine from non-ruminant adipose — this paper's Scottish island and coastal context requires biomarker evidence beyond the current tool's scope. |

---

## Repository structure

```
pipeline/
  00_fetch.py          fetch and cache PDFs by DOI
  01_tier_a_parse.py   deterministic parse for deposited data (Hammann)
  02_tier_b_extract.py LLM-assisted extraction for PDF tables (Copley III, Smyth)
  03_validate.py       schema, plausibility, and author-agreement QA
  04_ingest_db.py      load extracted JSONs into PostgreSQL (Docker)
  05_export.py         export corpus.json / corpus.csv from DB or extracted JSONs
  seed_corpus.py       authoritative DOI list and exclusion registry
  common.py            shared schema, thresholds, DB helpers

data/
  exports/
    corpus.json        full dataset (CC-BY 4.0)
    corpus.csv         same, tabular

frontend/
  src/App.jsx          React/Recharts web tool
  public/corpus.json   frontend copy of dataset

docker-compose.yml     PostgreSQL 16 + PostGIS for local pipeline runs
```

---

## Citing

If you use this dataset, please cite the original studies in addition to this repository. Each record carries a `source.citation` and `source.doi` field identifying which paper it came from.

Suggested repository citation:

> Satoru / DigiShield Labs (2026). *ORA: Organic Residue Archive — harmonised compound-specific δ¹³C dataset from British and Irish Neolithic pottery*. https://github.com/satoru-bio/ORA. CC-BY 4.0.

---

## Stack

Python pipeline · PostgreSQL 16/PostGIS (Docker) · React/Vite/Recharts frontend
