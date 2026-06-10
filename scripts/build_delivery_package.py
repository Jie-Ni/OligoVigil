from __future__ import annotations

import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DESKTOP = Path.home() / "Desktop"
PACKAGE_ROOT = DESKTOP / "NAR_OligoSafetyDB_delivery"

EXCLUDE_NAMES = {
    "server.err.log",
    "server.out.log",
    "__pycache__",
    ".pytest_cache",
}


def should_include(path: Path) -> bool:
    if path.name in EXCLUDE_NAMES:
        return False
    if path.suffix == ".bak":
        return False
    if path.suffix == ".db" and path.name != "oligosafety.db":
        return False
    if path.suffix == ".json" and "data" in path.parts and "generated" in path.parts:
        return False
    if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts):
        return False
    return True


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_file():
        if should_include(src):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        return
    for item in src.iterdir():
        if not should_include(item):
            continue
        copy_tree(item, dst / item.name)


def zip_dir(src: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in src.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(src.parent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=datetime.now().strftime("%Y%m%d_%H%M%S"))
    args = parser.parse_args()

    package_dir = PACKAGE_ROOT / f"OligoVigil_presubmission_release_{args.label}"
    zip_path = PACKAGE_ROOT / f"{package_dir.name}.zip"

    if package_dir.exists() or zip_path.exists():
        raise SystemExit(f"Refusing to overwrite existing package: {package_dir}")

    package_dir.mkdir(parents=True)
    for name in [
        "00_scoping",
        "01_sources",
        "02_design",
        "04_delivery",
        "repo_ready",
    ]:
        copy_tree(PROJECT_ROOT / name, package_dir / name)
    copy_tree(PROJECT_ROOT / "03_ingestion_status.md", package_dir / "03_ingestion_status.md")
    zip_dir(package_dir, zip_path)
    print(f"delivery_package_dir={package_dir}")
    print(f"delivery_package_zip={zip_path}")


if __name__ == "__main__":
    main()
