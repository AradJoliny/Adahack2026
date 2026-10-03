import csv
import io
import os

from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__, template_folder="htmlpages")

RISK_LEVELS = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.csv")

# Abstract CSV schema: canonical field -> accepted header names (lowercase).
# Final CSV columns are not settled, so extend these lists as needed.
COLUMN_ALIASES = {
    "name": ["project name", "project", "name"],
    "status": ["status"],
    "type": ["project type", "type"],
    "region": ["region"],
    "country": ["country"],
    "developer": ["developer"],
    "vintage": ["vintage year", "vintage"],
    "price": ["price per tonne", "price", "price_per_tonne"],
    "risk": ["risk", "risk level"],
    "tonnes": ["tonnes", "tonnes chosen", "tonnes selected", "quantity", "amount"],
}
NUMERIC_FIELDS = {"price", "tonnes"}


def _to_number(value):
  try:
    return float(str(value).replace("$", "").replace(",", "").strip())
  except ValueError:
    return 0.0


def parse_investments(csv_text):
  """Turns CSV text into a list of normalised investment dicts."""
  reader = csv.DictReader(io.StringIO(csv_text))
  lookup = {}
  for header in reader.fieldnames or []:
    for field, aliases in COLUMN_ALIASES.items():
      if header.strip().lower() in aliases:
        lookup[field] = header
  rows = []
  for raw in reader:
    row = {}
    for field in COLUMN_ALIASES:
      value = raw.get(lookup[field], "") if field in lookup else ""
      row[field] = _to_number(value) if field in NUMERIC_FIELDS else (value or "").strip()
    row["invested"] = row["price"] * row["tonnes"]
    rows.append(row)
  return rows


def load_investments():
  """Source of the chosen-investments CSV. Currently a sample file."""
  with open(SAMPLE_CSV, newline="", encoding="utf-8") as f:
    return parse_investments(f.read())


@app.route("/favicon.ico")
def favicon():
  return send_from_directory(app.static_folder, "favicon.svg", mimetype="image/svg+xml")


# 1. Start page
@app.route("/")
def start():
  return render_template("start.html")


# 2. Risk selection page
@app.route("/risk")
def risk():
  return render_template("risk.html")


# 3. Carbon portfolio viewer
@app.route("/viewer")
def viewer():
  level = request.args.get("risk", 3, type=int)
  if level not in RISK_LEVELS:
    level = 3
  return render_template(
      "viewer.html",
      risk_level=level,
      risk_name=RISK_LEVELS[level],
      investments=load_investments(),
  )


if __name__ == "__main__":
  app.run(debug=True, port=5000)
