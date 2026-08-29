import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from scripts.post_canonicalise_sitemap import (
    LASTMOD_TAG,
    LOC_TAG,
    SITEMAP_NAMESPACE,
    canonicalise_sitemap,
    canonicalise_url,
)


class CanonicaliseUrlTests(unittest.TestCase):
    def test_root_index_becomes_homepage(self) -> None:
        self.assertEqual(
            canonicalise_url("https://example.com/index.html"),
            "https://example.com/",
        )

    def test_nested_index_becomes_slash_url(self) -> None:
        self.assertEqual(
            canonicalise_url("https://example.com/about/index.html"),
            "https://example.com/about/",
        )

    def test_non_index_html_is_unchanged(self) -> None:
        self.assertEqual(
            canonicalise_url("https://example.com/report.html"),
            "https://example.com/report.html",
        )


class CanonicaliseSitemapTests(unittest.TestCase):
    def _write_sitemap(
        self,
        site_root: Path,
        entries: list[tuple[str, str | None]],
    ) -> Path:
        urls = []
        for location, lastmod in entries:
            lastmod_xml = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
            urls.append(f"  <url><loc>{location}</loc>{lastmod_xml}</url>")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="{SITEMAP_NAMESPACE}">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )
        sitemap = site_root / "sitemap.xml"
        sitemap.parent.mkdir(parents=True, exist_ok=True)
        sitemap.write_text(xml, encoding="utf-8")
        return sitemap

    def _write_html(self, site_root: Path, relative: str, canonical: str) -> None:
        output = site_root / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            '<!doctype html><html><head>'
            f'<link rel="canonical" href="{canonical}">'
            "</head><body></body></html>",
            encoding="utf-8",
        )

    def _write_qmd(self, project_root: Path, relative: str, front_matter: str) -> None:
        source = project_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            f"---\n{front_matter}\n---\n\nContent.\n",
            encoding="utf-8",
        )

    def _write_notebook(
        self,
        project_root: Path,
        relative: str,
        front_matter: str | None = None,
    ) -> None:
        cells = []
        if front_matter is not None:
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [f"---\n{front_matter}\n---\n"],
                }
            )
        notebook = {
            "cells": cells,
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        source = project_root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps(notebook), encoding="utf-8")

    def _entries(self, sitemap: Path) -> list[tuple[str, str | None]]:
        tree = ET.parse(sitemap)
        return [
            (
                url.find(LOC_TAG).text,
                url.find(LASTMOD_TAG).text
                if url.find(LASTMOD_TAG) is not None
                else None,
            )
            for url in tree.getroot()
        ]

    def test_rewrites_and_deduplicates_generated_sitemap(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            sitemap = self._write_sitemap(
                site_root,
                [
                    ("https://example.com/index.html", None),
                    ("https://example.com/about/index.html", None),
                    ("https://example.com/about/", None),
                ],
            )
            self._write_html(
                site_root,
                "index.html",
                "https://example.com/",
            )
            self._write_html(
                site_root,
                "about/index.html",
                "https://example.com/about/",
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (2, 1, 0, 0))
        self.assertEqual(
            entries,
            [
                ("https://example.com/", None),
                ("https://example.com/about/", None),
            ],
        )

    def test_uses_date_modified_before_publication_date(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_qmd(
                project_root,
                "posts/example/index.qmd",
                'title: Example\ndate: 2024-01-02\ndate-modified: "2024-02-03"',
            )
            self._write_html(
                site_root,
                "posts/example/index.html",
                "https://example.com/posts/example/",
            )
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/posts/example/", "2026-08-29T12:00:00Z")],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (0, 0, 1, 0))
        self.assertEqual(
            entries,
            [("https://example.com/posts/example/", "2024-02-03")],
        )

    def test_removes_build_timestamp_when_source_has_no_date(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_qmd(project_root, "about/index.qmd", "title: About")
            self._write_html(
                site_root,
                "about/index.html",
                "https://example.com/about/",
            )
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/about/", "2026-08-29T12:00:00Z")],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (0, 0, 0, 1))
        self.assertEqual(entries, [("https://example.com/about/", None)])

    def test_removes_companion_notebook_beside_index_page(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_qmd(
                project_root,
                "posts/example/index.qmd",
                "title: Example\ndate: 2024-01-02",
            )
            self._write_notebook(
                project_root,
                "posts/example/companion.ipynb",
                "title: Companion\ndate: 2024-01-03",
            )
            self._write_html(
                site_root,
                "posts/example/index.html",
                "https://example.com/posts/example/",
            )
            self._write_html(
                site_root,
                "posts/example/companion.html",
                "https://example.com/posts/example/companion.html",
            )
            sitemap = self._write_sitemap(
                site_root,
                [
                    (
                        "https://example.com/posts/example/",
                        "2026-08-29T12:00:00Z",
                    ),
                    (
                        "https://example.com/posts/example/companion.html",
                        "2026-08-29T12:00:00Z",
                    ),
                ],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (0, 1, 1, 0))
        self.assertEqual(
            entries,
            [("https://example.com/posts/example/", "2024-01-02")],
        )

    def test_keeps_standalone_notebook_and_omits_unknown_lastmod(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_notebook(project_root, "posts/notebook/example.ipynb")
            self._write_html(
                site_root,
                "posts/notebook/example.html",
                "https://example.com/posts/notebook/example.html",
            )
            sitemap = self._write_sitemap(
                site_root,
                [
                    (
                        "https://example.com/posts/notebook/example.html",
                        "2026-08-29T12:00:00Z",
                    )
                ],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (0, 0, 0, 1))
        self.assertEqual(
            entries,
            [("https://example.com/posts/notebook/example.html", None)],
        )

    def test_uses_date_from_retained_standalone_notebook(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_notebook(
                project_root,
                "posts/notebook/example.ipynb",
                'title: Example\ndate: "2024-04-05" # publication date',
            )
            self._write_html(
                site_root,
                "posts/notebook/example.html",
                "https://example.com/posts/notebook/example.html",
            )
            sitemap = self._write_sitemap(
                site_root,
                [
                    (
                        "https://example.com/posts/notebook/example.html",
                        "2026-08-29T12:00:00Z",
                    )
                ],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (0, 0, 1, 0))
        self.assertEqual(
            entries,
            [("https://example.com/posts/notebook/example.html", "2024-04-05")],
        )

    def test_alias_uses_canonical_target_date(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_qmd(
                project_root,
                "alias/index.qmd",
                "title: Alias\ndate: 2023-01-02",
            )
            self._write_qmd(
                project_root,
                "canonical/index.qmd",
                "title: Canonical\ndate-modified: 2024-03-04",
            )
            self._write_html(
                site_root,
                "alias/index.html",
                "https://example.com/canonical/",
            )
            self._write_html(
                site_root,
                "canonical/index.html",
                "https://example.com/canonical/",
            )
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/alias/", "2026-08-29T12:00:00Z")],
            )

            result = canonicalise_sitemap(sitemap, project_root)
            entries = self._entries(sitemap)

        self.assertEqual(result, (1, 0, 1, 0))
        self.assertEqual(
            entries,
            [("https://example.com/canonical/", "2024-03-04")],
        )

    def test_rejects_sitemap_url_without_rendered_page(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/missing/", None)],
            )

            with self.assertRaisesRegex(ValueError, "no rendered page"):
                canonicalise_sitemap(sitemap, project_root)

    def test_rejects_rendered_page_without_canonical_url(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            output = site_root / "about/index.html"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("<!doctype html><title>About</title>", encoding="utf-8")
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/about/", None)],
            )

            with self.assertRaisesRegex(ValueError, "no canonical URL"):
                canonicalise_sitemap(sitemap, project_root)

    def test_rejects_notebook_source_url_as_canonical(self) -> None:
        with TemporaryDirectory() as directory:
            project_root = Path(directory)
            site_root = project_root / "_site"
            self._write_notebook(project_root, "posts/notebook/example.ipynb")
            self._write_html(
                site_root,
                "posts/notebook/example.html",
                "https://example.com/posts/notebook/example.ipynb",
            )
            copied_notebook = site_root / "posts/notebook/example.ipynb"
            copied_notebook.parent.mkdir(parents=True, exist_ok=True)
            copied_notebook.write_text("{}", encoding="utf-8")
            sitemap = self._write_sitemap(
                site_root,
                [("https://example.com/posts/notebook/example.html", None)],
            )

            with self.assertRaisesRegex(ValueError, "has no rendered target"):
                canonicalise_sitemap(sitemap, project_root)


if __name__ == "__main__":
    unittest.main()
