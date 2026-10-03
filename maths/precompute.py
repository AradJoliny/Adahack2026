# Solve the CVaR portfolio once for each slider level and save results for the frontend
#   - portfolio_<level>.csv : the portfolio rows (read by the viewer's csv_adapter)
#   - portfolios.json       : risk metrics + pie/map summaries for every level
import json
from pathlib import Path
import numpy as np
from optimiser import df
from A2_monte_carlo import simulate_copula   # import before prefilter: adds crit_threshold and *_id columns
from A3_CVaRLP import prefilter, cvar_portfolio, evaluate


# Slider level -> alpha (size of the bad tail the portfolio must survive)
RISK_LEVELS = {"very_low": 0.01, "low": 0.025, "medium": 0.05, "high": 0.10, "very_high": 1.0}


# Final validated settings: 5,000 training scenarios, 104k target (4% out-of-sample safety margin)
N_TRAIN, N_TEST = 5_000, 5_000
TARGET = 104_000


# Where the viewer app reads its data
viewer_dir = Path(__file__).resolve().parent.parent / "UI" / "carbon-portfolio-viewer"
OUT_DIR = viewer_dir / "sample_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


cands = prefilter(df)
price = cands["price_usd_per_t"].to_numpy()
d_train = simulate_copula(cands, n_scenarios=N_TRAIN, seed=1).T
d_test = simulate_copula(cands, n_scenarios=N_TEST, seed=2).T


results = {}
for level, alpha in RISK_LEVELS.items():
   print(f"Solving {level} (alpha={alpha})...")
   tonnes = cvar_portfolio(cands, d_train, target=TARGET, alpha=alpha)
   metrics = evaluate(tonnes, d_test, price)            # always judged on real 100k, worst 5%
   bought = cands.assign(tonnes_bought=tonnes, cost=tonnes * price)
   bought = bought[bought["tonnes_bought"] > 0]


   # CSV for the viewer (column names to match csv_adapter canonical fields)
   export = bought.rename(columns={
       "tonnes_bought": "tonnes_chosen",
       "cost": "total_spend",
       "price_usd_per_t": "price_per_tonne",
       "risk_rating": "risk"
   })
   export[["credit_id", "project_name", "country", "region", "project_type", "risk",
           "price_per_tonne", "tonnes_chosen", "total_spend"]] \
       .round(2).to_csv(OUT_DIR / f"portfolio_{level}.csv", index=False)


   results[level] = {
       "alpha": alpha,
       "metrics": {k: float(v) for k, v in metrics.items()},
       "by_type": bought.groupby("project_type")["tonnes_bought"].sum().round(0).to_dict(),
       "by_country": bought.groupby("country")["tonnes_bought"].sum().round(0).to_dict(),
   }
   print(f"  cost ${metrics['cost']:,.0f}, {int(metrics['projects'])} projects, "
         f"worst-5% avg {metrics['worst_alpha_avg']:,.0f}")


(OUT_DIR / "portfolios.json").write_text(json.dumps(results, indent=2))
print(f"Saved to {OUT_DIR}")