import bibtexparser
from collections import defaultdict

def read_bibtex_file(filename) -> dict:
    """Reads a BibTeX file and returns entries as a dict keyed by year of publication."""
    with open(filename, 'r') as bibtex_file:
        bibtex_str = bibtex_file.read()
    bib_database = bibtexparser.loads(bibtex_str)

    entries = bib_database.entries
    entries.sort(key=lambda x: x['year'], reverse=True)

    entries_by_year = defaultdict(list)
    for entry in entries:
        entries_by_year[entry['year']].append(entry)

    return entries_by_year


def process_authors_to_string_with_highlighting(authors: str, highlight_name: str = "csefalvay") -> str:
    authors = authors.split(" and ")
    authors = [author.split(", ") for author in authors]
    authors = [f"{author[0]} {author[1][0]}" for author in authors]
    authors = [f"**{author}**" if highlight_name.lower() in author.lower() else author for author in authors]
    authors = ", ".join(authors)
    return authors


def render_article_as_nlm(entry: dict) -> str:
    """Renders an article BibTeX entry dict in the NLM format."""
    authors = process_authors_to_string_with_highlighting(entry["author"])

    title = entry["title"]
    journal = entry["journal"]
    volume = entry.get("volume")
    pages = entry.get("pages")
    year = entry["year"]
    doi = entry.get("doi")

    if "arxiv preprint" in journal.lower():
        arxiv_id = journal.split(":")[1]
        arxiv_link = f"https://arxiv.org/abs/{arxiv_id}"
        return f"{authors} ({year}). {title}. _arXiv_ [{arxiv_id}]({arxiv_link})."
    elif "medRxiv" in journal:
        res = f"{authors} ({year}). {title}. _medRxiv_."
        if doi:
            return res + f" doi:[{doi}](https://doi.org/{doi})."
        else:
            return res
    else:
        res = f"{authors} ({year}). {title}. _{journal}_ {year}"
        if volume:
            res += f";**{volume}**"
        if pages:
            res += f":{pages}"
        if doi:
            return res + f". doi:[{doi}](https://doi.org/{doi})"
        return res + "."


def render_book_as_nlm(entry: dict) -> str:
    """Renders a book BibTeX entry dict in the NLM format."""
    authors = process_authors_to_string_with_highlighting(entry["author"])

    title = entry["title"]
    publisher = entry["publisher"]
    location = entry.get("address")
    year = entry["year"]
    url = entry.get("url")

    ayt = f"{authors} ({year}). {title}."

    if location:
        ayt += f" {location}: {publisher}."
    else:
        ayt += f" {publisher}."

    if url:
        ayt += f" [{url}]({url})."

    return ayt

def render_as_nlm(entry: dict) -> str:
    """Renders a BibTeX entry dict in the NLM format."""
    if entry["ENTRYTYPE"] == "article":
        return render_article_as_nlm(entry)
    elif entry["ENTRYTYPE"] == "book" or entry["ENTRYTYPE"] == "misc":
        return render_book_as_nlm(entry)
    else:
        raise ValueError()

def generate_list_by_year(entries_by_year: dict) -> str:
    """Generates a Markdown list of publications by year."""
    md = ""
    for year, entries in sorted(entries_by_year.items(), reverse=True):
        md += f"# {year}\n\n"
        for entry in entries:
            md += f"- {render_as_nlm(entry)}\n\n"

    # determine number of years and entries
    years = len(entries_by_year)
    total_entries = 0
    for year, entries in entries_by_year.items():
        total_entries += len(entries)

    print("Processed " + str(total_entries) + " entries from " + str(years) + " years.")
    return md


def write_into_file(entries_by_year: dict, destination_path: str, destination_div: str) -> None:
    """Opens the file at `destination_path`, finds the Markdown div `destination_div`, deletes its current contents
    and renders the list of bibliography entries into it."""

    with open(destination_path, 'r') as file:
        md = file.read()

    start = md.find(f"<!-- {destination_div} -->")
    end = md.find(f"<!-- /{destination_div} -->")

    md = md[:start] + f"<!-- {destination_div} -->\n\n" + generate_list_by_year(
        entries_by_year) + md[end:]

    with open(destination_path, 'w') as file:
        file.write(md)


if __name__ == "__main__":
    import os

    if not os.getenv("QUARTO_PROJECT_RENDER_ALL"):
        exit()

    OUTPUT_FILENAME: str = "papers/index.qmd"
    INPUT_FILENAME: str = "papers/bibliography.bib"

    print(f"Rendering bibliography...")
    print("Reading BibTeX file from " + INPUT_FILENAME)
    entries = read_bibtex_file(INPUT_FILENAME)

    print("Writing bibliography to " + OUTPUT_FILENAME)
    write_into_file(entries, OUTPUT_FILENAME, "references")
    print("Done.")
