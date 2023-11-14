import yaml
from difflib import SequenceMatcher
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

CANONICAL_ENTRIES = ["LLMs", "AI", "ML", "Julia", "Python", "Quarto"]

def is_similar(cat1, cat2):
    # Normalize to lower case
    cat1 = cat1.lower()
    cat2 = cat2.lower()

    # Remove pluralization
    if cat1.endswith('s'):
        cat1 = cat1[:-1]
    if cat2.endswith('s'):
        cat2 = cat2[:-1]

    similarity = SequenceMatcher(None, cat1, cat2).ratio()
    return similarity > 0.8, similarity

def replace_with_canonical_entries(folder):
    for filename in Path(folder).rglob('index.qmd'):
        replacements_made = []

        with open(filename, 'r') as file:
            lines = file.readlines()

        # Parse the YAML front-matter
        preamble_lines = []
        for line in lines[1:]:  # Skip the first '---'
            if line.strip() == "---":
                break
            preamble_lines.append(line)
        preamble = "".join(preamble_lines)

        metadata = yaml.safe_load(preamble)

        # Skip if there are no categories in the front-matter
        if 'categories' not in metadata:
            continue

        original_categories = metadata.get('categories', [])
        new_categories = []

        for category in original_categories:
            similarity_scores = [(canonical, *is_similar(canonical, category)) for canonical in CANONICAL_ENTRIES]
            canonical_category, is_match, similarity = max(similarity_scores, key=lambda x: x[2])
            if is_match:
                new_categories.append(canonical_category)
                replacements_made.append({
                    'original': category,
                    'replacement': canonical_category,
                    'similarity': similarity
                })
            else:
                # If not a match with a canonical category, keep the original
                new_categories.append(category)

        # Skip if no replacements were made
        if not replacements_made:
            continue

        # Update the categories in the metadata
        metadata['categories'] = new_categories

        new_preamble = yaml.dump(metadata, default_flow_style=False)

        # Recombine the front-matter and body
        body_idx = lines.index("---\n", 1) + 1  # Find the index after the second '---'
        new_content = ["---\n"] + [new_preamble, "---\n"] + lines[body_idx:]

        with open(filename, 'w') as file:
            file.writelines(new_content)

        logging.info(f'Processed file: {filename}, Replacements: {replacements_made}')

if __name__ == "__main__":
    replace_with_canonical_entries("posts")