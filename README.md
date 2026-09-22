# ORA — Organic Residue Archive

A harmonised dataset of compound-specific δ¹³C values from published lipid residue studies of British and Irish Neolithic pottery, and a web tool for plotting new analyses against those published values.

**327 records · 3 studies · 17 sites · Data: CC-BY-4.0 · Code: MIT**

---

## Licensing

The code and the data have separate licences.

| Component | Licence | File |
|---|---|---|
| Code: `pipeline/`, `frontend/src/`, `db/`, `schema/`, configuration | MIT | [`LICENSE`](LICENSE) |
| Data: `data/exports/corpus.json` (canonical), `data/exports/corpus.csv`, `frontend/public/corpus.json` | CC-BY-4.0 | [`LICENSE-DATA`](LICENSE-DATA) |

The MIT licence does not extend to the dataset files. If you reuse the dataset, cite this repository **and** the original study named in each record's `source.citation` / `source.doi` fields. `LICENSE-DATA` sets out the attribution requirement in full.

---

## Dataset provenance

The active corpus contains three papers. Every value is a single-compound GC-C-IRMS measurement of the C16:0 and C18:0 fatty acids in lipids absorbed into Neolithic ceramic sherds.

| Paper | DOI | Tier | Records | Sites |
|---|---|---|---|---|
| Copley et al. 2005c (*Dairying in antiquity III*). *Evidence from absorbed lipid residues dating to the British Neolithic*. J. Archaeol. Sci. 32(4):523–546 | [10.1016/j.jas.2004.08.006](https://doi.org/10.1016/j.jas.2004.08.006) | **B** | 191 | 6: Abingdon, Eton Rowing Lake, Hambledon Hill, Runnymede Bridge, Windmill Hill, Yarnton FP |
| Hammann et al. 2022. *Neolithic culinary traditions revealed by cereal, milk and meat lipids in pottery from Scottish crannogs*. Nat. Commun. 13:5045 | [10.1038/s41467-022-32286-0](https://doi.org/10.1038/s41467-022-32286-0) | **A** | 29 | 4 crannogs: Loch an Duna (Ranish), Loch Arnish, Loch Bhorgastail, Loch Langabhat |
| Smyth & Evershed 2016. *Milking the megafauna: using organic residue analysis to understand early farming practice*. Environ. Archaeol. 21(3):214–229 | [10.1179/1749631414Y.0000000045](https://doi.org/10.1179/1749631414Y.0000000045) | **B** | 107 | 7: Ballygalley, Donegore Hill, Haggardstown, Kilmainham 1C, Magheraboy, Monanny, Upper Campsie |

In the data files, Copley 2005c is cited as `Copley et al. 2005 (III)`. That label separates it from its two siblings in the same JAS volume (see [Excluded papers](#excluded-papers)).

### Extraction tiers

| Tier | Route | `source.extraction_route` | Used in v1 |
|---|---|---|---|
| **A** | Deterministic parse of machine-readable data deposited with the article | `tierA_parse` | Hammann 2022 |
| **B** | LLM-assisted extraction from a PDF table or appendix, then human review against the source | `tierB_llm` | Copley 2005c, Smyth & Evershed 2016 |
| **C** | Digitising values from published figures | `tierC_figure` | Not implemented in v1 |

Tier A records inherit the accuracy of the deposit itself. All records passed a QA sweep (`pipeline/03_validate.py`) covering provenance, schema, physical plausibility, recomputation of Δ¹³C, and agreement between each author's assignment and the computed band. Each record's `qa.extraction_confidence` and `qa.flags` fields carry that record's outcome.

### Known data issue: AB30

**AB30** (Copley 2005c, Abingdon) has δ¹³C₁₈:₀ = −20.7‰. The value matches the published table exactly, but it is physically implausible for a Neolithic ceramic context. The column order was checked, so this is not a column swap. The cause is unknown: it could be a typographical error, a production error or a genuinely unusual sample. The record stays in the dataset so that citations remain complete, and it carries the flag `value_verbatim_physically_implausible`. Do not use AB30 in quantitative work unless it has been checked against the authors' raw data.

---

## Reference bands are 1D, not 2D

The web tool colours samples by Δ¹³C band, using the −1.0‰ and −3.1‰ thresholds from Copley et al. 2003 and Evershed et al. 2008:

| Δ¹³C = δ¹³C₁₈:₀ − δ¹³C₁₆:₀ | Band |
|---|---|
| < −3.1‰ | Ruminant dairy |
| −3.1 to −1.0‰ | Ruminant adipose |
| > −1.0‰ | Non-ruminant adipose |

**Caveat.** The source papers did not classify samples by Δ¹³C alone. They plotted each sample in two dimensions (δ¹³C₁₆:₀ against δ¹³C₁₈:₀) and compared it with **2D reference ellipses** built from modern authentic fats. The bands in this tool collapse those ellipses onto a single axis. A sample can therefore fall inside a Δ¹³C band while lying outside the matching reference ellipse, most often at relatively high δ¹³C₁₆:₀. For samples near a threshold, especially −3.1‰, use the scatter view (δ¹³C₁₆:₀ vs δ¹³C₁₈:₀) rather than the band label. Rendering the actual 2D reference ellipses is planned for v2.

Other points to keep in mind:

- `author_assignment` records each paper's own interpretation, normalised to the schema's vocabulary. It follows that paper's criteria, not the bands above. Hammann et al. 2022, for example, use Δ¹³C < −3.5‰ for pure dairy fat and call values between −3.5‰ and −3.1‰ a dairy/carcass mixture.
- Δ¹³C cannot tell aquatic or marine fats apart from non-ruminant adipose, because the two overlap. Separating them needs biomarker evidence (isoprenoid acids, C20/C22 APAAs), which this dataset does not include.
- The tool plots values and places them in context. **It does not classify.** Falling inside a band gives context; it does not identify the fat.

---

## Excluded papers

These papers were evaluated and left out of v1. The authoritative list, with full notes, is `EXCLUDED_DOIS` in [`pipeline/seed_corpus.py`](pipeline/seed_corpus.py). No excluded paper goes back in without a logged decision.

### Excluded on data-access grounds

| Paper | DOI | Reason for exclusion | How it could be reinstated |
|---|---|---|---|
| Copley et al. 2003. *Direct chemical evidence for widespread dairying in prehistoric Britain*. PNAS 100:1524–1529 | [10.1073/pnas.0335955100](https://doi.org/10.1073/pnas.0335955100) | Per-sherd δ¹³C values appear only in Figure 1, a scatter plot, with no SI or data deposit. The same group published the formal Neolithic per-sherd dataset as Copley 2005c, which is in the corpus, so adding the 2003 values would risk duplicate `sample_id`s. | Tier C figure digitisation, and only for any samples that Copley 2005c does not already cover. Duplicates would have to be reconciled against Copley 2005c before ingest. |
| Mukherjee et al. 2008. *Trends in pig product processing at British Neolithic Grooved Ware sites traced through organic residues in potsherds*. J. Archaeol. Sci. 35(7):2059–2073 | [10.1016/j.jas.2008.01.010](https://doi.org/10.1016/j.jas.2008.01.010) | Per-sherd values appear only in Figures 6–9, which are scatter plots. No SI or data deposit was found. The data are unique: 222 Grooved Ware sherds from domestic and ceremonial sites, not covered by any other corpus paper. | Tier C figure digitisation (e.g. WebPlotDigitizer), ingested with `extraction_route = tierC_figure`. Getting the values from the authors would allow a higher tier. |
| Cramp et al. 2014. *Immediate replacement of fishing with dairying by the earliest farmers of the northeast Atlantic archipelagos*. Proc. R. Soc. B 281:20132372 | [10.1098/rspb.2013.2372](https://doi.org/10.1098/rspb.2013.2372) | The ESM cannot be retrieved: the old RSB server is gone and the new domain returns 403. A Bristol raw IRMS deposit ([10.5523/bris.upjtf9os1dzr154phmgvrupib](https://doi.org/10.5523/bris.upjtf9os1dzr154phmgvrupib)) exists, but it holds 1.1 GiB of replicate-level instrument runs rather than a per-sample table. | Obtain the ESM from the authors, or parse the Bristol deposit into per-sample values (Tier A). Even once reinstated, Δ¹³C alone cannot separate aquatic/marine fats from non-ruminant adipose at these island and coastal sites. Interpreting them needs biomarker evidence beyond the tool's current scope. |

### Near-twin guards

These DOIs are blocked so that a similar-looking paper, or a stale DOI, cannot be keyed by mistake.

| DOI | What it is | Reinstatement note |
|---|---|---|
| 10.1016/j.jas.2004.05.003 | The wrong DOI first logged for Copley 2005c | Never. Superseded by 10.1016/j.jas.2004.08.006 |
| 10.1016/j.jas.2008.01.005 | The wrong DOI first logged for Mukherjee 2008 | Never. Superseded by 10.1016/j.jas.2008.01.010 |
| 10.1080/14614103.2016.1164345 | The wrong DOI first logged for Smyth & Evershed 2016 | Never. Superseded by 10.1179/1749631414Y.0000000045 |
| 10.1098/rspb.2014.0819 | Cramp et al. 2014, Finland: a different region in the same year and volume | Out of geographic scope |
| 10.1353/ria.2015.0011 | Smyth & Evershed 2015, *The molecules of meals*, PRIA C 115:27–46 | A different paper. Would need a scope decision |
| 10.1017/S0003598X00095703 | Mukherjee et al. 2007, the *Antiquity* precursor to Mukherjee 2008 | Dropped by decision. It resolves and can be obtained if ever reinstated |

Copley et al. 2005a (*Dairying in antiquity I*, Iron Age, JAS 32:485–503) and 2005b (*II*, Bronze Age, JAS 32:505–521) are excluded by period, not by DOI. They are outside the Neolithic scope.

---

## Repository structure

```
pipeline/
  seed_corpus.py         authoritative seed DOI list and exclusion registry
  common.py              shared schema, thresholds and helpers
  01_tier_a_hammann.py   Tier A parse of the Hammann 2022 source-data deposit
  02_tier_b_extract.py   Tier B LLM-assisted table extraction (Copley 2005c, Smyth & Evershed 2016)
  03_validate.py         provenance, schema, plausibility and author-agreement QA
  04_ingest_db.py        load extracted JSON into PostgreSQL
  05_export.py           write corpus.json, corpus.csv and the frontend copy
schema/
  sample_schema.json     record schema
db/migrations/           PostgreSQL schema and validation views
data/exports/
  corpus.json            canonical dataset (CC-BY-4.0)
  corpus.csv             same records, tabular (CC-BY-4.0)
frontend/
  src/App.jsx            React/Recharts web tool
  public/corpus.json     reshaped dataset copy for the web tool (CC-BY-4.0)
docker-compose.yml       PostgreSQL 16 + PostGIS for local pipeline runs
LICENSE                  MIT (code)
LICENSE-DATA             CC-BY-4.0 (data)
```

`data/raw/` (source PDFs) and `data/processed/` (intermediate extractions) are git-ignored. Paywalled source PDFs are not redistributed.

### Running the web tool

```bash
cd frontend && npm install && npm run dev
```

---

## Citing

Cite the original study for each record you use, as well as this repository. The `source.citation` and `source.doi` fields on each record name its paper.

Suggested repository citation:

> Satoru / DigiShield Labs. *ORA: Organic Residue Archive — harmonised compound-specific δ¹³C dataset from British and Irish Neolithic pottery*. https://github.com/satoru-bio/ORA. Data CC-BY-4.0.

---

## Stack

Python pipeline · PostgreSQL 16 / PostGIS (Docker) · React / Vite / Recharts frontend
