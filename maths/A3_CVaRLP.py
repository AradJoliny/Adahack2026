import numpy as np
import pandas as pd
import cvxpy as cp
from optimiser import df
from A1_knapsacking import greedy_portfolio
from A2_monte_carlo import simulate_copula   # import before prefilter: adds crit_threshold and *_id columns to df

#Prefilter -- keep just the cheapest projects so the LP stays small
def prefilter(df, n_keep=400):
    return df.nsmallest(n_keep, "effective_price").reset_index(drop=True)

# Algorithm three - cheapest portfolio whose worst-alpha average delivery still hits target


def cvar_portfolio(cands, d, target=100_000, budget=1_000_000, alpha=0.05):
    n, N = d.shape
    price = cands["price_usd_per_t"].to_numpy()
    avail = cands["available_tonnes"].to_numpy()

    x = cp.Variable(n, nonneg=True)     # tonnes bought from each project
    zeta = cp.Variable()                # threshold: shortfall at the edge of the worst alpha
    u = cp.Variable(N, nonneg=True)     # how far each scenario's shortfall goes past zeta

    delivered = d.T @ x                 # tonnes delivered in each scenario
    constraints = [
        x <= avail,                                   # can't buy more than exists
        price @ x <= budget,                          # stay under $1M
        u >= target - delivered - zeta,               # u_k = shortfall beyond zeta
        zeta + cp.sum(u) / (alpha * N) <= 0,          # worst-alpha average shortfall <= 0
    ]
    problem = cp.Problem(cp.Minimize(price @ x), constraints)
    problem.solve()
    if problem.status != "optimal":
        raise ValueError(f"Solver status: {problem.status}")
    tonnes = np.where(x.value > 1.0, x.value, 0.0) # drop solver dust (anything under 1 tonne)
    return tonnes

# Evaluate any portfolio (tonnes per candidate) on a set of scenarios
def evaluate(tonnes, d, price, target=100_000, alpha=0.05):
    delivered = d.T @ tonnes
    n_worst = int(alpha * len(delivered))
    return {
        "cost": price @ tonnes,
        "projects": int((tonnes > 0).sum()),
        "mean_delivered": delivered.mean(),
        "p_shortfall": (delivered < target).mean(),
        "worst_alpha_avg": np.sort(delivered)[:n_worst].mean(),
    }

if __name__ == "__main__":
    cands = prefilter(df)
    price = cands["price_usd_per_t"].to_numpy()
    # Optimise on one set of scenarios, test on a fresh set
    # simulate_copula returns (scenarios, projects), so .T flips it to (projects, scenarios)
    d_train = simulate_copula(cands, n_scenarios=2_000, seed=1).T
    d_test = simulate_copula(cands, n_scenarios=5_000, seed=2).T
    cvar_tonnes = cvar_portfolio(cands, d_train)
    # Put greedy's purchases on the same candidate list for a fair comparison
    greedy = greedy_portfolio(df).set_index("credit_id")["tonnes_bought"]
    greedy_tonnes = cands["credit_id"].map(greedy).fillna(0).to_numpy()
    results = pd.DataFrame({
        "greedy": evaluate(greedy_tonnes, d_test, price),
        "cvar": evaluate(cvar_tonnes, d_test, price),
    })
    print(results.round(3))
    portfolio = cands.assign(tonnes_bought=cvar_tonnes)
    portfolio = portfolio[portfolio["tonnes_bought"] > 0]
    print(portfolio[["credit_id", "project_name", "country", "risk_rating",
                     "price_usd_per_t", "tonnes_bought"]])