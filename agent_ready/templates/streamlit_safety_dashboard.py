from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st


BASE_URL = os.environ.get("OLIGOVIGIL_BASE_URL", "https://oligovigil.pages.dev").rstrip("/")


def get_json(path: str, params: dict[str, str] | None = None) -> object:
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="OligoVigil safety dashboard", layout="wide")
st.title("OligoVigil safety evidence dashboard")

query = st.text_input("Safety or off-target query", "GalNAc hepatotoxicity")
domain = st.selectbox("Evidence domain", ["", "toxicity", "offtarget"], format_func=lambda value: value or "all")

if st.button("Search verified evidence", type="primary"):
    records = get_json("/api/evidence_records", {"q": query, "domain": domain, "limit": "100"})
    frame = pd.DataFrame(records)
    st.caption("Release evidence only. Candidate records are not shown here.")
    if frame.empty:
        st.info("No curator-verified release records matched this query.")
    else:
        columns = [
            "evidence_domain",
            "evidence_id",
            "canonical_name",
            "evidence_grade",
            "category",
            "evidence_label",
            "source_location",
            "pmid",
            "doi",
        ]
        st.dataframe(frame[[column for column in columns if column in frame.columns]], use_container_width=True)

st.divider()
triage = st.expander("Source-grounded triage packet")
with triage:
    sequence = st.text_input("Sequence", "AUGCUACUGACUGA")
    target = st.text_input("Target", "PCSK9")
    modification = st.text_input("Modification", "GalNAc")
    endpoint = st.text_input("Endpoint", "hepatic")
    if st.button("Generate triage report"):
        report = get_json(
            "/api/safety_triage",
            {
                "sequence": sequence,
                "target": target,
                "modification": modification,
                "delivery": modification,
                "endpoint": endpoint,
                "species": "human",
            },
        )
        st.json(report)
