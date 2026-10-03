import os
print(os.getcwd())
print(os.listdir())

import pandas as pd
from optimiser import df

# Algorithm one -- buy the cheapest expected tonnes first until target is met
def greedy_portfolio(df, target=100_000, budget=1_000_000):
    ranked = df.sortvalues("effective_price")
    remaining = target
    rows = []

    for _, r in ranked.iterrows():
        if remaining <= 0:
            break
        max_expected = r['m'] * r['available_tonnes']
        take = min(remaining, max_expected)
        rows.append({
            "credit_id": r["credit_id"],
            "project_name": r["project_name"],
            "tonnes_bought": tonnes,
            "cost": tonnes * r["price_usd_per_t"],
            "expected_delivered": take,
        })
        remaining -= take

    portfolio = pd.dataframe(rows)
    if remaining > 0:
        raise ValueError("Not enough supply to reach the target")
    if portfolio["cost"].sum() > budget:
        raise ValueError("Cheapest portfolio is over the budget")
    return portfolio

if __name__ == "__main__":
    port = greedy_portfolio(df)
    print(port)
    print(f"Total cost: ${port['cost'].sum():,.0f}")
    print(f"Tonnes bought: {port['tonnes_bought'].sum():,.0f}")
    print(f"Expected delivered: {port['expected_delivered'].sum():,.0f}")

