"""
Builds site/data/zips.js — which congressional district(s) each ZIP code is in.

Source: the Census Bureau's relationship file between 119th Congress districts and
ZIP Code Tabulation Areas (ZCTAs). District lines are fixed for the whole Congress, so
this only needs to be rerun when CONGRESS changes in build_data.py; it is not part of
the nightly update.

Usage:
  python build_zips.py

ZCTAs are the Census Bureau's approximation of ZIP codes. ZIP codes used only for PO boxes
or a single building have no ZCTA and are not in the output.
"""
import csv
import io
import json

from build_data import CONGRESS, ROOT, fetch

URL = (f"https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/"
       f"tab20_cd{CONGRESS}20_zcta520_natl.txt")
OUT = ROOT / "site" / "data" / "zips.js"

# The district and ZIP boundaries don't line up exactly, so the file lists slivers where a
# ZIP barely crosses a district line. Ignore overlaps smaller than this share of the ZIP.
MIN_SHARE = 0.01

FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT",
    "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL",
    "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV",
    "55": "WI", "56": "WY", "60": "AS", "66": "GU", "69": "MP", "72": "PR", "78": "VI",
}
# District codes: 00 = at-large, 98 = delegate. Both are district 0 in the roster.
AT_LARGE = {"00", "98"}


def main():
    print("Loading Census ZIP-to-district file…")
    text = fetch(URL).lstrip(chr(0xFEFF))  # the file starts with a byte-order mark
    overlaps = {}  # zip -> {"OH3": area}
    for row in csv.DictReader(io.StringIO(text), delimiter="|"):
        zcta, geoid = row["GEOID_ZCTA5_20"], row[f"GEOID_CD{CONGRESS}_20"]
        state, cd = FIPS.get(geoid[:2]), geoid[2:]
        if not zcta or not state or not cd.isdigit():
            continue  # water-only areas and district parts outside any ZIP
        district = f"{state}{0 if cd in AT_LARGE else int(cd)}"
        area = int(row["AREALAND_PART"]) + int(row["AREAWATER_PART"])
        parts = overlaps.setdefault(zcta, {})
        parts[district] = parts.get(district, 0) + area

    zips = {}
    for zcta in sorted(overlaps):
        parts = sorted(overlaps[zcta].items(), key=lambda p: -p[1])  # biggest overlap first
        total = sum(a for _, a in parts) or 1
        keep = [d for i, (d, a) in enumerate(parts) if i == 0 or a / total >= MIN_SHARE]
        zips[zcta] = " ".join(keep)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.ZIP_DISTRICTS = " + json.dumps(zips, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    split = sum(1 for v in zips.values() if " " in v)
    print(f"  {len(zips)} ZIP codes, {split} in more than one district")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
