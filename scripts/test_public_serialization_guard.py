from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("oligovigil_server", ROOT / "app" / "server.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load app/server.py")
SERVER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER)


def fake_handler(path: str = "/") -> tuple[object, list[int], dict[str, str]]:
    handler = object.__new__(SERVER.Handler)
    statuses: list[int] = []
    headers: dict[str, str] = {}
    handler.path = path
    handler.send_response = statuses.append
    handler.send_header = headers.__setitem__
    handler.end_headers = lambda: None
    handler.wfile = io.BytesIO()
    return handler, statuses, headers


class PublicSerializationGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "id": 17,
            "decision": "accept",
            "grade": "A",
            "source_location": "Results; Figure 2",
            "grounding_quote_hash": "a" * 64,
            "raw_quote_included": False,
            "audit_reason": "Derived reason",
            "auditNote": json.dumps(
                {
                    "reason": "Derived reason",
                    "groundingQuote": "verbatim source text",
                    "note_sha256": "b" * 64,
                    "quote_sha256": "c" * 64,
                    "note_withheld": True,
                    "source_pmid": "12345",
                }
            ),
            "nested": {
                "llm_grounding_quote": "verbatim source text",
                "source_excerpt": "verbatim source text",
                "safe_hash": "d" * 64,
            },
            "items": [{"quoted_passage": "verbatim source text", "entity_id": 9}],
            "single_curator_note": "Safe release-level validation summary.",
            "count": 2,
            "score": 0.75,
            "flag": True,
            "missing": None,
        }

    def test_recursive_payload_guard_and_safe_metadata(self) -> None:
        sanitized = SERVER.sanitize_public_payload(self.payload)
        self.assertNotIn("auditNote", sanitized)
        self.assertNotIn("llm_grounding_quote", sanitized["nested"])
        self.assertNotIn("source_excerpt", sanitized["nested"])
        self.assertNotIn("quoted_passage", sanitized["items"][0])
        self.assertEqual(sanitized["id"], 17)
        self.assertEqual(sanitized["decision"], "accept")
        self.assertEqual(sanitized["grade"], "A")
        self.assertEqual(sanitized["source_location"], "Results; Figure 2")
        self.assertEqual(sanitized["grounding_quote_hash"], "a" * 64)
        self.assertFalse(sanitized["raw_quote_included"])
        self.assertEqual(sanitized["audit_reason"], "Derived reason")
        self.assertEqual(sanitized["single_curator_note"], self.payload["single_curator_note"])
        self.assertEqual(sanitized["count"], 2)
        self.assertEqual(sanitized["score"], 0.75)
        self.assertTrue(sanitized["flag"])
        self.assertIsNone(sanitized["missing"])
        metadata = sanitized["audit_note_meta"]
        self.assertEqual(metadata["note_sha256"], "b" * 64)
        self.assertEqual(metadata["quote_sha256"], "c" * 64)
        self.assertEqual(metadata["source_pmid"], "12345")
        self.assertNotIn("reason", metadata)
        self.assertNotIn("groundingQuote", metadata)

    def test_stringified_json_guard_preserves_string_type(self) -> None:
        external_ids = json.dumps(
            {
                "release_row_id": 59,
                "source_pmid": "40672232",
                "evidence_quote": "verbatim source text",
            }
        )
        sanitized = SERVER.sanitize_public_payload({"external_ids": external_ids})
        self.assertIsInstance(sanitized["external_ids"], str)
        decoded = json.loads(sanitized["external_ids"])
        self.assertEqual(decoded["release_row_id"], 59)
        self.assertEqual(decoded["source_pmid"], "40672232")
        self.assertNotIn("evidence_quote", decoded)
        self.assertEqual(
            decoded["evidence_quote_sha256"],
            hashlib.sha256(b"verbatim source text").hexdigest(),
        )
        self.assertTrue(decoded["evidence_quote_withheld"])

    def test_json_response_boundary_for_json_media_types(self) -> None:
        for media_type in (
            "application/json; charset=utf-8",
            "application/ld+json; charset=utf-8",
            "application/problem+json; charset=utf-8",
        ):
            with self.subTest(media_type=media_type):
                handler, statuses, _ = fake_handler()
                handler.send_payload(200, media_type, SERVER.json_bytes(self.payload))
                result = json.loads(handler.wfile.getvalue())
                self.assertEqual(statuses, [200])
                self.assertNotIn("auditNote", result)
                self.assertNotIn("llm_grounding_quote", result["nested"])
                self.assertEqual(result["grounding_quote_hash"], "a" * 64)

    def test_json_guard_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            SERVER.sanitize_public_json_bytes(b"{not-json")

    def test_csv_guard_handles_headers_and_stringified_json(self) -> None:
        external_ids = json.dumps({"release_row_id": 59, "evidence_quote": "verbatim source text"})
        body = SERVER.dicts_to_csv_bytes(
            [{**self.payload, "external_ids": external_ids}],
        )
        reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
        row = next(reader)
        self.assertNotIn("auditNote", reader.fieldnames)
        self.assertIn("audit_note_meta", reader.fieldnames)
        self.assertIn("grounding_quote_hash", reader.fieldnames)
        self.assertEqual(row["id"], "17")
        self.assertEqual(row["grade"], "A")
        decoded = json.loads(row["external_ids"])
        self.assertNotIn("evidence_quote", decoded)
        self.assertTrue(decoded["evidence_quote_withheld"])

    def test_file_csv_get_head_and_manifest_are_identical(self) -> None:
        raw = b"id,original_audit_note,source_location\n1,raw text,Figure 1\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "canary.csv"
            path.write_bytes(raw)
            canary_endpoint = "/api/manifest/canary.csv"
            original = SERVER.MANIFEST_DOWNLOADS.get("canary.csv")
            endpoint_was_public = canary_endpoint in SERVER.PUBLIC_API_ENDPOINTS
            original_file_cache = SERVER._PUBLIC_CSV_FILE_CACHE
            original_body_cache = SERVER._PUBLIC_CSV_BODY_CACHE
            original_uncached_sanitizer = SERVER._sanitize_public_csv_bytes_uncached
            sanitizer_calls = 0

            def counting_uncached_sanitizer(body: bytes) -> bytes:
                nonlocal sanitizer_calls
                sanitizer_calls += 1
                return original_uncached_sanitizer(body)

            SERVER.MANIFEST_DOWNLOADS["canary.csv"] = path
            SERVER.PUBLIC_API_ENDPOINTS.add(canary_endpoint)
            SERVER._PUBLIC_CSV_FILE_CACHE = {}
            SERVER._PUBLIC_CSV_BODY_CACHE = {}
            SERVER._sanitize_public_csv_bytes_uncached = counting_uncached_sanitizer
            try:
                get_handler, get_statuses, get_headers = fake_handler("/api/manifest/canary.csv")
                get_handler.do_GET()
                head_handler, head_statuses, head_headers = fake_handler("/api/manifest/canary.csv")
                head_handler.do_HEAD()
                entry = SERVER.download_entry(
                    {
                        "category": "test",
                        "filename": "canary.csv",
                        "url": "/api/manifest/canary.csv",
                        "kind": "manifest_file",
                        "manifest": "canary.csv",
                        "schema": "test",
                        "purpose": "test",
                        "recommended_use": "test",
                    }
                )
            finally:
                if original is None:
                    del SERVER.MANIFEST_DOWNLOADS["canary.csv"]
                else:
                    SERVER.MANIFEST_DOWNLOADS["canary.csv"] = original
                if not endpoint_was_public:
                    SERVER.PUBLIC_API_ENDPOINTS.discard(canary_endpoint)
                SERVER._PUBLIC_CSV_FILE_CACHE = original_file_cache
                SERVER._PUBLIC_CSV_BODY_CACHE = original_body_cache
                SERVER._sanitize_public_csv_bytes_uncached = original_uncached_sanitizer
            body = get_handler.wfile.getvalue()
            self.assertEqual(get_statuses, [200])
            self.assertEqual(head_statuses, [200])
            self.assertEqual(int(get_headers["Content-Length"]), len(body))
            self.assertEqual(int(head_headers["Content-Length"]), len(body))
            self.assertEqual(entry["bytes"], len(body))
            self.assertEqual(entry["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(sanitizer_calls, 1)
            header = next(csv.reader(io.StringIO(body.decode("utf-8"))))
            self.assertNotIn("original_audit_note", header)
            self.assertIn("original_audit_note_meta", header)

    def test_public_csv_cache_revalidates_same_size_source_change(self) -> None:
        first_raw = b"id,original_audit_note\n1,raw text\n"
        second_raw = b"id,original_audit_note\n1,new text\n"
        self.assertEqual(len(first_raw), len(second_raw))
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "canary.csv"
            original_file_cache = SERVER._PUBLIC_CSV_FILE_CACHE
            original_body_cache = SERVER._PUBLIC_CSV_BODY_CACHE
            original_uncached_sanitizer = SERVER._sanitize_public_csv_bytes_uncached
            sanitizer_calls = 0

            def counting_uncached_sanitizer(body: bytes) -> bytes:
                nonlocal sanitizer_calls
                sanitizer_calls += 1
                return original_uncached_sanitizer(body)

            SERVER._PUBLIC_CSV_FILE_CACHE = {}
            SERVER._PUBLIC_CSV_BODY_CACHE = {}
            SERVER._sanitize_public_csv_bytes_uncached = counting_uncached_sanitizer
            try:
                path.write_bytes(first_raw)
                first = SERVER.public_csv_file_bytes(path)
                path.write_bytes(second_raw)
                second = SERVER.public_csv_file_bytes(path)
            finally:
                SERVER._PUBLIC_CSV_FILE_CACHE = original_file_cache
                SERVER._PUBLIC_CSV_BODY_CACHE = original_body_cache
                SERVER._sanitize_public_csv_bytes_uncached = original_uncached_sanitizer
            self.assertEqual(sanitizer_calls, 2)
            self.assertNotEqual(first, second)
            for body in (first, second):
                header = next(csv.reader(io.StringIO(body.decode("utf-8"))))
                self.assertNotIn("original_audit_note", header)
                self.assertIn("original_audit_note_meta", header)

    def test_query_oracles_do_not_search_hidden_text(self) -> None:
        queries: list[tuple[str, tuple[object, ...]]] = []
        original_rows = SERVER.rows

        def capture_rows(
            query: str,
            params: tuple[object, ...] = (),
        ) -> list[dict[str, object]]:
            queries.append((query, params))
            return []

        SERVER.rows = capture_rows
        try:
            SERVER.api_audit({"q": ["canary"]})
            SERVER.api_molecules({"q": ["canary"]})
        finally:
            SERVER.rows = original_rows
        audit_sql = queries[0][0].lower()
        molecule_sql = queries[1][0].lower()
        self.assertNotIn("audit.audit_note like", audit_sql)
        self.assertNotIn("molecule.external_ids like", molecule_sql)

    def test_dynamic_download_manifest_declares_data_release(self) -> None:
        original_catalog = SERVER.DOWNLOAD_CATALOG
        original_cache = SERVER._DOWNLOAD_MANIFEST_CACHE
        SERVER.DOWNLOAD_CATALOG = []
        SERVER._DOWNLOAD_MANIFEST_CACHE = None
        try:
            manifest = SERVER.api_download_manifest()
        finally:
            SERVER.DOWNLOAD_CATALOG = original_catalog
            SERVER._DOWNLOAD_MANIFEST_CACHE = original_cache
        self.assertEqual(manifest["data_release_version"], "1.0.2")

    def test_public_bundle_get_is_read_only_and_manifest_locked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "all_tables.zip"
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("molecule.csv", 'id,external_ids\n1,{"pmid":"123"}\n')
            bundle = bundle_path.read_bytes()
            manifest_path = directory / "download_manifest"
            manifest_path.write_text(
                json.dumps(
                    {
                        "data_release_version": "1.0.2",
                        "files": [
                            {
                                "filename": "all_tables.zip",
                                "bytes": len(bundle),
                                "sha256": hashlib.sha256(bundle).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            original_bundle_path = SERVER.ALL_TABLES_ZIP_PATH
            original_manifest_path = SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH
            original_builder = SERVER.build_all_tables_zip_bytes
            original_validator = SERVER.validate_public_zip_payload
            original_validation_cache = SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE
            validation_scans = 0

            def counting_validator(body: bytes) -> None:
                nonlocal validation_scans
                validation_scans += 1
                original_validator(body)

            SERVER.ALL_TABLES_ZIP_PATH = bundle_path
            SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = manifest_path
            SERVER.build_all_tables_zip_bytes = lambda: self.fail("request rebuilt bundle")
            SERVER.validate_public_zip_payload = counting_validator
            SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = None
            before = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
            try:
                self.assertEqual(SERVER.all_tables_zip_bytes(), bundle)
                first_handler, first_statuses, _ = fake_handler("/api/download/all_tables.zip")
                first_handler.do_GET()
                second_handler, second_statuses, _ = fake_handler("/api/download/all_tables.zip")
                second_handler.do_GET()
            finally:
                SERVER.ALL_TABLES_ZIP_PATH = original_bundle_path
                SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = original_manifest_path
                SERVER.build_all_tables_zip_bytes = original_builder
                SERVER.validate_public_zip_payload = original_validator
                SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = original_validation_cache
            after = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
            self.assertEqual(first_statuses, [200])
            self.assertEqual(second_statuses, [200])
            self.assertEqual(first_handler.wfile.getvalue(), bundle)
            self.assertEqual(second_handler.wfile.getvalue(), bundle)
            self.assertEqual(validation_scans, 1)
            self.assertEqual(before, after)
            self.assertEqual(before, json.loads(manifest_path.read_text())["files"][0]["sha256"])

    def test_cached_public_bundle_rejects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "all_tables.zip"
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("molecule.csv", "id,name\n1,safe\n")
            bundle = bundle_path.read_bytes()
            manifest_path = directory / "download_manifest"
            manifest_path.write_text(
                json.dumps(
                    {
                        "data_release_version": "1.0.2",
                        "files": [
                            {
                                "filename": "all_tables.zip",
                                "bytes": len(bundle),
                                "sha256": hashlib.sha256(bundle).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            original_bundle_path = SERVER.ALL_TABLES_ZIP_PATH
            original_manifest_path = SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH
            original_validator = SERVER.validate_public_zip_payload
            original_validation_cache = SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE
            validation_scans = 0

            def counting_validator(body: bytes) -> None:
                nonlocal validation_scans
                validation_scans += 1
                original_validator(body)

            SERVER.ALL_TABLES_ZIP_PATH = bundle_path
            SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = manifest_path
            SERVER.validate_public_zip_payload = counting_validator
            SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = None
            try:
                self.assertEqual(SERVER.all_tables_zip_bytes(), bundle)
                bundle_path.write_bytes(bundle + b"tamper")
                tampered_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
                handler, statuses, _ = fake_handler("/api/download/all_tables.zip")
                handler.do_GET()
                after = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
            finally:
                SERVER.ALL_TABLES_ZIP_PATH = original_bundle_path
                SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = original_manifest_path
                SERVER.validate_public_zip_payload = original_validator
                SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = original_validation_cache
            self.assertEqual(statuses, [503])
            self.assertEqual(validation_scans, 1)
            self.assertEqual(tampered_hash, after)
            error = json.loads(handler.wfile.getvalue())
            self.assertEqual(error["error"], "public_release_artifact_unavailable")

    def test_public_bundle_missing_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "all_tables.zip"
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("molecule.csv", "id,name\n1,safe\n")
            original_bundle_path = SERVER.ALL_TABLES_ZIP_PATH
            original_manifest_path = SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH
            original_validation_cache = SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE
            SERVER.ALL_TABLES_ZIP_PATH = bundle_path
            SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = directory / "missing_manifest"
            SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = None
            before = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
            try:
                handler, statuses, _ = fake_handler("/api/download/all_tables.zip")
                handler.do_GET()
            finally:
                SERVER.ALL_TABLES_ZIP_PATH = original_bundle_path
                SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = original_manifest_path
                SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = original_validation_cache
            self.assertEqual(statuses, [503])
            self.assertEqual(before, hashlib.sha256(bundle_path.read_bytes()).hexdigest())
            error = json.loads(handler.wfile.getvalue())
            self.assertEqual(error["error"], "public_release_artifact_unavailable")

    def test_public_bundle_rejects_embedded_quote_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            bundle_path = directory / "all_tables.zip"
            external_ids = json.dumps({"id": 1, "evidence_quote": "raw source text"})
            handle = io.StringIO()
            writer = csv.DictWriter(handle, fieldnames=["id", "external_ids"])
            writer.writeheader()
            writer.writerow({"id": 1, "external_ids": external_ids})
            with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("molecule.csv", handle.getvalue())
            bundle = bundle_path.read_bytes()
            manifest_path = directory / "download_manifest"
            manifest_path.write_text(
                json.dumps(
                    {
                        "data_release_version": "1.0.2",
                        "files": [
                            {
                                "filename": "all_tables.zip",
                                "bytes": len(bundle),
                                "sha256": hashlib.sha256(bundle).hexdigest(),
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            original_bundle_path = SERVER.ALL_TABLES_ZIP_PATH
            original_manifest_path = SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH
            original_validation_cache = SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE
            SERVER.ALL_TABLES_ZIP_PATH = bundle_path
            SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = manifest_path
            SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = None
            before = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
            try:
                handler, statuses, _ = fake_handler("/api/download/all_tables.zip")
                handler.do_GET()
            finally:
                SERVER.ALL_TABLES_ZIP_PATH = original_bundle_path
                SERVER.PUBLIC_DOWNLOAD_MANIFEST_PATH = original_manifest_path
                SERVER._PUBLIC_BUNDLE_VALIDATION_CACHE = original_validation_cache
            self.assertEqual(statuses, [503])
            error = json.loads(handler.wfile.getvalue())
            self.assertEqual(error["error"], "public_release_artifact_unavailable")
            self.assertEqual(before, hashlib.sha256(bundle_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
