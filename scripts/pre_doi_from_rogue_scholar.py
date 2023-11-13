import requests
from bs4 import BeautifulSoup
import os
import yaml
import re
import logging
from typing import Dict

FEED_URL: str = "https://rogue-scholar.org/blogs/chrisvoncsefalvay"
POSTS_FOLDER: str = "posts"

logging.basicConfig(level=logging.INFO)

def scrape_blog_for_dois(url) -> Dict[str, str]:
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    articles = soup.select("article")[:10]
    posts_with_dois = {}
    for article in articles:
        title = article.select_one('h3').text
        doi_link = next((a['href'] for a in article.select('a') if a['href'].startswith('https://doi.org')), None)
        if doi_link:
            doi = doi_link.split('https://doi.org/')[1]
        else:
            doi = None
        posts_with_dois[title] = doi

    logging.info(f"Found {len(posts_with_dois)} posts with DOIs:")
    for title, doi in posts_with_dois.items():
        logging.info(f"{title}: {doi}")
    return posts_with_dois


def process_qmd_file(file_path: str, posts_with_dois: Dict[str, str]) -> None:
    with open(file_path, 'r') as stream:
        contents = stream.read()

    delim = re.compile(r'^---$', re.MULTILINE)
    splits = re.split(delim, contents)
    yaml_preamble = splits[1].strip() if len(splits) > 2 else ""
    rest_of_post = splits[2] if len(splits) > 2 else contents

    yaml_contents = yaml.safe_load(yaml_preamble) if yaml_preamble else None

    if yaml_contents:
        citation = yaml_contents.get('citation')
        google_scholar = yaml_contents.get('google-scholar')
        categories = yaml_contents.get('categories', [])
        title = yaml_contents.get('title')

        # Check files from crosspost categories
        if any("cross-post" in category.lower() for category in categories):
            if yaml_contents["citation"] == True or yaml_contents["google-scholar"] == True:
                yaml_contents["citation"] = False
                yaml_contents["google-scholar"] = False
                logging.info(f'Modified crosspost {title} to remove Google Scholar and/or citation reference.')
        else:
            # Ensure that google-scholar is set to true if citation is required
            if citation and not google_scholar:
                yaml_contents["google-scholar"] = True
                logging.info(f'Setting google-scholar to true for {title}')

            # If citation is true but no DOI, and post exists in scraped posts
            if citation is True and posts_with_dois.get(title):
                yaml_contents['citation'] = {'doi': posts_with_dois[title]}
                logging.info(f'Adding doi for {title}.')

        new_preamble = yaml.dump(yaml_contents).rstrip()
        new_yaml_doc = f"---\n{new_preamble}\n---"

        # write the modified YAML document back to file
        with open(file_path, 'w') as yaml_file:
            yaml_file.write(new_yaml_doc + rest_of_post)
        logging.info(f'Updated file {title}')


def process_all_qmd_files(directory: str, posts_with_dois: Dict[str, str]) -> None:
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith("index.qmd"):
                file_path = os.path.join(root, file)
                process_qmd_file(file_path, posts_with_dois)


if __name__ == "__main__":
    posts_with_dois = scrape_blog_for_dois(FEED_URL)
    process_all_qmd_files(POSTS_FOLDER, posts_with_dois)