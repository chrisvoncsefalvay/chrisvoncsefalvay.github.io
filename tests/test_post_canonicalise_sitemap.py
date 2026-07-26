from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import xml.etree.ElementTree as ET

from scripts.post_canonicalise_sitemap import (
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
    def test_rewrites_and_deduplicates_generated_sitemap(self) -> None:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="{SITEMAP_NAMESPACE}">
  <url><loc>https://example.com/index.html</loc></url>
  <url><loc>https://example.com/about/index.html</loc></url>
  <url><loc>https://example.com/about/</loc></url>
</urlset>
"""
        with TemporaryDirectory() as directory:
            sitemap = Path(directory) / "sitemap.xml"
            sitemap.write_text(xml, encoding="utf-8")

            rewritten, removed = canonicalise_sitemap(sitemap)

            tree = ET.parse(sitemap)
            locations = [
                element.text
                for element in tree.findall(
                    f".//{{{SITEMAP_NAMESPACE}}}loc"
                )
            ]

        self.assertEqual(rewritten, 2)
        self.assertEqual(removed, 1)
        self.assertEqual(
            locations,
            ["https://example.com/", "https://example.com/about/"],
        )


if __name__ == "__main__":
    unittest.main()
