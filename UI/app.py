import csv
import io
import json
import os

from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__, template_folder="htmlpages")

RISK_LEVELS = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
LEVEL_KEY_MAP = {1: "very_low", 2: "low", 3: "medium", 4: "high", 5: "very_high"}

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.csv")

# Abstract CSV schema: canonical field -> accepted header names.
COLUMN_ALIASES = {
    "name": ["project name", "project_name", "project", "name", "project title", "title"],
    "status": ["status", "project status", "stage"],
    "type": ["project type", "project_type", "type", "category"],
    "region": ["region", "continent", "area"],
    "country": ["country", "nation", "location"],
    "developer": ["developer", "proponent", "owner"],
    "vintage": ["vintage year", "vintage_year", "vintage", "year"],
    "price": ["price per tonne", "price_per_tonne", "price", "price_usd_per_t", "cost per tonne"],
    "risk": ["risk", "risk level", "risk_rating", "risk score"],
    "tonnes": ["tonnes", "tonnes chosen", "tonnes_chosen", "tonnes selected", "tonnes bought", "tonnes_bought", "quantity", "amount"],
}
NUMERIC_FIELDS = {"price", "tonnes"}


def _norm_header(h):
  import re
  return re.sub(r"[^a-z0-9]+", " ", str(h).lower()).strip()


def _to_number(value):
  try:
    return float(str(value).replace("$", "").replace(",", "").strip())
  except ValueError:
    return 0.0


def parse_investments(csv_text):
  """Turns CSV text into a list of normalised investment dicts."""
  reader = csv.DictReader(io.StringIO(csv_text))
  lookup = {}
  norm_aliases = {
      field: [_norm_header(a) for a in aliases]
      for field, aliases in COLUMN_ALIASES.items()
  }
  for header in reader.fieldnames or []:
    norm_h = _norm_header(header)
    for field, aliases in norm_aliases.items():
      if norm_h in aliases:
        lookup[field] = header
        break

  rows = []
  for raw in reader:
    row = {}
    for field in COLUMN_ALIASES:
      value = raw.get(lookup[field], "") if field in lookup else ""
      row[field] = _to_number(value) if field in NUMERIC_FIELDS else (value or "").strip()
    total_spend = _to_number(raw.get("total_spend", 0.0))
    row["invested"] = total_spend if total_spend > 0 else (row["price"] * row["tonnes"])
    rows.append(row)
  return rows


def load_investments(level=3):
  """Source of the chosen-investments CSV. Loads optimised portfolio if available."""
  key = LEVEL_KEY_MAP.get(level, "medium")
  optimised_csv = os.path.join(
      os.path.dirname(__file__), "carbon-portfolio-viewer", "sample_data", f"portfolio_{key}.csv"
  )
  if os.path.exists(optimised_csv):
    with open(optimised_csv, newline="", encoding="utf-8") as f:
      return parse_investments(f.read())
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
  metrics = None
  key = LEVEL_KEY_MAP.get(level, "medium")
  metrics_file = os.path.join(
      os.path.dirname(__file__), "carbon-portfolio-viewer", "sample_data", "portfolios.json"
  )
  if os.path.exists(metrics_file):
    try:
      with open(metrics_file, encoding="utf-8") as f:
        data = json.load(f)
        if key in data and "metrics" in data[key]:
          metrics = data[key]["metrics"]
    except Exception:
      pass
  return render_template(
      "viewer.html",
      risk_level=level,
      risk_name=RISK_LEVELS[level],
      risk_metrics=metrics,
      investments=load_investments(level),
  )


if __name__ == "__main__":
  app.run(debug=True, port=5000)
