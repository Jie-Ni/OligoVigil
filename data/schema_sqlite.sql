PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_document (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    pmid TEXT,
    pmcid TEXT,
    doi TEXT,
    title TEXT,
    journal_or_agency TEXT,
    publication_year INTEGER,
    license_status TEXT NOT NULL,
    reuse_category TEXT NOT NULL,
    accessed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS modality (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    in_core_scope INTEGER NOT NULL DEFAULT 1,
    scope_note TEXT
);

CREATE TABLE IF NOT EXISTS molecule (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT,
    modality_id INTEGER NOT NULL,
    target_gene_symbol TEXT,
    disease_context TEXT,
    therapeutic_status TEXT,
    sense_sequence TEXT,
    antisense_sequence TEXT,
    guide_sequence TEXT,
    passenger_sequence TEXT,
    seed_region TEXT,
    backbone_chemistry TEXT,
    sugar_modification TEXT,
    base_modification TEXT,
    conjugate_delivery TEXT,
    sequence_annotation_status TEXT NOT NULL DEFAULT 'needs_curator_sequence_curation',
    modification_annotation_status TEXT NOT NULL DEFAULT 'needs_curator_modification_curation',
    external_ids TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (modality_id) REFERENCES modality(id)
);

CREATE TABLE IF NOT EXISTS assay (
    id INTEGER PRIMARY KEY,
    assay_type TEXT NOT NULL,
    organism TEXT,
    model_system TEXT,
    cell_line_or_tissue TEXT,
    dose_value REAL,
    dose_unit TEXT,
    exposure_time_value REAL,
    exposure_time_unit TEXT,
    replicate_count INTEGER,
    source_document_id INTEGER NOT NULL,
    source_location TEXT,
    FOREIGN KEY (source_document_id) REFERENCES source_document(id)
);

CREATE TABLE IF NOT EXISTS toxicity_endpoint (
    id INTEGER PRIMARY KEY,
    molecule_id INTEGER NOT NULL,
    assay_id INTEGER,
    endpoint_name TEXT NOT NULL,
    endpoint_category TEXT NOT NULL,
    measured_value REAL,
    measured_unit TEXT,
    direction TEXT,
    significance_label TEXT,
    is_observed_experimental INTEGER NOT NULL DEFAULT 1,
    source_document_id INTEGER NOT NULL,
    source_location TEXT,
    evidence_grade TEXT NOT NULL DEFAULT 'ungraded',
    FOREIGN KEY (molecule_id) REFERENCES molecule(id),
    FOREIGN KEY (assay_id) REFERENCES assay(id),
    FOREIGN KEY (source_document_id) REFERENCES source_document(id)
);

CREATE TABLE IF NOT EXISTS offtarget_evidence (
    id INTEGER PRIMARY KEY,
    molecule_id INTEGER NOT NULL,
    assay_id INTEGER,
    offtarget_gene_symbol TEXT,
    offtarget_transcript_id TEXT,
    evidence_type TEXT NOT NULL,
    measured_effect REAL,
    effect_unit TEXT,
    match_type TEXT,
    seed_match_length INTEGER,
    is_observed_experimental INTEGER NOT NULL DEFAULT 1,
    is_computational_prediction INTEGER NOT NULL DEFAULT 0,
    source_document_id INTEGER NOT NULL,
    source_location TEXT,
    evidence_grade TEXT NOT NULL DEFAULT 'ungraded',
    FOREIGN KEY (molecule_id) REFERENCES molecule(id),
    FOREIGN KEY (assay_id) REFERENCES assay(id),
    FOREIGN KEY (source_document_id) REFERENCES source_document(id)
);

CREATE TABLE IF NOT EXISTS curation_audit (
    id INTEGER PRIMARY KEY,
    entity_table TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    extraction_method TEXT NOT NULL,
    extractor_model_or_script TEXT,
    validation_status TEXT NOT NULL,
    curator_decision TEXT NOT NULL,
    curator_id TEXT,
    audit_note TEXT,
    audited_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS benchmark_split (
    id INTEGER PRIMARY KEY,
    task_name TEXT NOT NULL,
    split_name TEXT NOT NULL,
    entity_table TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    split_strategy TEXT NOT NULL,
    leakage_group TEXT,
    version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS curation_queue (
    id INTEGER PRIMARY KEY,
    source_document_id INTEGER NOT NULL,
    pmid TEXT,
    doi TEXT,
    source_title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    candidate_modality TEXT NOT NULL,
    evidence_domain TEXT NOT NULL,
    extraction_target TEXT NOT NULL,
    suggested_evidence_grade TEXT NOT NULL,
    priority TEXT NOT NULL,
    queue_status TEXT NOT NULL,
    curator_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_document_id) REFERENCES source_document(id)
);

CREATE TABLE IF NOT EXISTS curation_candidate (
    id INTEGER PRIMARY KEY,
    queue_id INTEGER NOT NULL,
    source_document_id INTEGER NOT NULL,
    pmid TEXT,
    doi TEXT,
    evidence_domain TEXT NOT NULL,
    candidate_modality TEXT NOT NULL,
    source_location TEXT NOT NULL,
    matched_terms TEXT,
    candidate_signal TEXT NOT NULL,
    suggested_evidence_grade TEXT NOT NULL,
    confidence_label TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    curator_decision TEXT NOT NULL,
    redistribution_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (queue_id) REFERENCES curation_queue(id),
    FOREIGN KEY (source_document_id) REFERENCES source_document(id)
);
