#!/usr/bin/env python3
"""Régénère custom_components/local_tahoma depuis l'intégration Overkiz amont.

Usage :
    python3 sync.py                    # récupère la branche dev de home-assistant/core
    python3 sync.py --ref 2026.10.2    # un tag/une branche précis (recommandé : la
                                       # version de votre Home Assistant)
    python3 sync.py --source overkiz   # utilise un dossier local au lieu de git

Étapes : (1) l'amont est copié tel quel dans upstream/overkiz (un `git diff`
montre ce qui a changé chez Home Assistant), (2) transforms.py est appliqué,
(3) le résultat est écrit dans custom_components/local_tahoma.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import transforms as t

ROOT = Path(__file__).parent
UPSTREAM_DIR = ROOT / "upstream" / "overkiz"
TARGET_DIR = ROOT / "custom_components" / t.NEW_DOMAIN
UPSTREAM_REPO = "https://github.com/home-assistant/core.git"
UPSTREAM_PATH = "homeassistant/components/overkiz"
IGNORED = {"__pycache__", ".DS_Store"}


def fetch_upstream(ref: str, dest: Path) -> str:
    """Clone partiel du seul dossier overkiz ; retourne le commit récupéré."""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "core"
        git = ["git", "-C", str(clone)]
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none",
             "--sparse", "--branch", ref, UPSTREAM_REPO, str(clone)],
            check=True,
        )
        subprocess.run([*git, "sparse-checkout", "set", UPSTREAM_PATH], check=True)
        commit = subprocess.run(
            [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
        copy_tree(clone / UPSTREAM_PATH, dest)
    return commit


def copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*IGNORED))


def build(upstream: Path, target: Path) -> list[str]:
    warnings: list[str] = []
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(upstream, target, ignore=shutil.ignore_patterns(*IGNORED))

    for excluded in t.EXCLUDED:
        path = target / excluded
        if path.exists():
            path.unlink()

    for name, transform in t.TEXT_TRANSFORMS.items():
        path = target / name
        if not path.exists():
            raise t.TransformError(f"{name}: fichier absent de l'amont")
        path.write_text(transform(path.read_text()))

    strings_path = upstream / t.STRINGS
    strings_text = t.strings_json(strings_path.read_text())
    resolved = t.resolve_references(json.loads(strings_text), warnings.append)
    translations = target / "translations"
    translations.mkdir(exist_ok=True)
    (translations / "en.json").write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False) + "\n"
    )

    # Images de l'intégration (brand/icon.png, icon@2x.png…) : maintenues à la main.
    brand = ROOT / "brand"
    if brand.is_dir():
        shutil.copytree(brand, target / "brand", ignore=shutil.ignore_patterns(*IGNORED))

    # Overrides de traduction maintenus à la main (ex. fr.json) : copiés tels quels.
    overrides = ROOT / "translations_overrides"
    if overrides.is_dir():
        for file in overrides.glob("*.json"):
            shutil.copy(file, translations / file.name)

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ref", default="dev", help="tag ou branche de home-assistant/core")
    parser.add_argument("--source", type=Path, help="dossier overkiz local à utiliser")
    args = parser.parse_args()

    if args.source:
        copy_tree(args.source, UPSTREAM_DIR)
        origin = f"dossier local {args.source}"
    else:
        commit = fetch_upstream(args.ref, UPSTREAM_DIR)
        origin = f"home-assistant/core@{args.ref} ({commit[:10]})"
    (UPSTREAM_DIR.parent / "UPSTREAM_REF").write_text(origin + "\n")

    try:
        warnings = build(UPSTREAM_DIR, TARGET_DIR)
    except t.TransformError as err:
        print(f"ÉCHEC : l'amont a divergé de ce que transforms.py attend.\n{err}",
              file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"avertissement : {warning}", file=sys.stderr)
    print(f"OK : {TARGET_DIR.relative_to(ROOT)} généré depuis {origin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
