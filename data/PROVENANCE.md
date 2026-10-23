# Provenance

readback recomputes nothing. Every table it can query is a file one of three portfolio builds
published at its v0.1.0 tag, fetched from GitHub and checked against the SHA-256 in
data/warehouses.lock.json. The lock records the tag, the commit, every file and its digest.

| Warehouse | Repository | Tag | What it is |
|---|---|---|---|
| doorstep | github.com/mekala27-45/doorstep | v0.1.0 | housing affordability over every U.S. metro, the marts, the eight chapter tables, the calculator marts and the CSV bundle |
| turnaround | github.com/mekala27-45/turnaround | v0.1.0 | every scheduled domestic flight since January 2015, summarized to the published marts, the eight chapter tables and the CSV bundle |
| ledger | github.com/mekala27-45/ledger | v0.1.0 | a fictional bank, Harborline, with its twelve functions, the metric layer, the model registry and the extracts |

## Terms of the data inside each warehouse

The code of all three builds and of readback is Apache 2.0. The data carries its own terms, as each
build states them, restated here:

- **doorstep.** The FHFA House Price Index, the American Community Survey, the Building Permits
  Survey and the Population Estimates of the Census Bureau, HUD Fair Market Rents and income limits,
  and the HMDA loan level data of the CFPB are public data of the United States government. The
  Freddie Mac Primary Mortgage Market Survey rates are used under Freddie Mac's terms of use, which
  ask for attribution. Metros are real; no household, borrower or address appears.
- **turnaround.** The Bureau of Transportation Statistics on time files and the FAA releasable
  aircraft registry are public domain; OurAirports is public domain; Open-Meteo weather is CC BY 4.0
  and is attributed on every surface. Carriers and airports are real; no traveler appears.
- **ledger.** Harborline Bank is fictional and its accounts, transactions and customers are
  generated. The customer and account identifiers in its published tables belong to generated
  records, not people. The public series beside it (New Jersey HMDA, CFPB complaint data, the FDIC
  directory and financials, BLS, FHFA, Treasury and Federal Reserve series) are public data.

> Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep (public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround (public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted before a model sees them. Every number is read back to the warehouse before it is shown. This is a portfolio demonstration, not financial, travel or lending advice.

## What was left out of the lock, and why

- doorstep's exports/csv/mart_metro_year.csv is the metro year mart written out for spreadsheet
  users; the parquet of the same table is locked, so the CSV would be a second copy.
- turnaround's exports/tableau files are the route month mart split by year for Tableau Public; the
  parquet of the same mart is locked.
- The data dictionaries and metric definitions of doorstep and turnaround are locked as documents
  the catalog reads, not as tables.
