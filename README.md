# Palm Beach County Property Lookup App

A Streamlit app that converts **listing addresses or owner names** into:

- PCN (Parcel Control Number)
- Owner Name
- Mailing Address
- Property Location Address

Supports Palm Beach County (PBC) property records using the public GIS API.

---

## Features

Upload **CSV or Excel**  
Search by **Address OR Owner Name**  
Expands results so **each PCN becomes its own row**  
Scrapes property details automatically  
Built-in debug logging panel  
Download results as CSV  

---

## How to Run Locally

```bash
git clone https://github.com/mtayyabqureshi/palm_beach_county_data.git
cd your-repo
pip install -r requirements.txt
streamlit run app.py
