import contextlib
from html import escape
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.post_validate_metadata import (
    ABOUT_DESCRIPTION,
    ABOUT_HEADING,
    ABOUT_TITLE,
    ABOUT_URL,
    HOME_DESCRIPTION,
    HOME_TITLE,
    PERSON_ID,
    PROFILE_PAGE_ID,
    WEBSITE_ID,
    MetadataValidationError,
    main,
    validate_metadata,
)


PROFILE_PAGE = {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    "@id": PROFILE_PAGE_ID,
    "url": ABOUT_URL,
    "name": "About Chris von Csefalvay",
    "mainEntity": {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": HOME_TITLE,
    },
    "isPartOf": {"@id": WEBSITE_ID},
}

GLOBAL_ENTITIES = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Person",
            "@id": PERSON_ID,
            "name": HOME_TITLE,
        },
        {
            "@type": "WebSite",
            "@id": WEBSITE_ID,
            "name": HOME_TITLE,
        },
    ],
}


def json_ld(value: object) -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(value, ensure_ascii=False)
        + "</script>"
    )


def rendered_page(
    *,
    title: str,
    description: str,
    heading: str,
    canonical: str | None = None,
    open_graph_title: str | None = None,
    twitter_title: str | None = None,
    json_ld_blocks: tuple[str, ...] = (),
    extra_head: str = "",
) -> str:
    title_metadata = ""
    if open_graph_title is not None:
        title_metadata += (
            f'<meta property="og:title" content="{escape(open_graph_title)}">'
        )
    if twitter_title is not None:
        title_metadata += (
            f'<meta name="twitter:title" content="{escape(twitter_title)}">'
        )
    canonical_link = (
        f'<link href="{escape(canonical)}" rel="alternate canonical">'
        if canonical is not None
        else ""
    )
    return f"""<!doctype html>
<html>
<head>
  <title>{escape(title)}</title>
  <meta content="{escape(description)}" name="description">
  <meta content="{escape(description)}" property="og:description">
  <meta content="{escape(description)}" name="twitter:description">
  {title_metadata}
  {canonical_link}
  {''.join(json_ld_blocks)}
  {extra_head}
</head>
<body><h1><span>{escape(heading)}</span></h1></body>
</html>
"""


class RenderedMetadataFixtureTests(unittest.TestCase):
    def write_site(
        self,
        root: Path,
        *,
        homepage_title: str = HOME_TITLE,
        homepage_heading: str = HOME_TITLE,
        homepage_description: str = HOME_DESCRIPTION,
        about_title: str = ABOUT_TITLE,
        about_heading: str = ABOUT_HEADING,
        about_description: str = ABOUT_DESCRIPTION,
        about_canonical: str = ABOUT_URL,
        include_global_entities: bool = True,
        profile_page: dict[str, object] | None = None,
        homepage_json_ld: tuple[str, ...] = (),
        about_extra_json_ld: tuple[str, ...] = (),
        homepage_extra_head: str = "",
        about_extra_head: str = "",
    ) -> Path:
        site_root = root / "_site"
        (site_root / "about").mkdir(parents=True)
        (site_root / "index.html").write_text(
            rendered_page(
                title=homepage_title,
                description=homepage_description,
                heading=homepage_heading,
                json_ld_blocks=homepage_json_ld,
                extra_head=homepage_extra_head,
            ),
            encoding="utf-8",
        )
        about_json_ld = []
        if include_global_entities:
            about_json_ld.append(json_ld(GLOBAL_ENTITIES))
        about_json_ld.append(
            json_ld(PROFILE_PAGE if profile_page is None else profile_page)
        )
        about_json_ld.extend(about_extra_json_ld)
        (site_root / "about" / "index.html").write_text(
            rendered_page(
                title=about_title,
                description=about_description,
                heading=about_heading,
                canonical=about_canonical,
                open_graph_title=about_title,
                twitter_title=about_title,
                json_ld_blocks=tuple(about_json_ld),
                extra_head=about_extra_head,
            ),
            encoding="utf-8",
        )
        return site_root

    def test_accepts_exact_rendered_contract_from_default_site_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_site(root)
            previous_directory = Path.cwd()
            try:
                os.chdir(root)
                validate_metadata()
            finally:
                os.chdir(previous_directory)

    def test_rejects_description_that_does_not_propagate(self) -> None:
        with TemporaryDirectory() as directory:
            site_root = self.write_site(Path(directory))
            about = site_root / "about" / "index.html"
            about.write_text(
                about.read_text(encoding="utf-8").replace(
                    f'<meta content="{ABOUT_DESCRIPTION}" '
                    'name="twitter:description">',
                    '<meta content="A stale description." '
                    'name="twitter:description">',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                MetadataValidationError,
                "About: Twitter description must be",
            ):
                validate_metadata(site_root)

    def test_rejects_wrong_about_title_heading_and_canonical(self) -> None:
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                about_title="About Chris von Csefalvay",
                about_heading="About Chris von Csefalvay",
                about_canonical="https://chrisvoncsefalvay.com/about/index.html",
            )

            with self.assertRaises(MetadataValidationError) as context:
                validate_metadata(site_root)

            message = str(context.exception)
            self.assertIn("About: document title must be", message)
            self.assertIn("About: Open Graph title must be", message)
            self.assertIn("About: Twitter title must be", message)
            self.assertIn("About: H1 must be", message)
            self.assertIn("About: canonical URL must be", message)

    def test_rejects_wrong_homepage_title_and_heading(self) -> None:
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                homepage_title="Chris von Csefalvay – AI researcher",
                homepage_heading="AI researcher",
            )

            with self.assertRaises(MetadataValidationError) as context:
                validate_metadata(site_root)

            message = str(context.exception)
            self.assertIn("Homepage: document title must be", message)
            self.assertIn("Homepage: H1 must be", message)

    def test_rejects_duplicate_metadata_fields(self) -> None:
        duplicate = (
            f'<meta name="description" content="{escape(HOME_DESCRIPTION)}">'
        )
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                homepage_extra_head=duplicate,
            )

            with self.assertRaisesRegex(
                MetadataValidationError,
                "Homepage: expected exactly one meta description; found 2",
            ):
                validate_metadata(site_root)

    def test_rejects_more_than_one_profile_page_across_rendered_pages(self) -> None:
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                homepage_json_ld=(json_ld(PROFILE_PAGE),),
            )

            with self.assertRaisesRegex(
                MetadataValidationError,
                "exactly one ProfilePage; found 2",
            ):
                validate_metadata(site_root)

    def test_nested_main_entity_does_not_replace_global_entities(self) -> None:
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                include_global_entities=False,
            )

            with self.assertRaises(MetadataValidationError) as context:
                validate_metadata(site_root)

            message = str(context.exception)
            self.assertIn("top-level Person", message)
            self.assertIn("top-level WebSite", message)

    def test_rejects_profile_page_contract_drift(self) -> None:
        profile = {
            **PROFILE_PAGE,
            "@id": "https://chrisvoncsefalvay.com/about/#profile",
            "name": "About",
            "url": "https://chrisvoncsefalvay.com/about/index.html",
            "mainEntity": {"@id": PERSON_ID},
            "isPartOf": {"@id": "https://example.com/#website"},
        }
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                profile_page=profile,
            )

            with self.assertRaises(MetadataValidationError) as context:
                validate_metadata(site_root)

            message = str(context.exception)
            for field in ("@id", "name", "url", "mainEntity", "isPartOf"):
                self.assertIn(f"About: ProfilePage {field} must be", message)

    def test_reports_invalid_json_ld_clearly(self) -> None:
        invalid_json_ld = '<script type="application/ld+json">{"@type":</script>'
        with TemporaryDirectory() as directory:
            site_root = self.write_site(
                Path(directory),
                about_extra_json_ld=(invalid_json_ld,),
            )

            with self.assertRaisesRegex(
                MetadataValidationError,
                "About: JSON-LD block 3 is invalid",
            ):
                validate_metadata(site_root)

    def test_command_reports_missing_default_pages(self) -> None:
        with TemporaryDirectory() as directory:
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                exit_code = main([str(Path(directory) / "missing")])

            self.assertEqual(exit_code, 1)
            self.assertIn("Homepage: rendered file is missing", errors.getvalue())
            self.assertIn("About: rendered file is missing", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
