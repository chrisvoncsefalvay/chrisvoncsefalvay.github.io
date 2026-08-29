#!/usr/bin/env python3
"""Validate rendered presentation metadata and ProfilePage semantics."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence


HOME_DESCRIPTION = (
    "Chris von Csefalvay researches language-model post-training, agentic AI, "
    "reinforcement learning from verifiable rewards and computational epidemiology."
)
ABOUT_DESCRIPTION = (
    "Chris von Csefalvay is an AI researcher and computational epidemiologist. "
    "He leads post-training research and clinical intelligence at HCLTech."
)
HOME_TITLE = "Chris von Csefalvay"
ABOUT_TITLE = "About – Chris von Csefalvay"
ABOUT_HEADING = "About"
ABOUT_URL = "https://chrisvoncsefalvay.com/about/"
PROFILE_PAGE_ID = f"{ABOUT_URL}#profile-page"
PERSON_ID = "https://chrisvoncsefalvay.com/#person"
WEBSITE_ID = "https://chrisvoncsefalvay.com/#website"


class MetadataValidationError(ValueError):
    """Report one or more rendered metadata contract failures."""


class RenderedMetadataParser(HTMLParser):
    """Collect metadata, headings and JSON-LD from one rendered page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta_by_name: dict[str, list[str]] = {}
        self.meta_by_property: dict[str, list[str]] = {}
        self.canonical_urls: list[str] = []
        self.titles: list[str] = []
        self.headings: list[str] = []
        self.json_ld_documents: list[str] = []

        self._inside_title = False
        self._title_parts: list[str] = []
        self._inside_heading = False
        self._heading_parts: list[str] = []
        self._inside_json_ld = False
        self._json_ld_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag = tag.lower()
        attributes = {
            name.lower(): value
            for name, value in attrs
            if value is not None
        }

        if tag == "title" and not self._inside_title:
            self._inside_title = True
            self._title_parts = []

        if tag == "h1" and not self._inside_heading:
            self._inside_heading = True
            self._heading_parts = []

        if (
            tag == "script"
            and not self._inside_json_ld
            and attributes.get("type", "").split(";", 1)[0].strip().lower()
            == "application/ld+json"
        ):
            self._inside_json_ld = True
            self._json_ld_parts = []

        if tag == "meta":
            self._collect_meta(attributes)
        elif tag == "link":
            relationships = attributes.get("rel", "").lower().split()
            href = attributes.get("href")
            if "canonical" in relationships and href is not None:
                self.canonical_urls.append(href)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if tag == "title" and self._inside_title:
            self.titles.append(_normalise_text(self._title_parts))
            self._inside_title = False
            self._title_parts = []

        if tag == "h1" and self._inside_heading:
            self.headings.append(_normalise_text(self._heading_parts))
            self._inside_heading = False
            self._heading_parts = []

        if tag == "script" and self._inside_json_ld:
            self.json_ld_documents.append("".join(self._json_ld_parts))
            self._inside_json_ld = False
            self._json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self._title_parts.append(data)
        if self._inside_heading:
            self._heading_parts.append(data)
        if self._inside_json_ld:
            self._json_ld_parts.append(data)

    def _collect_meta(self, attributes: dict[str, str]) -> None:
        content = attributes.get("content")
        if content is None:
            return

        name = attributes.get("name")
        if name is not None:
            self.meta_by_name.setdefault(name.strip().lower(), []).append(content)

        property_name = attributes.get("property")
        if property_name is not None:
            self.meta_by_property.setdefault(
                property_name.strip().lower(), []
            ).append(content)


def _normalise_text(parts: Iterable[str]) -> str:
    """Collapse presentation whitespace while retaining punctuation."""
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _read_rendered_page(
    path: Path,
    page_name: str,
    errors: list[str],
) -> RenderedMetadataParser | None:
    if not path.is_file():
        errors.append(f"{page_name}: rendered file is missing: {path}")
        return None

    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{page_name}: could not read {path}: {error}")
        return None

    parser = RenderedMetadataParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception as error:  # HTMLParser extensions may raise parser errors.
        errors.append(f"{page_name}: could not parse {path}: {error}")
        return None
    return parser


def _require_single_value(
    errors: list[str],
    page_name: str,
    field: str,
    values: Sequence[str],
    expected: str,
) -> None:
    if len(values) != 1:
        errors.append(
            f"{page_name}: expected exactly one {field}; found {len(values)}."
        )
    elif values[0] != expected:
        errors.append(
            f"{page_name}: {field} must be {expected!r}; got {values[0]!r}."
        )


def _decode_json_ld(
    parser: RenderedMetadataParser,
    page_name: str,
    errors: list[str],
) -> list[Any]:
    documents: list[Any] = []
    for index, source in enumerate(parser.json_ld_documents, start=1):
        if not source.strip():
            errors.append(f"{page_name}: JSON-LD block {index} is empty.")
            continue
        try:
            documents.append(json.loads(source))
        except json.JSONDecodeError as error:
            errors.append(
                f"{page_name}: JSON-LD block {index} is invalid: "
                f"{error.msg} at line {error.lineno}, column {error.colno}."
            )
    return documents


def _top_level_entities(documents: Iterable[Any]) -> list[dict[str, Any]]:
    """Return JSON-LD nodes defined at document or @graph level."""
    entities: list[dict[str, Any]] = []
    for document in documents:
        candidates = document if isinstance(document, list) else [document]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if "@type" in candidate or "@id" in candidate:
                entities.append(candidate)
            graph = candidate.get("@graph")
            if isinstance(graph, list):
                entities.extend(node for node in graph if isinstance(node, dict))
    return entities


def _has_type(entity: dict[str, Any], expected: str) -> bool:
    entity_type = entity.get("@type")
    if isinstance(entity_type, str):
        return entity_type == expected
    return isinstance(entity_type, list) and expected in entity_type


def _require_entity(
    errors: list[str],
    entities: Iterable[dict[str, Any]],
    entity_id: str,
    entity_type: str,
) -> None:
    if not any(
        entity.get("@id") == entity_id and _has_type(entity, entity_type)
        for entity in entities
    ):
        errors.append(
            "About: rendered JSON-LD must define a top-level "
            f"{entity_type} with @id {entity_id!r}."
        )


def _validate_page_metadata(
    parser: RenderedMetadataParser,
    page_name: str,
    description: str,
    errors: list[str],
) -> None:
    _require_single_value(
        errors,
        page_name,
        "meta description",
        parser.meta_by_name.get("description", []),
        description,
    )
    _require_single_value(
        errors,
        page_name,
        "Open Graph description",
        parser.meta_by_property.get("og:description", []),
        description,
    )
    _require_single_value(
        errors,
        page_name,
        "Twitter description",
        parser.meta_by_name.get("twitter:description", []),
        description,
    )


def validate_metadata(site_root: Path | str = Path("_site")) -> None:
    """Validate the rendered homepage and About page metadata contract."""
    site_root = Path(site_root)
    errors: list[str] = []
    homepage = _read_rendered_page(site_root / "index.html", "Homepage", errors)
    about = _read_rendered_page(
        site_root / "about" / "index.html",
        "About",
        errors,
    )

    if homepage is not None:
        _validate_page_metadata(
            homepage,
            "Homepage",
            HOME_DESCRIPTION,
            errors,
        )
        _require_single_value(
            errors,
            "Homepage",
            "document title",
            homepage.titles,
            HOME_TITLE,
        )
        _require_single_value(
            errors,
            "Homepage",
            "H1",
            homepage.headings,
            HOME_TITLE,
        )

    if about is not None:
        _validate_page_metadata(about, "About", ABOUT_DESCRIPTION, errors)
        _require_single_value(
            errors,
            "About",
            "document title",
            about.titles,
            ABOUT_TITLE,
        )
        _require_single_value(
            errors,
            "About",
            "Open Graph title",
            about.meta_by_property.get("og:title", []),
            ABOUT_TITLE,
        )
        _require_single_value(
            errors,
            "About",
            "Twitter title",
            about.meta_by_name.get("twitter:title", []),
            ABOUT_TITLE,
        )
        _require_single_value(
            errors,
            "About",
            "H1",
            about.headings,
            ABOUT_HEADING,
        )
        _require_single_value(
            errors,
            "About",
            "canonical URL",
            about.canonical_urls,
            ABOUT_URL,
        )

    homepage_documents = (
        _decode_json_ld(homepage, "Homepage", errors)
        if homepage is not None
        else []
    )
    about_documents = (
        _decode_json_ld(about, "About", errors) if about is not None else []
    )
    homepage_entities = _top_level_entities(homepage_documents)
    about_entities = _top_level_entities(about_documents)
    profiles = [
        ("Homepage", entity)
        for entity in homepage_entities
        if _has_type(entity, "ProfilePage")
    ] + [
        ("About", entity)
        for entity in about_entities
        if _has_type(entity, "ProfilePage")
    ]

    if len(profiles) != 1:
        errors.append(
            "Rendered homepage and About JSON-LD must contain exactly one "
            f"ProfilePage; found {len(profiles)}."
        )
    else:
        page_name, profile = profiles[0]
        if page_name != "About":
            errors.append("The sole rendered ProfilePage must be on the About page.")
        expected_fields = {
            "@id": PROFILE_PAGE_ID,
            "name": "About Chris von Csefalvay",
            "url": ABOUT_URL,
            "mainEntity": {
                "@type": "Person",
                "@id": PERSON_ID,
                "name": HOME_TITLE,
            },
            "isPartOf": {"@id": WEBSITE_ID},
        }
        for field, expected in expected_fields.items():
            actual = profile.get(field)
            if actual != expected:
                errors.append(
                    f"About: ProfilePage {field} must be {expected!r}; "
                    f"got {actual!r}."
                )

    if about is not None:
        _require_entity(errors, about_entities, PERSON_ID, "Person")
        _require_entity(errors, about_entities, WEBSITE_ID, "WebSite")

    if errors:
        raise MetadataValidationError(
            "Rendered metadata validation failed:\n- " + "\n- ".join(errors)
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate rendered presentation metadata and ProfilePage semantics."
    )
    parser.add_argument(
        "site_root",
        nargs="?",
        type=Path,
        default=Path("_site"),
        help="Rendered site directory (default: _site)",
    )
    args = parser.parse_args(argv)
    try:
        validate_metadata(args.site_root)
    except MetadataValidationError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Validated rendered metadata in {args.site_root}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
