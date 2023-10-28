import re
import bs4
import requests

WR_LINK: str = "https://www.concept2.com/skierg/motivation/records/adaptive-world?event=&gender=M&age_category=30&adaptive=31&op=Search&form_id=concept2_record_search_form#results"

TIME_EVENTS = [1, 4, 30, 60]

def count_times_of_world_records(link: str = WR_LINK) -> int:
    """Count the number of times Chris von Csefalvay holds a world record based on the linked site."""
    soup = bs4.BeautifulSoup(requests.get(link).text, "html.parser")
    return len(soup.find_all("td", string="Chris von Csefalvay"))


def get_world_records(link: str = WR_LINK) -> list:
    """Gets a list of Events from the Event column of the table on the linked site where the world record is held by Chris von Csefalvay (i.e. the Name column has my name)."""
    soup = bs4.BeautifulSoup(requests.get(link).text, "html.parser")

    # Get the table of world records, which is in an element with the id "concept2-record-search-form"
    table = soup.find(id="concept2-record-search-form")

    # Return a dict that comprises each row that contains my name in the Name column, with the Event as the key and the time as the value
    results = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) > 3 and cells[3].string == "Chris von Csefalvay":
            results.append(cells[1].string)

    # Sort results, with distance events first and sorted by distance, then time events.
    results.sort(key=lambda x: (int(x) in TIME_EVENTS, int(x)))

    return results

def render_text_list_of_distance_events(events: list) -> str:
    """Renders a list of distance events as a string, "pretty printed" with "and" before the last item if there is more than one items."""
    if len(events) == 0:
        return ""
    elif len(events) == 1:
        return events[0] + " distance"
    else:
        return ", ".join(events[:-1]) + " and " + events[-1] + " distances"


def render_text_list_of_time_events(events: list) -> str:
    """Renders a list of time events as a string, "pretty printed" with "and" before the last item if there is more than one items."""
    if len(events) == 0:
        return ""
    elif len(events) == 1:
        return events[0] + " time"
    else:
        return ", ".join(events[:-1]) + " and " + events[-1] + " times"


def resolve_events(event: str) -> str:
    """Resolves whether a distance is a metre distance or a time event and represents them in a consistent format."""

    if int(event) in TIME_EVENTS:
        # This is a time event, so format it as such
        return f"{event} minutes"
    else:
        # This is a distance event, so format it as such
        return f"{int(event):,}m"


def get_text_of_all_distance_events(events: list) -> str:
    """Gets a string that lists all distance events in the list."""

    # Filter events list for non-TIME_EVENTS:
    distance_events = [i for i in events if int(i) not in TIME_EVENTS]

    # Return a string that lists all distance events in the list
    return render_text_list_of_distance_events([resolve_events(i) for i in distance_events])


def get_text_of_all_time_events(events: list) -> str:
    """Gets a string that lists all time events in the list."""

    # Filter events list for TIME_EVENTS:
    time_events = [i for i in events if int(i) in TIME_EVENTS]

    # Return a string that lists all time events in the list
    return render_text_list_of_time_events([resolve_events(i) for i in time_events])


def render_text_for_all_events(events: list) -> str:
    """Renders a string that lists all events in the list."""

    # Filter events list for TIME_EVENTS:
    time_events = [i for i in events if int(i) in TIME_EVENTS]

    # Filter events list for non-TIME_EVENTS:
    distance_events = [i for i in events if int(i) not in TIME_EVENTS]

    # If there are no time events, return a string that lists all distance events in the list
    if len(time_events) == 0:
        return get_text_of_all_distance_events(distance_events)

    # If there are no distance events, return a string that lists all time events in the list
    if len(distance_events) == 0:
        return get_text_of_all_time_events(time_events)

    # If there are both time and distance events, return a string that lists all distance events in the list and all time events in the list. If there is only one time event, use "the" before listing the time event.
    if len(time_events) == 1:
        return get_text_of_all_distance_events(distance_events) + " and the " + get_text_of_all_time_events(time_events)


def generate_world_record_string():
    # Determine if I hold any current records by count_times_of_world_records() > 0
    if count_times_of_world_records() > 0:
        # Get a list of events where I hold the world record
        events = get_world_records()

        # Return a string that lists all events in the list
        return f"In the latter, I [currently hold the world record{'s' if count_times_of_world_records() > 1 else ''} for {render_text_for_all_events(events)}]({WR_LINK})."
    else:
        return ""


if __name__ == "__main__":
    import os

    if not os.getenv("QUARTO_PROJECT_RENDER_ALL"):
        exit()

    print("Checking SkiErg results...")
    print(f"{count_times_of_world_records()} world records held.")
    print(f"World records held: {get_world_records()}")
    print(f"Rendering results...")

    with open("index.qmd", "r") as f:
        contents = f.read()
        contents = re.sub(r"(?<=<!-- skierg_results -->).*?(?=<!-- /skierg_results -->)",
                          generate_world_record_string(),
                          contents, flags=re.DOTALL)

    with open("index.qmd", "w") as f:
        f.write(contents)
        print("Done.")
