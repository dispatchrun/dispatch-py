# Adapted from https://github.com/mkdocstrings/griffe/blob/2359a02aef3cdc1776608a9e507c0096285e1d75/scripts/gen_ref_nav.py (ISC License)

import fnmatch
from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()
mod_symbol = '<code class="doc-symbol doc-symbol-nav doc-symbol-module"></code>'

exclude = {"buf/*", "*/proto/*", "*_pb2*", "dispatch/sdk/*"}
src = Path(__file__).parent.parent / "src"

for path in sorted(src.rglob("*.py")):
    if any(fnmatch.fnmatch(str(path.relative_to(src)), pat) for pat in exclude):
        continue
    module_path = path.relative_to(src).with_suffix("")
    doc_path = path.relative_to(src).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    elif parts[-1].startswith("_"):
        continue

    nav_parts = [f"{mod_symbol} {part}" for part in parts]
    nav[tuple(nav_parts)] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"::: {ident}")

    mkdocs_gen_files.set_edit_path(full_doc_path, ".." / path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
