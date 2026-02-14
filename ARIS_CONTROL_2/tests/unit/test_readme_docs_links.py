from pathlib import Path


DOC_FILES = [
    "docs/01_MANUAL_OPERATIVO.md",
    "docs/02_UAT_FINAL_CHECKLIST.md",
    "docs/03_RELEASE_RUNBOOK.md",
    "docs/04_OPERACION_DIARIA.md",
]


def test_readme_links_key_docs() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    for doc in DOC_FILES:
        assert doc in readme


def test_docs_exist() -> None:
    for doc in DOC_FILES:
        assert Path(doc).exists()
