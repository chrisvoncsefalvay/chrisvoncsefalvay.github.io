import requests
import os
import yaml
import re
import logging
import sys
from typing import Dict, Optional

API_URL: str = "https://api.rogue-scholar.org/blogs/chrisvoncsefalvay"
POSTS_FOLDER: str = "posts"

# Configure logging to be more visible in CI/CD
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def fetch_dois_from_api(url: str) -> Dict[str, str]:
    """Fetch blog posts with DOIs from the Rogue Scholar API."""
    try:
        logging.info(f"Fetching DOI data from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # The API returns an object with 'items' array containing the posts
        posts = data.get('items', [])
        
        posts_with_dois = {}
        for post in posts:
            title = post.get('title', '')
            doi = post.get('doi', '')
            # Remove the https://doi.org/ prefix if present
            if doi.startswith('https://doi.org/'):
                doi = doi.replace('https://doi.org/', '')
            
            if title and doi:
                posts_with_dois[title] = doi
                logging.debug(f"Found DOI for '{title}': {doi}")
                
        logging.info(f"Successfully fetched {len(posts_with_dois)} posts with DOIs from API")
        return posts_with_dois
    except requests.RequestException as e:
        logging.error(f"Error fetching data from API: {e}")
        logging.error("Continuing with empty DOI data - build will proceed without DOI updates")
        return {}


def process_qmd_file(file_path: str, posts_with_dois: Dict[str, str]) -> None:
    """Process a single .qmd file to update citation information."""
    with open(file_path, 'r', encoding='utf-8') as stream:
        contents = stream.read()

    delim = re.compile(r'^---$', re.MULTILINE)
    splits = re.split(delim, contents)
    
    if len(splits) < 3:
        logging.warning(f"File {file_path} does not have valid YAML frontmatter")
        return
        
    yaml_preamble = splits[1].strip()
    rest_of_post = delim.pattern.join([''] + splits[2:])  # Preserve additional --- delimiters

    try:
        yaml_contents = yaml.safe_load(yaml_preamble)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML in {file_path}: {e}")
        return

    if yaml_contents:
        citation = yaml_contents.get('citation')
        google_scholar = yaml_contents.get('google-scholar')
        categories = yaml_contents.get('categories', [])
        title = yaml_contents.get('title', '')

        # Check files from crosspost categories
        if any("cross-post" in str(category).lower() for category in categories):
            if yaml_contents.get("citation") == True or yaml_contents.get("google-scholar") == True:
                yaml_contents["citation"] = False
                yaml_contents["google-scholar"] = False
                logging.info(f'Modified crosspost {title} to remove Google Scholar and/or citation reference.')
        else:
            # Ensure that google-scholar is set to true if citation is required
            if citation and not google_scholar:
                yaml_contents["google-scholar"] = True
                logging.info(f'Setting google-scholar to true for {title}')

            # If citation is true but no DOI, and post exists in scraped posts
            if citation is True and title in posts_with_dois:
                yaml_contents['citation'] = {'doi': posts_with_dois[title]}
                logging.info(f'Adding DOI {posts_with_dois[title]} for {title}.')
            elif citation is True and title not in posts_with_dois:
                logging.warning(f'Post "{title}" has citation=true but no DOI found in API')

        new_preamble = yaml.dump(yaml_contents, default_flow_style=False, sort_keys=False).rstrip()
        new_yaml_doc = f"---\n{new_preamble}\n---"

        # write the modified YAML document back to file
        with open(file_path, 'w', encoding='utf-8') as yaml_file:
            yaml_file.write(new_yaml_doc + rest_of_post)
        logging.info(f'Updated file for post: {title}')


def process_all_qmd_files(directory: str, posts_with_dois: Dict[str, str]) -> None:
    """Process all index.qmd files in the posts directory."""
    processed_count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == "index.qmd":
                file_path = os.path.join(root, file)
                process_qmd_file(file_path, posts_with_dois)
                processed_count += 1
    
    logging.info(f"Processed {processed_count} index.qmd files")


if __name__ == "__main__":
    logging.info("Starting DOI processing script")
    
    # Check if posts folder exists
    if not os.path.exists(POSTS_FOLDER):
        logging.error(f"Posts folder '{POSTS_FOLDER}' does not exist. Aborting.")
        sys.exit(1)
    
    posts_with_dois = fetch_dois_from_api(API_URL)
    if posts_with_dois:
        process_all_qmd_files(POSTS_FOLDER, posts_with_dois)
        logging.info("DOI processing completed successfully")
    else:
        logging.warning("No DOI data fetched from API. Proceeding without DOI updates.")
        # Don't abort - let the build continue even if API is unavailable
    
    logging.info("DOI processing script finished")