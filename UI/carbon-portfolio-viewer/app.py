"""Carbon portfolio viewer - REST API + static front end.

Endpoints
  POST /api/portfolio   JSON body, one of:
                          {"csv": "<csv text>", "column_map": {...optional...}}
                          {"rows": [{...}, ...], "column_map": {...optional...}}
                        -> normalised records, column mapping and summary
  GET  /api/sample      the bundled sample portfolio (same response shape)
  GET  /api/schema      canonical fields the CSV adapter understands
"""
import json
from pathlib import Path

from flask import Flask, jsonify, request

from csv_adapter import FIELDS, REQUIRED, ParseResult, parse_csv_text, parse_rows

BASE = Path(__file__).parent
app = Flask(__name__, static_folder=str(BASE / "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


def summarise(result: ParseResult) -> dict:
    recs = result.records
    tonnes = sum(r["tonnes_chosen"] for r in recs)
    spend = sum(r["total_spend"] for r in recs)
    return {
        "records": recs,
        "mapping": result.mapping,
        "unmapped_headers": result.unmapped_headers,
        "warnings": result.warnings,
        "summary": {
            "project_count": len(recs),
            "total_tonnes": tonnes,
            "total_spend": round(spend, 2),
            "weighted_avg_price": round(spend / tonnes, 2) if tonnes else 0,
            "region_count": len({r["region"] for r in recs}),
        },
    }


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/schema")
def schema():
    return jsonify({"fields": {k: v[0] for k, v in FIELDS.items()}, "required": REQUIRED})


@app.post("/api/portfolio")
def portfolio():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Request body must be a JSON object"), 400
    column_map = body.get("column_map")
    try:
        if isinstance(body.get("csv"), str):
            result = parse_csv_text(body["csv"], column_map)
        elif isinstance(body.get("rows"), list):
            result = parse_rows(body["rows"], column_map=column_map)
        else:
            return jsonify(error="Provide either 'csv' (string) or 'rows' (array)"), 400
    except ValueError as e:
        return jsonify(error=str(e)), 422
    return jsonify(summarise(result))


@app.get("/api/sample")
def sample():
    text = (BASE / "sample_data" / "sample_portfolio.csv").read_text(encoding="utf-8")
    return jsonify(summarise(parse_csv_text(text)))


@app.get("/api/optimised")
def optimised():
    raw_risk = request.args.get("risk", "medium").strip().lower().replace(" ", "_").replace("-", "_")
    num_map = {"1": "very_low", "2": "low", "3": "medium", "4": "high", "5": "very_high"}
    risk = num_map.get(raw_risk, raw_risk)

    path = BASE / "sample_data" / f"portfolio_{risk}.csv"
    if not path.exists():
        return jsonify(error=f"Unknown risk level '{risk}'"), 400

    response = summarise(parse_csv_text(path.read_text(encoding="utf-8")))

    metrics_file = BASE / "sample_data" / "portfolios.json"
    if metrics_file.exists():
        try:
            risk_metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
            if risk in risk_metrics and "metrics" in risk_metrics[risk]:
                response["risk_metrics"] = risk_metrics[risk]["metrics"]
        except Exception:
            pass

    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
