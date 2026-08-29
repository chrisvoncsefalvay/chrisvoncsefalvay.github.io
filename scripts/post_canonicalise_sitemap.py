#!/usr/bin/env python3
"""Give Quarto sitemap entries canonical URLs and content-level dates."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
URL_TAG = f"{{{SITEMAP_NAMESPACE}}}url"
LOC_TAG = f"{{{SITEMAP_NAMESPACE}}}loc"
LASTMOD_TAG = f"{{{SITEMAP_NAMESPACE}}}lastmod"
SOURCE_SUFFIXES = (".qmd", ".md", ".ipynb")


class CanonicalLinkParser(HTMLParser):
    """Extract the first canonical URL from a rendered HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.canonical_url: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if self.canonical_url is not None or tag.lower() != "link":
            return

        attributes = {name.lower(): value for name, value in attrs}
        relationships = (attributes.get("rel") or "").lower().split()
        href = attributes.get("href")
        if "canonical" in relationships and href:
            self.canonical_url = href.strip()


def canonicalise_url(url: str) -> str:
    """Replace a terminal index.html with the equivalent slash URL."""
    parsed = urlsplit(url)
    if parsed.path == "/index.html":
        path = "/"
    elif parsed.path.endswith("/index.html"):
        path = parsed.path[: -len("index.html")]
    else:
        path = parsed.path
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def output_path_for_url(url: str, site_root: Path) -> Path | None:
    """Resolve a site URL to its rendered file without leaving the site root."""
    path = unquote(urlsplit(url).path).lstrip("/")
    relative = Path(path)
    if ".." in relative.parts:
        return None
    if not path or path.endswith("/"):
        relative = relative / "index.html"
    return site_root / relative


def source_path_for_output(
    output_path: Path,
    site_root: Path,
    project_root: Path,
) -> Path | None:
    """Find the Quarto source corresponding to a rendered HTML path."""
    try:
        relative = output_path.relative_to(site_root)
    except ValueError:
        return None

    if relative.name == "index.html":
        source_stem = relative.parent / "index"
    elif relative.suffix == ".html":
        source_stem = relative.with_suffix("")
    else:
        return None

    for suffix in SOURCE_SUFFIXES:
        candidate = project_root / source_stem.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def is_auxiliary_notebook(source_path: Path) -> bool:
    """Return whether a notebook is an implementation companion to an index page."""
    if source_path.suffix != ".ipynb":
        return False
    return any(
        (source_path.parent / f"index{suffix}").is_file()
        for suffix in (".qmd", ".md")
    )


def _front_matter_from_text(text: str) -> str | None:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    return None


def source_front_matter(source_path: Path) -> str | None:
    """Read YAML front matter from a text document or notebook markdown cell."""
    if source_path.suffix in {".qmd", ".md"}:
        return _front_matter_from_text(source_path.read_text(encoding="utf-8"))
    if source_path.suffix != ".ipynb":
        return None

    notebook = json.loads(source_path.read_text(encoding="utf-8"))
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else str(source)
        front_matter = _front_matter_from_text(text)
        if front_matter is not None:
            return front_matter
    return None


def _normalise_iso_date(value: str, source_path: Path) -> str:
    candidate = value.strip()
    if " #" in candidate:
        candidate = candidate.split(" #", 1)[0].rstrip()
    if (
        len(candidate) >= 2
        and candidate[0] == candidate[-1]
        and candidate[0] in "\"'"
    ):
        candidate = candidate[1:-1].strip()

    try:
        if "T" in candidate or " " in candidate:
            datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        else:
            date.fromisoformat(candidate)
    except ValueError as error:
        raise ValueError(
            f"{source_path}: sitemap date must use ISO 8601, got {candidate!r}"
        ) from error
    return candidate


def source_lastmod(source_path: Path) -> str | None:
    """Use explicit modification/publication metadata, never checkout time."""
    front_matter = source_front_matter(source_path)
    if not front_matter:
        return None

    for field in ("date-modified", "date"):
        match = re.search(
            rf"(?m)^{re.escape(field)}\s*:\s*(.*?)\s*$",
            front_matter,
        )
        if match:
            return _normalise_iso_date(match.group(1), source_path)
    return None


def canonical_url_from_output(output_path: Path) -> str | None:
    """Read the canonical URL emitted by the rendered page."""
    if not output_path.is_file() or output_path.suffix != ".html":
        return None
    parser = CanonicalLinkParser()
    parser.feed(output_path.read_text(encoding="utf-8", errors="replace"))
    return parser.canonical_url


def canonicalise_sitemap(
    sitemap_path: Path,
    project_root: Path | None = None,
) -> tuple[int, int, int, int]:
    """Canonicalise URLs and replace build timestamps with source metadata."""
    project_root = (project_root or Path.cwd()).resolve()
    site_root = sitemap_path.parent.resolve()
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    seen: set[str] = set()
    rewritten = 0
    removed = 0
    updated_lastmod = 0
    removed_lastmod = 0

    for url_element in list(root.findall(URL_TAG)):
        loc_element = url_element.find(LOC_TAG)
        if loc_element is None or not loc_element.text:
            continue

        original = loc_element.text.strip()
        output_path = output_path_for_url(original, site_root)
        original_source_path = (
            source_path_for_output(output_path, site_root, project_root)
            if output_path is not None
            else None
        )

        if original_source_path is not None and is_auxiliary_notebook(
            original_source_path
        ):
            root.remove(url_element)
            removed += 1
            continue

        if (
            output_path is None
            or output_path.suffix != ".html"
            or not output_path.is_file()
        ):
            raise ValueError(f"Sitemap URL has no rendered page: {original}")

        canonical = canonical_url_from_output(output_path)
        if canonical is None:
            raise ValueError(f"Rendered page has no canonical URL: {original}")

        original_parts = urlsplit(original)
        canonical_parts = urlsplit(canonical)
        if (
            canonical_parts.scheme != original_parts.scheme
            or canonical_parts.netloc != original_parts.netloc
        ):
            raise ValueError(
                f"Canonical URL for {original} leaves the sitemap origin: {canonical}"
            )

        canonical_output = output_path_for_url(canonical, site_root)
        if (
            canonical_output is None
            or canonical_output.suffix != ".html"
            or not canonical_output.is_file()
        ):
            raise ValueError(
                f"Canonical URL for {original} has no rendered target: {canonical}"
            )
        source_path = source_path_for_output(
            canonical_output,
            site_root,
            project_root,
        )

        if canonical in seen:
            root.remove(url_element)
            removed += 1
            continue

        seen.add(canonical)
        if canonical != original:
            loc_element.text = canonical
            rewritten += 1

        lastmod_element = url_element.find(LASTMOD_TAG)
        lastmod = source_lastmod(source_path) if source_path is not None else None
        if lastmod is not None:
            if lastmod_element is None:
                lastmod_element = ET.SubElement(url_element, LASTMOD_TAG)
            if (lastmod_element.text or "").strip() != lastmod:
                lastmod_element.text = lastmod
                updated_lastmod += 1
        elif lastmod_element is not None:
            url_element.remove(lastmod_element)
            removed_lastmod += 1

    ET.register_namespace("", SITEMAP_NAMESPACE)
    ET.indent(tree, space="  ")
    tree.write(sitemap_path, encoding="UTF-8", xml_declaration=True)
    return rewritten, removed, updated_lastmod, removed_lastmod


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "sitemap",
        nargs="?",
        type=Path,
        default=Path("_site/sitemap.xml"),
        help="Path to the generated sitemap.xml",
    )
    args = parser.parse_args()
    rewritten, removed, updated_lastmod, removed_lastmod = canonicalise_sitemap(
        args.sitemap
    )
    print(
        f"Canonicalised {rewritten} sitemap URL(s)"
        f", removed {removed} non-canonical or duplicate URL(s),"
        f" updated {updated_lastmod} content date(s),"
        f" and removed {removed_lastmod} build timestamp(s)."
    )


if __name__ == "__main__":
    main()
