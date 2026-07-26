#!/usr/bin/env python3
"""Rewrite Quarto sitemap entries to their clean canonical URLs."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET


SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
URL_TAG = f"{{{SITEMAP_NAMESPACE}}}url"
LOC_TAG = f"{{{SITEMAP_NAMESPACE}}}loc"


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


def canonicalise_sitemap(sitemap_path: Path) -> tuple[int, int]:
    """Canonicalise URLs in place and remove any duplicates created by rewriting."""
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    seen: set[str] = set()
    rewritten = 0
    removed = 0

    for url_element in list(root.findall(URL_TAG)):
        loc_element = url_element.find(LOC_TAG)
        if loc_element is None or not loc_element.text:
            continue

        original = loc_element.text.strip()
        canonical = canonicalise_url(original)
        if canonical in seen:
            root.remove(url_element)
            removed += 1
            continue

        seen.add(canonical)
        if canonical != original:
            loc_element.text = canonical
            rewritten += 1

    ET.register_namespace("", SITEMAP_NAMESPACE)
    ET.indent(tree, space="  ")
    tree.write(sitemap_path, encoding="UTF-8", xml_declaration=True)
    return rewritten, removed


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
    rewritten, removed = canonicalise_sitemap(args.sitemap)
    print(
        f"Canonicalised {rewritten} sitemap URL(s)"
        f" and removed {removed} duplicate(s)."
    )


if __name__ == "__main__":
    main()
