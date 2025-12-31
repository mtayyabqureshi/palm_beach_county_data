import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

st.set_page_config(page_title="Listing Address → Property Details", layout="wide")

# ---------------------------
# Simple Debug Logger
# ---------------------------

log_buffer = []

def log(msg):
    msg = str(msg)
    print(msg)
    log_buffer.append(msg)
    if "log_placeholder" in st.session_state:
        st.session_state.log_placeholder.text("\n".join(log_buffer))



# ---------------------------
# Helpers
# ---------------------------

def is_empty_address(address):
    return address is None or (isinstance(address, float)) or address.strip() == ""


def is_empty_name(name):
    return name is None or (isinstance(name, float)) or name.strip() == ""


def normalize(text):
    return " ".join(text.upper().split())


# ---------------------------
# API helpers
# ---------------------------

def build_payload(search_text):
    return {
        "inputName": "addresssearch",
        "searchLimit": "20",
        "uID": "89540f28-8b9a-4aed-b609-72529f86a3ca",
        "version": 2,
        "removeZip": True,
        "papaVersion": True,
        "removeChar": "_",
        "removeSpace": True,
        "papaVariance": False,
        "searchText": search_text,
    }


def api_call(value):
    log(f"API CALL → {value}")
    url = "https://maps.pbc.gov/giswebapi/anysearch"

    try:
        resp = requests.post(url, json=build_payload(value), timeout=20)
    except Exception as e:
        log(f"❌ API request failed: {e}")
        return None

    log(f"API STATUS {resp.status_code}")

    if resp.status_code != 200:
        log("❌ API non-200 response")
        return None

    return resp.json()


def get_pcn_number(address, data):
    address_norm = normalize(address)

    for item in data or []:
        search_term = item.get("searchTerm", "")
        if normalize(search_term) == address_norm:
            return item.get("PCN")

    return None


def get_pcn(address):
    if is_empty_address(address):
        return None

    data = api_call(address)
    return get_pcn_number(address, data)


# ---- name lookup support ----

def get_pcn_numbers_from_name(name, data):
    log(f"Matching PCNs for name: {name}")

    if not data or not name:
        return []

    current_name = name.strip().upper()
    pcns = []

    for item in data:
        search_term = item.get("searchTerm", "").upper()

        if current_name in search_term:
            pcn = str(item.get("PCN"))
            if pcn and pcn not in pcns:
                pcns.append(pcn)

    log(f"Matched PCNs: {pcns}")
    return pcns


def get_pcn_from_name(name):
    if is_empty_name(name):
        return []

    all_pcns = []

    for raw in name.split("|"):
        search_name = raw.strip()
        if not search_name:
            continue

        log(f"Searching by NAME: {search_name}")

        data = api_call(search_name)
        if not data:
            continue

        pcns = get_pcn_numbers_from_name(search_name, data)

        for pcn in pcns:
            if pcn not in all_pcns:
                all_pcns.append(pcn)

    log(f"ALL PCNs for name: {all_pcns}")
    return all_pcns


# ---------------------------
# Property Page Parsing
# ---------------------------

def get_property_details(pcn):
    if not pcn:
        return None

    url = "https://pbcpao.gov/Property/MapDetails"
    log(f"Fetching property page → {pcn}")

    try:
        resp = requests.get(url, params={"parcelId": pcn}, timeout=20)
    except Exception as e:
        log(f"❌ Property request failed: {e}")
        return None

    if resp.status_code == 200:
        return resp.text

    log(f"❌ Property HTML status {resp.status_code}")
    return None


def get_owners(soup):
    section = soup.find("div", class_="map-owners") or soup.find("div", class_="map-ownerinfo")
    if not section:
        log("Owners section NOT found")
        return None

    owners = [
        td.get_text(" ", strip=True)
        for td in section.find_all("td")
        if td.get_text(strip=True)
    ]

    log(f"Owners parsed: {owners}")
    return "; ".join(owners) if owners else None


def get_mailing_address(soup):
    for row in soup.find_all("tr"):
        label = row.find("td", class_="label")
        if label and label.get_text(strip=True) == "Mailing Address":
            value = row.find("td", class_="value")
            labels = [
                l.get_text(strip=True)
                for l in value.find_all("label")
                if l.get_text(strip=True)
            ]
            return ", ".join(labels) if labels else None
    return None


def get_location(soup):
    for row in soup.find_all("tr"):
        label = row.find("td", class_="label")
        if label and label.get_text(strip=True) == "Location":
            value = row.find("td", class_="value")
            label = value.find("label", id="lblLocation")
            return label.get_text(strip=True) if label else None
    return None


def parse_property_html(html):
    soup = BeautifulSoup(html, "html.parser")
    return {
        "Owner_Name": get_owners(soup),
        "Mailing_Address": get_mailing_address(soup),
        "Location_Address": get_location(soup),
    }


# ---------------------------
# Streamlit UI
# ---------------------------

st.title("Palm Beach County → Property Lookup (PCN + Property Details)")

uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

if uploaded:

    if uploaded.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    df.columns = df.columns.str.strip()

    st.subheader("Preview")
    st.dataframe(df.head())

    lookup_mode = None

    # detect input mode
    if "Property_Street_Address" in df.columns:
        lookup_mode = "address"
        log("Mode: ADDRESS lookup (Property_Street_Address present)")

        ordinal_map = {
            "First": "1st","Second": "2nd","Third": "3rd","Fourth": "4th",
            "Fifth": "5th","Sixth": "6th","Seventh": "7th","Eighth": "8th",
            "Ninth": "9th","Tenth": "10th","Eleventh": "11th","Twelfth": "12th",
            "Thirteenth": "13th","Fourteenth": "14th","Fifteenth": "15th",
            "Sixteenth": "16th","Seventeenth": "17th","Eighteenth": "18th",
            "Nineteenth": "19th","Twentieth": "20th"
        }

        pattern = re.compile(r"\b(" + "|".join(ordinal_map.keys()) + r")\b", re.IGNORECASE)

        def replace_ordinals(address):
            return pattern.sub(lambda m: ordinal_map[m.group(0).title()], address or "")

        df["Clean_Address"] = df["Property_Street_Address"].astype(str).apply(replace_ordinals)

        df["Full_Address"] = (
            df["Clean_Address"].str.strip() + ", "
            + df["Property_City"].str.strip() + " "
            + df["Property_Zip_Code"].astype(str)
        )

    elif "Reverse Name" in df.columns:
        lookup_mode = "name"
        log("Mode: NAME lookup (Reverse Name present)")

        df["Reverse Name"] = (
            df["Reverse Name"]
            .astype(str)
            .replace(r"\r?\n", " | ", regex=True)
            .str.strip()
        )

    else:
        lookup_mode = "address"
        log("Mode: ADDRESS lookup (fallback)")

        df["Full_Address"] = (
            df["Address"].str.strip() + ", "
            + df["City"].str.strip() + " "
            + df["Zip"].astype(str)
        )

    run = st.button("Search")

    if run:
        progress = st.progress(0)
        results = []

        for i, row in df.iterrows():
            log(f"\n--- ROW {i+1}/{len(df)} ---")

            # ADDRESS MODE
            if lookup_mode == "address":
                value = row["Full_Address"]
                log(f"Searching ADDRESS → {value}")
                pcns = [get_pcn(value)] if value else []

            # NAME MODE
            else:
                value = row["Reverse Name"]
                log(f"Searching NAME → {value}")
                pcns = get_pcn_from_name(value)

            log(f"PCNs returned: {pcns}")

            if not pcns:
                results.append({**row.to_dict(),
                    "PCN": None,
                    "Owner_Name": None,
                    "Mailing_Address": None,
                    "Location_Address": None,
                })
                progress.progress((i + 1) / len(df))
                continue

            # expand rows
            for pcn in pcns:
                html = get_property_details(pcn)
                details = parse_property_html(html) if html else {
                    "Owner_Name": None,
                    "Mailing_Address": None,
                    "Location_Address": None,
                }

                results.append({**row.to_dict(), "PCN": pcn, **details})

            progress.progress((i + 1) / len(df))

        result_df = pd.DataFrame(results)

        st.success("Search Completed!")
        st.subheader("Results")
        st.dataframe(result_df)

        st.download_button(
            "⬇️ Download results as CSV",
            data=result_df.to_csv(index=False),
            file_name=lookup_mode+"_final.csv",
            mime="text/csv",
        )

else:
    st.info("Upload a file to begin.")
