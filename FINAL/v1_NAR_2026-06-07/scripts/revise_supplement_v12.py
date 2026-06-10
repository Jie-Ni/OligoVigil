from __future__ import annotations

import re
from pathlib import Path


FINAL = Path("C:/Users/Jie/Desktop/NAR_OligoSafetyDB/repo_ready/FINAL/v1_NAR_2026-06-07")
SUPPLEMENT = FINAL / "supplement"
SOURCE = SUPPLEMENT / "SUPPLEMENTARY_MATERIALS.md"


HEADER = """# Supplementary Materials

**OligoVigil: a curator-verified, source-anchored database of safety and off-target evidence for therapeutic oligonucleotides**

*Jie Ni, Xinting Zhang, Zhuoying Xie, Shan Lu, Yun Liu and Adam Jatowt*

*Current release snapshot: 737 curator-verified evidence records (626 toxicity and 111 off-target) from 660 primary sources. All current release counts were re-verified against `data/oligosafety.db` on 2026-06-10.*

## Supplementary contents

- **S1:** Full curation protocol and grounding gate.
- **S2:** Database schema and candidate-to-release firewall.
- **S3:** Comparator matrix.
- **S4:** Deterministic benchmark baselines.
- **S5:** Proposal-to-human decision provenance.
- **S6:** Backup chain and source-license/reuse classifications.
- **S7:** Excluded and residual-record inventory.
- **S8:** Closest-work feature audit underlying Figure 5.

---"""


S7 = """## S7. Excluded and residual-record inventory

The current release separates removed rows, residual metadata gaps and benchmark exclusions so that users can reproduce each boundary.

### S7.1 Removed computational off-target row

The earlier draft contained one Grade-C computational off-target prediction (`offtarget_evidence.id = 156`). It was removed from the release at the v5 revision and was not re-introduced. Consequently, **all 737 current release rows are observed experimental results**.

### S7.2 Residual placeholder molecules

The collaborator B2 recovery pass resolved 110 of 143 v5 placeholder-linked release rows. The current disclosed residual is **31 release rows** on true placeholder or mixed-modality fallback molecules. Within the frozen 344-row benchmark, **14 rows (4.1%)** remain attached to placeholders, down from 107/344 (31.1%) at v5. Users requiring named-molecule isolation should restrict analysis to the 330-row named-molecule benchmark subset.

### S7.3 Grade A/B release rows outside the frozen benchmark

The release contains **508 Grade A/B records**, of which **344** are assigned to the frozen reference benchmark. The remaining **164 Grade A/B rows** are released as evidence but are not benchmark-assigned because they are singleton leakage groups or await promotion of later expansion batches under the pair-level isolation rule.

### S7.4 Pair-level leakage invariant

The current benchmark enforces pair-level isolation at `(source_document_id, molecule_id)`. The release check:

```sql
SELECT leakage_group, COUNT(DISTINCT split_name)
FROM benchmark_split
GROUP BY leakage_group
HAVING COUNT(DISTINCT split_name) > 1;
```

returns no rows. The benchmark is therefore pair-isolated, while the manuscript explicitly discloses that strict molecule-level isolation requires the 330-row named-molecule subset.

---"""


S8 = """## S8. Closest-work feature audit underlying Figure 5

Figure 5 separates literature overlap from resource capability. Source-PMID sets were available for OligoVigil, CRISPRoffT and siRNAEfficacyDB; all pairwise and triple intersections were zero. Feature support was assessed conservatively as **yes**, **partial**, or **absent/undocumented** from the corresponding paper or inspectable portal.

| Feature | OligoVigil | theRNA | siRNAEfficacyDB | CMsiRNAdb | siRNAmod | CRISPRoffT |
| --- | --- | --- | --- | --- | --- | --- |
| Total curated records | yes | yes | yes | yes | yes | yes |
| Exact source location | yes | yes | partial | partial | partial | partial |
| Curator audit trail | yes | partial | absent | absent | absent | partial |
| Inter-curator check | yes | absent | absent | absent | absent | absent |
| Machine-stage FAR audit | yes | absent | absent | absent | absent | absent |
| Benchmark splits | yes | absent | partial | absent | absent | partial |
| Deterministic baselines | yes | absent | absent | absent | absent | absent |
| Structured assay metadata | partial | partial | yes | partial | absent | partial |
| Per-position chemistry | absent | partial | absent | yes | yes | absent |
| Off-target gene resolution | partial | absent | absent | absent | absent | yes |
| No-login portal | yes | yes | yes | yes | absent | yes |
| API / OpenAPI | yes | partial | partial | partial | absent | partial |
| Agent-readable metadata | yes | absent | absent | absent | absent | partial |
| Bulk download | yes | partial | partial | partial | partial | partial |
| Versioned release | yes | partial | partial | partial | partial | partial |
| Named maintainer | yes | yes | yes | yes | partial | yes |

**Interpretation.** OligoVigil does not lead on absolute scale, per-position chemistry, dose coverage or gene-level off-target resolution. Its distinguishing combination is exact source-localized evidence, a downloadable human audit trail, measured machine-stage error, inter-curator reliability reporting, a frozen reference split and programmatic reuse surfaces.

The source-data tables used to render Figure 5 are:

- `figures/source_data/FIG5_closest_work_audit_v2_sets.csv`
- `figures/source_data/FIG5_closest_work_audit_v2_intersections.csv`
- `figures/source_data/FIG5_closest_work_audit_v2_features.csv`

---"""


def replace_section(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?(?={re.escape(end)})", re.S)
    text, count = pattern.subn(replacement.rstrip() + "\n\n", text, count=1)
    if count != 1:
        raise RuntimeError(f"Could not replace section {start!r}")
    return text


def revise() -> str:
    text = SOURCE.read_text(encoding="utf-8")
    text = re.sub(r"\A# Supplementary Materials.*?\n---", HEADER, text, count=1, flags=re.S)

    replacements = {
        "toxicity_endpoint   (release: 551 rows accepted by 'ni_jie')": "toxicity_endpoint   (release: 626 curator-verified rows)",
        "offtarget_evidence  (release: 107 rows accepted by 'ni_jie')": "offtarget_evidence  (release: 111 curator-verified rows)",
        "molecule         (415 distinct release molecules)": "molecule         (1,012 rows in the current molecule table)",
        "{ 'curator_verified'        -- 658 rows, curator_id='ni_jie'": "{ 'curator_verified'        -- 737 current release rows",
        ", 'curator_rejected'        -- 28,275 rows (mixed source)": ", 'curator_rejected'        -- 28,908 rows (mixed source)",
        ", 'machine_precurated_v1'   -- 1,984 rows (v1 pool, never released)": ", 'machine_precurated_v1'   -- 1,983 historical rows (never released)",
        ", 'recurated_rejected'      -- 1,345 rows, curator_id='ni_jie' (demoted by v2+human)": ", 'recurated_rejected'      -- 1,345 rows (demoted after source review)",
        "curator_id        { 'ni_jie' | 'machine_v1_keyword_classifier' |": "curator_id        { human curator id | 'machine_v1_keyword_classifier' |",
        "**Observed safety endpoints + observed off-target results (657/658 observed; 1 Grade-C computational row, excluded from benchmark)**": "**Observed safety endpoints + observed off-target results (737/737 observed experimental rows)**",
        "**Source-localised: section / figure / table / paragraph captured per release row; 78% (515/658) full-text PMC-anchored; 100% PMID, 99.7% DOI**": "**Source-localised: section / figure / table / paragraph captured per release row; 74.2% (547/737) full-text PMC-anchored; 100% PMID, 99.5% DOI**",
        "Column total **658 = accepted release** and **1,345 = demoted** — these are exactly the headline 658 / 1,345 counts.": "The historical Stage-3 decision table contains **658 human accepts and 1,345 rejects** from the original 2,003-candidate pool. One computational accept was subsequently removed, leaving 657 rows from that pool; later curator-verified expansion rounds added 80 observed rows, producing the current 737-row release.",
        "pre-rebuild snapshot before the 2026-06-07 full database rebuild that produced the canonical 658-record release.": "pre-rebuild snapshot before the 2026-06-07 historical 658-record provisional release.",
        "leaving exactly 658 curator-verified accept audits for 658 release rows.": "leaving one curator-verified accept audit per then-current release row; the current release contains 737 such audits.",
        "both for the 36,245 indexed sources and the 603 release-anchored sources.": "both for the 36,245 indexed sources and the 660 current release-anchored sources.",
        "**Table S6.2b — 603 release-anchored sources (post-R4 deletion of off-target row 156):**": "**Table S6.2b — 660 current release-anchored sources:**",
        "| abstract_metadata_only | derived_annotations_only | 603 |": "| abstract_metadata_only | derived_annotations_only | 660 |",
        "| **total** | | **603** |": "| **total** | | **660** |",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("siRNAmod (RNA Biol 2016)", "siRNAmod (Scientific Reports 2016)")
    text = text.replace(
        "## S6.2 Source-license / reuse-category per-class counts (added at v5 revision per R3)",
        "## S6.2 Source-license / reuse-category per-class counts",
    )
    text = re.sub(
        r"\nEditor's R3 \(decision letter, 2026-06-07\): add per-class counts for the "
        r"source-license reuse classifications, both for the 36,245 indexed sources and "
        r"the 660 current release-anchored sources\.\n",
        "\n",
        text,
        count=1,
    )
    text = text.replace("鈥?", "—").replace("搂", "§").replace("脳", "×")

    if "## S7. Excluded-row inventory" in text:
        text = replace_section(text, "## S7. Excluded-row inventory", "## S6.2 Source-license", S7)
    elif "## S7. Excluded and residual-record inventory" in text:
        text = replace_section(
            text,
            "## S7. Excluded and residual-record inventory",
            "## S8. Closest-work feature audit",
            S7,
        )

    license_start = text.index("## S6.2 Source-license")
    s7_start = text.index("## S7. Excluded and residual-record inventory")
    if license_start > s7_start:
        license_match = re.search(
            r"## S6\.2 Source-license.*?(?=\n---\n\n\*End of Supplementary Materials\.\*)",
            text,
            re.S,
        )
        if not license_match:
            raise RuntimeError("Source-license section not found")
        license_section = license_match.group(0)
        text = text[: license_match.start()] + text[license_match.end() :]
        insert_at = text.index("\n## S7. Excluded and residual-record inventory")
        text = text[:insert_at] + "\n" + license_section + "\n\n---\n" + text[insert_at:]

    if "## S8. Closest-work feature audit" in text:
        text = replace_section(
            text,
            "## S8. Closest-work feature audit",
            "*End of Supplementary Materials.*",
            S8,
        )
    else:
        text = text.replace(
            "\n---\n\n*End of Supplementary Materials.*",
            "\n" + S8 + "\n*End of Supplementary Materials.*",
        )
    for heading in [
        "## S3. Comparator matrix",
        "## S8. Closest-work feature audit underlying Figure 5",
    ]:
        text = text.replace(f"\n\\clearpage\n\n{heading}", f"\n{heading}")
        text = text.replace(f"\n{heading}", f"\n\\clearpage\n\n{heading}", 1)
    return text


def blind(text: str) -> str:
    text = text.replace(
        "*Jie Ni, Xinting Zhang, Zhuoying Xie, Shan Lu, Yun Liu and Adam Jatowt*",
        "*Author information removed for blinded review*",
    )
    text = text.replace("Ni Jie's final verdict", "the curator-of-record's final verdict")
    text = text.replace("The sole human curator (Ni Jie, University of Innsbruck)", "The sole human curator")
    for token in ["ni_jie", "chen_ming", "jie_ni"]:
        text = text.replace(token, "[CURATOR]")
    return text


def main() -> None:
    unblinded = revise()
    blinded = blind(unblinded)
    SOURCE.write_text(unblinded, encoding="utf-8")
    (SUPPLEMENT / "SUPPLEMENTARY_MATERIALS_unblinded.md").write_text(unblinded, encoding="utf-8")
    (SUPPLEMENT / "SUPPLEMENTARY_MATERIALS_blinded.md").write_text(blinded, encoding="utf-8")
    print("Revised and generated blinded/unblinded supplementary materials")


if __name__ == "__main__":
    main()
