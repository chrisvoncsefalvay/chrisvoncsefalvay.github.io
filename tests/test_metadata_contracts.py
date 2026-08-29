import ast
import json
from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOMEPAGE_DESCRIPTION = (
    "Chris von Csefalvay researches language-model post-training, agentic AI, "
    "reinforcement learning from verifiable rewards and computational epidemiology."
)
ABOUT_DESCRIPTION = (
    "Chris von Csefalvay is an AI researcher and computational epidemiologist. "
    "He leads post-training research and clinical intelligence at HCLTech."
)


def front_matter(relative_path: str) -> str:
    text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{relative_path} has no YAML front matter")
    return text.split("---", 2)[1]


def quoted_field(metadata: str, field: str) -> str:
    match = re.search(rf"(?m)^{re.escape(field)}:\s*(.+?)\s*$", metadata)
    if match is None:
        raise AssertionError(f"Missing {field}")
    return ast.literal_eval(match.group(1))


class PresentationMetadataTests(unittest.TestCase):
    def test_descriptions_are_concise_and_have_a_concise_fallback(self) -> None:
        homepage = quoted_field(front_matter("index.qmd"), "description")
        about = quoted_field(front_matter("about/index.qmd"), "description")
        configuration = (PROJECT_ROOT / "_quarto.yml").read_text(encoding="utf-8")
        fallback_match = re.search(r'(?m)^  description:\s*(".*")\s*$', configuration)

        self.assertIsNotNone(fallback_match)
        fallback = ast.literal_eval(fallback_match.group(1))
        self.assertEqual(homepage, HOMEPAGE_DESCRIPTION)
        self.assertEqual(about, ABOUT_DESCRIPTION)
        self.assertEqual(fallback, homepage)
        self.assertNotEqual(homepage, about)
        self.assertLessEqual(len(homepage), 160)
        self.assertLessEqual(len(about), 160)

    def test_about_page_uses_a_non_repetitive_title(self) -> None:
        self.assertEqual(
            quoted_field(front_matter("about/index.qmd"), "title"),
            "About",
        )

    def test_homepage_contains_no_agentic_typo(self) -> None:
        homepage = (PROJECT_ROOT / "index.qmd").read_text(encoding="utf-8")
        self.assertNotIn("agrntic", homepage.lower())


class ProfilePageSchemaTests(unittest.TestCase):
    def test_about_page_links_profile_to_existing_person(self) -> None:
        metadata = front_matter("about/index.qmd")
        match = re.search(
            r'<script type="application/ld\+json">(\{.*\})</script>',
            metadata,
        )
        self.assertIsNotNone(match)
        schema = json.loads(match.group(1))

        self.assertEqual(schema["@context"], "https://schema.org")
        self.assertEqual(schema["@type"], "ProfilePage")
        self.assertEqual(
            schema["@id"],
            "https://chrisvoncsefalvay.com/about/#profile-page",
        )
        self.assertEqual(schema["url"], "https://chrisvoncsefalvay.com/about/")
        self.assertEqual(schema["name"], "About Chris von Csefalvay")
        self.assertEqual(
            schema["mainEntity"],
            {
                "@type": "Person",
                "@id": "https://chrisvoncsefalvay.com/#person",
                "name": "Chris von Csefalvay",
            },
        )
        self.assertEqual(
            schema["isPartOf"],
            {"@id": "https://chrisvoncsefalvay.com/#website"},
        )

        configuration = (PROJECT_ROOT / "_quarto.yml").read_text(encoding="utf-8")
        self.assertIn('"@id":"https://chrisvoncsefalvay.com/#person"', configuration)
        self.assertIn('"@id":"https://chrisvoncsefalvay.com/#website"', configuration)


if __name__ == "__main__":
    unittest.main()
