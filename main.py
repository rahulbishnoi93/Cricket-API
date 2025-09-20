from flask import Flask, jsonify
import lxml
import requests
from bs4 import BeautifulSoup
import re
import time
from flask import Response
import json
from googlesearch import search #pip install googlesearch-python
from flask import render_template
from flask import make_response

app = Flask(__name__)

# Allowed teams dictionary
ALLOWED_TEAMS = {
    # ICC Full Members
    "IND": "India",
    "PAK": "Pakistan",
    "AUS": "Australia",
    "ENG": "England",
    "SA": "South Africa",
    "NZ": "New Zealand",
    "SL": "Sri Lanka",
    "BAN": "Bangladesh",
    "AFG": "Afghanistan",
    "IRE": "Ireland",
    "ZIM": "Zimbabwe",
    "WI": "West Indies",

    # Prominent ICC Associate Members
    "NED": "Netherlands",
    "NEP": "Nepal",
    "UAE": "United Arab Emirates",
    "NAM": "Namibia",
    "HK": "Hong Kong",
    "USA": "United States",
    "CAN": "Canada",
    "PNG": "Papua New Guinea",
    "OMA": "Oman",
    "OMAN": "Oman",

    #temp teams

}
DISABLE_FILTER_ALLOWED_TEAMS = False

# 🔒 Global cache headers
def with_cache(data, cache_control):
    response = make_response(jsonify(data))
    response.headers["Cache-Control"] = cache_control
    return response

@app.route('/allMatches')
def all_matches():
    link_schedule = f"https://www.cricbuzz.com/cricket-schedule/upcoming-series/international"
    source = requests.get(link_schedule).text
    soup = BeautifulSoup(source, "lxml")

    upcoming_matches = []

    # Each match container
    match_containers = soup.find_all("div", itemscope=True, itemtype="http://schema.org/SportsEvent")

    for match in match_containers:
        # Match title
        title_tag = match.find("a")
        match_title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract teams and remaining details
        team1, team2, details = "", "", ""
        if "," in match_title:
            teams_part, details = match_title.split(",", 1)
            teams = teams_part.split(" vs ")
            if len(teams) == 2:
                # Convert to short codes if in allowed teams
                team1_full = teams[0].strip()
                team2_full = teams[1].strip()
                team1_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team1_full), "")
                team2_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team2_full), "")
                if team1_code and team2_code:
                    team1 = team1_code
                    team2 = team2_code
            details = details.strip()
        else:
            if " vs " in match_title:
                teams = match_title.split(" vs ")
                if len(teams) == 2:
                    team1_full = teams[0].strip()
                    team2_full = teams[1].strip()
                    team1_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team1_full), "")
                    team2_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team2_full), "")
                    if team1_code and team2_code:
                        team1 = team1_code
                        team2 = team2_code

        # Skip if teams not allowed
        if not team1 or not team2:
            continue

        # Match date
        date_span = match.find("span", itemprop="startDate")
        match_date = date_span["content"].strip() if date_span and "content" in date_span.attrs else ""

        # Match time
        time_span = match.find("span", class_="schedule-date")
        match_time = time_span.get_text(strip=True) if time_span else ""

        upcoming_matches.append({
            "team1": team1,
            "team2": team2,
            "details": details,
            "date": match_date,
            "time": match_time
        })

    # Schedule → long cache (e.g. 6 hours)
    #return with_cache(upcoming_matches, "public, max-age=21600")  # 6 * 3600
    link_live = "https://www.cricbuzz.com/cricket-match/live-scores"
    source = requests.get(link_live).text
    page = BeautifulSoup(source, "lxml")

    # Container that holds all matches
    page = page.find("div", class_="cb-col cb-col-100 cb-bg-white")
    matches = page.find_all("a", class_="cb-lv-scrs-well")

    live_matches = []

    for m in matches:
        # extract matchId from href
        href = m.get("href", "")
        match_id = None
        if href.startswith("/live-cricket-scores/"):
            match_id = href.split("/")[2]  # second part is ID

        # Get team rows (batting + bowling team)
        team_rows = m.find_all("div", class_=["cb-hmscg-bat-txt", "cb-hmscg-bwl-txt"])

        team_data = []
        for row in team_rows:
            name = row.find("div", class_="cb-ovr-flo cb-hmscg-tm-nm")
            score = row.find_all("div", class_="cb-ovr-flo")[-1]  # last div is usually the score
            team_name = name.get_text(strip=True).upper() if name else ""

            team_data.append({
                "team": team_name,
                "score": score.get_text(strip=True) if score else ""
            })

        # Only keep matches where both teams are in allowed list
            # Only keep if valid teams
        if len(team_data) == 2 and (
            (team_data[0]['team'] in ALLOWED_TEAMS or team_data[1]['team'] in                     ALLOWED_TEAMS)
            or DISABLE_FILTER_ALLOWED_TEAMS
        ):
            summary = f"{team_data[0]['team']} vs {team_data[1]['team']}"
            live_matches.append({
                "matchId": match_id,
                "liveMatchSummary": summary,
                "team1": team_data[0],
                "team2": team_data[1]
            })

    link_recent = "https://www.cricbuzz.com/cricket-match/live-scores/recent-matches"
    source = requests.get(link_recent).text
    soup = BeautifulSoup(source, "lxml")

    recent_matches = []

    # Each match block
    match_blocks = soup.find_all("div", class_="cb-mtch-lst")

    for block in match_blocks:
        # Header: title, format, venue
        header = block.find("h3", class_="cb-lv-scr-mtch-hdr")
        header_link = header.find("a") if header else None

        href = header_link.get("href", "") if header_link else ""
        match_id = None
        if href.startswith("/live-cricket-scores/"):
            match_id = href.split("/")[2]

        # Date and time
        datetime_section = block.find("div", class_="text-gray")
        match_date, match_time, venue = "", "", ""
        if datetime_section:
            parts = datetime_section.get_text(" ", strip=True).split("•")
            if len(parts) >= 2:
                match_date = parts[0].strip()
            if "at" in datetime_section.text:
                venue = datetime_section.text.split("at")[-1].strip()

        # Teams + scores
        team_rows = block.find_all("div", class_=["cb-hmscg-bat-txt", "cb-hmscg-bwl-txt"])
        team_data = []
        for row in team_rows:
            name = row.find("div", class_="cb-ovr-flo cb-hmscg-tm-nm")
            score = row.find_all("div", class_="cb-ovr-flo")[-1] if row.find_all("div", class_="cb-ovr-flo") else None
            team_name = name.get_text(strip=True).upper() if name else ""
            if (team_name in ALLOWED_TEAMS) or DISABLE_FILTER_ALLOWED_TEAMS:
                team_data.append({
                    "team": team_name,
                    "score": score.get_text(strip=True) if score else ""
                })

        # Match result
        result = block.find("div", class_="cb-text-complete")
        result_text = result.get_text(strip=True) if result else ""

        # Only keep if valid teams
        if len(team_data) == 2 and (
            (team_data[0]['team'] in ALLOWED_TEAMS or team_data[1]['team'] in                     ALLOWED_TEAMS)
            or DISABLE_FILTER_ALLOWED_TEAMS
        ):
            summary = f"{team_data[0]['team']} vs {team_data[1]['team']}"
            recent_matches.append({
                "matchId": match_id,
                "date": match_date,
                "matchSummary": summary,
                "team1": team_data[0],
                "team2": team_data[1],
                "result": result_text
            })

    all_output = ({
        "upcoming_matches": upcoming_matches,
        "live_matches": live_matches,
        "recent_matches": recent_matches
    })

    return with_cache(all_output, "no-store, no-cache, must-revalidate, max-age=0")


@app.route('/schedule')
def schedule():
    link = f"https://www.cricbuzz.com/cricket-schedule/upcoming-series/international"
    source = requests.get(link).text
    soup = BeautifulSoup(source, "lxml")

    upcoming_matches = []

    # Each match container
    match_containers = soup.find_all("div", itemscope=True, itemtype="http://schema.org/SportsEvent")

    for match in match_containers:
        # Match title
        title_tag = match.find("a")
        match_title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract teams and remaining details
        team1, team2, details = "", "", ""
        if "," in match_title:
            teams_part, details = match_title.split(",", 1)
            teams = teams_part.split(" vs ")
            if len(teams) == 2:
                # Convert to short codes if in allowed teams
                team1_full = teams[0].strip()
                team2_full = teams[1].strip()
                team1_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team1_full), "")
                team2_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team2_full), "")
                if team1_code and team2_code:
                    team1 = team1_code
                    team2 = team2_code
            details = details.strip()
        else:
            if " vs " in match_title:
                teams = match_title.split(" vs ")
                if len(teams) == 2:
                    team1_full = teams[0].strip()
                    team2_full = teams[1].strip()
                    team1_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team1_full), "")
                    team2_code = next((k for k, v in ALLOWED_TEAMS.items() if v == team2_full), "")
                    if team1_code and team2_code:
                        team1 = team1_code
                        team2 = team2_code

        # Skip if teams not allowed
        if not team1 or not team2:
            continue

        # Match date
        date_span = match.find("span", itemprop="startDate")
        match_date = date_span["content"].strip() if date_span and "content" in date_span.attrs else ""

        # Match time
        time_span = match.find("span", class_="schedule-date")
        match_time = time_span.get_text(strip=True) if time_span else ""

        upcoming_matches.append({
            "team1": team1,
            "team2": team2,
            "details": details,
            "date": match_date,
            "time": match_time
        })

    # Schedule → long cache (e.g. 6 hours)
    return with_cache(upcoming_matches, "public, max-age=21600")  # 6 * 3600

@app.route('/recent')
def recent_matches():
    link = "https://www.cricbuzz.com/cricket-match/live-scores/recent-matches"
    source = requests.get(link).text
    soup = BeautifulSoup(source, "lxml")

    recent_matches = []

    # Each match block
    match_blocks = soup.find_all("div", class_="cb-mtch-lst")

    for block in match_blocks:
        # Header: title, format, venue
        header = block.find("h3", class_="cb-lv-scr-mtch-hdr")
        header_link = header.find("a") if header else None

        href = header_link.get("href", "") if header_link else ""
        match_id = None
        if href.startswith("/live-cricket-scores/"):
            match_id = href.split("/")[2]

        # Date and time
        datetime_section = block.find("div", class_="text-gray")
        match_date, match_time, venue = "", "", ""
        if datetime_section:
            parts = datetime_section.get_text(" ", strip=True).split("•")
            if len(parts) >= 2:
                match_date = parts[0].strip()
            if "at" in datetime_section.text:
                venue = datetime_section.text.split("at")[-1].strip()

        # Teams + scores
        team_rows = block.find_all("div", class_=["cb-hmscg-bat-txt", "cb-hmscg-bwl-txt"])
        team_data = []
        for row in team_rows:
            name = row.find("div", class_="cb-ovr-flo cb-hmscg-tm-nm")
            score = row.find_all("div", class_="cb-ovr-flo")[-1] if row.find_all("div", class_="cb-ovr-flo") else None
            team_name = name.get_text(strip=True).upper() if name else ""
            if (team_name in ALLOWED_TEAMS) or DISABLE_FILTER_ALLOWED_TEAMS:
                team_data.append({
                    "team": team_name,
                    "score": score.get_text(strip=True) if score else ""
                })

        # Match result
        result = block.find("div", class_="cb-text-complete")
        result_text = result.get_text(strip=True) if result else ""

        # Only keep if valid teams
        if len(team_data) == 2 and (
            (team_data[0]['team'] in ALLOWED_TEAMS or team_data[1]['team'] in                     ALLOWED_TEAMS)
            or DISABLE_FILTER_ALLOWED_TEAMS
        ):
            summary = f"{team_data[0]['team']} vs {team_data[1]['team']}"
            recent_matches.append({
                "matchId": match_id,
                "date": match_date,
                "matchSummary": summary,
                "team1": team_data[0],
                "team2": team_data[1],
                "result": result_text
            })

    # Recent → medium cache (e.g. 120 seconds)
    return with_cache(recent_matches, "public, max-age=120")

@app.route('/live')
def live_matches():
    link = "https://www.cricbuzz.com/cricket-match/live-scores"
    source = requests.get(link).text
    page = BeautifulSoup(source, "lxml")

    # Container that holds all matches
    page = page.find("div", class_="cb-col cb-col-100 cb-bg-white")
    matches = page.find_all("a", class_="cb-lv-scrs-well")

    live_matches = []

    for m in matches:
        # extract matchId from href
        href = m.get("href", "")
        match_id = None
        if href.startswith("/live-cricket-scores/"):
            match_id = href.split("/")[2]  # second part is ID

        # Get team rows (batting + bowling team)
        team_rows = m.find_all("div", class_=["cb-hmscg-bat-txt", "cb-hmscg-bwl-txt"])

        team_data = []
        for row in team_rows:
            name = row.find("div", class_="cb-ovr-flo cb-hmscg-tm-nm")
            score = row.find_all("div", class_="cb-ovr-flo")[-1]  # last div is usually the score
            team_name = name.get_text(strip=True).upper() if name else ""

            team_data.append({
                "team": team_name,
                "score": score.get_text(strip=True) if score else ""
            })

        # Only keep matches where both teams are in allowed list
            # Only keep if valid teams
        if len(team_data) == 2 and (
            (team_data[0]['team'] in ALLOWED_TEAMS or team_data[1]['team'] in                     ALLOWED_TEAMS)
            or DISABLE_FILTER_ALLOWED_TEAMS
        ):
            summary = f"{team_data[0]['team']} vs {team_data[1]['team']}"
            live_matches.append({
                "matchId": match_id,
                "liveMatchSummary": summary,
                "team1": team_data[0],
                "team2": team_data[1]
            })

    return with_cache(live_matches, "no-store, no-cache, must-revalidate, max-age=0")


@app.route("/match/<match_id>", methods=["GET"])
def match_details(match_id):
    try:
        # Fetch the HTML content
        URL = f"https://www.cricbuzz.com/live-cricket-scores/{match_id}"
        response = requests.get(URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Initialize a dictionary with all keys to ensure consistent JSON output
        result = {
            "status": None,
            "player_of_the_match": None,
            "batsmen": [],
            "bowlers": []
        }
        # Attempt to parse live match details
        # We check for the presence of elements that are only in a live match page
        batsmen_div = soup.find("div", class_="cb-min-inf", ng_if=lambda x: x and "batsman" in x)
        if not batsmen_div:
            batsmen_div = soup.find("div", class_="cb-min-inf cb-col-100")

        # Check if live match parsing is possible
        if batsmen_div:
            # Parse Batsmen
            for row in batsmen_div.find_all("div", class_="cb-min-itm-rw"):
                cols = row.find_all("div")
                if len(cols) < 6:
                    continue
                batsman = {
                    "name": cols[0].text.strip().replace("*",""),
                    "runs": cols[1].text.strip(),
                    "balls": cols[2].text.strip(),
                    "fours": cols[3].text.strip(),
                    "sixes": cols[4].text.strip(),
                    "strike_rate": cols[5].text.strip()
                }
                result["batsmen"].append(batsman)

            # Parse Bowlers
            bowlers_divs = soup.find_all("div", class_="cb-min-inf cb-col-100")
            if len(bowlers_divs) > 1:
                bowlers_div = bowlers_divs[1]
                for row in bowlers_div.find_all("div", class_="cb-min-itm-rw"):
                    cols = row.find_all("div")
                    if len(cols) < 6:
                        continue
                    bowler = {
                        "name": cols[0].text.strip().replace("*",""),
                        "overs": cols[1].text.strip(),
                        "maidens": cols[2].text.strip(),
                        "runs": cols[3].text.strip(),
                        "wickets": cols[4].text.strip(),
                        "econ": cols[5].text.strip()
                    }
                    result["bowlers"].append(bowler)
        else:
            # If live match elements are not found, assume the match is complete
            complete_div = soup.find("div", class_="cb-min-comp")
            if complete_div:
                # Find the match status
                status_element = complete_div.find("div", class_="cb-min-stts")
                result["status"] = status_element.text.strip() if status_element else "Status not found."

                # Find the Player of the Match
                mom_element = complete_div.find("div", class_="cb-mom-itm")
                if mom_element:
                    mom_link = mom_element.find("a", class_="cb-link-undrln")
                    if mom_link:
                        result["player_of_the_match"] = mom_link.text.strip()

        # Match Heading
        heading_tag = soup.select_one("h1.cb-nav-hdr")
        if heading_tag:
            full_heading = heading_tag.get_text(strip=True)

            # Split into title and extra part
            if " - " in full_heading:
                parts = full_heading.split(" - ", 1)
                result["match_title"] = parts[0]
            else:
                result["match_title"] = full_heading

        # Match status
        bat_row = soup.select_one("div.cb-min-bat-rw")
        if bat_row:
            # Look for the next sibling <div> whose class starts with "cb-text-"
            next_div = bat_row.find_next_sibling("div")
            if next_div and next_div.get("class"):
                for cls in next_div.get("class"):
                    if cls.startswith("cb-text-"):
                        result["Livestatus"] = next_div.get_text(strip=True)
                        break

        return with_cache(result, "no-store, no-cache, must-revalidate, max-age=0")

    except Exception as e:
        # Catch any unexpected errors during the request or parsing
        return jsonify({"error": str(e)}), 500

@app.route('/')
def website():
    return "OK"

if __name__ =="__main__":
    app.run(debug=True)


























