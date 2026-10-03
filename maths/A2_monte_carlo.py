import numpy as np
import scipy as scipy
from scipy.stats import norm
import pandas as pd
from optimiser import df

#print(df.head())
#print(df.columns)

# For each project, calculate the critical threshold
crit_threshold = norm.ppf(df["q"])
df["crit_threshold"] = crit_threshold

#print(df[["risk_rating", "q", "crit_threshold"]].head())

# Identify the unique categories, looking across country, developer, registry, project_type
# for any single scenario, we need one random normal draw per unique country, one per unique developer, etc
groups = ["country", "developer", "registry", "project_type"]

for group in groups:
    uniques = df[group].unique()
    #print(f"{group} ({len(uniques)} unique):" , uniques[:5])

# Prepare for simulation, creating a mapping from each unique category to an integer ID
for group in groups:
    df[f"{group}_id"] = df[group].astype("category").cat.codes

# ----------------------------------------------------------------------------------------------------------------

# Scale to N scenarios & evaluate portfolio
# Returns delivered_matrix with shape (n_scenarios, n_projects)
# seed fixes the random draws so runs are reproducible (use different seeds for train/test)

def simulate_copula(df, n_scenarios=5000,
                    beta_country=0.25, beta_developer=0.20,
                    beta_registry=0.15, beta_project_type=0.30,
                    seed=0):

    rng = np.random.default_rng(seed)
    n_projects = len(df)

    country_ids = df["country_id"].values
    dev_ids = df["developer_id"].values
    reg_ids = df["registry_id"].values
    type_ids = df["project_type_id"].values

    crit_thresholds = df["crit_threshold"].values
    loss_fractions = df["L"].values
    
    # 2. Category counts:
    n_c = country_ids.max() + 1
    n_d = dev_ids.max() + 1
    n_r = reg_ids.max() + 1
    n_t = type_ids.max() + 1

    # Precompute idiosyncratic weight
    sum_beta_sq = (beta_project_type**2 + beta_country**2 + 
                   beta_developer**2 + beta_registry**2)
    idiosyncratic_weight = np.sqrt(1.0 - sum_beta_sq)

    # 3. Initialize the matrix before the loop:
    delivered_matrix = np.zeros((n_scenarios, n_projects), dtype=np.float32)

    for s in range(n_scenarios):
        # Draw group shocks for this scenario
        f_c = rng.standard_normal(n_c)[country_ids]
        f_d = rng.standard_normal(n_d)[dev_ids]
        f_r = rng.standard_normal(n_r)[reg_ids]
        f_t = rng.standard_normal(n_t)[type_ids]
        
        # Draw idiosyncratic project noise
        eps = rng.standard_normal(n_projects)
        
        # Assemble Z
        Z = (beta_country * f_c + 
             beta_developer * f_d + 
             beta_registry * f_r + 
             beta_project_type * f_t + 
             idiosyncratic_weight * eps)
        
        # Evaluate survival: (1 - L) if failed, else 1.0
        failed = Z < crit_thresholds
        delivered_matrix[s] = np.where(failed, 1.0 - loss_fractions, 1.0)
    
    return delivered_matrix


# ----------------------------------------------------------------------------------------------------------------
# Everything below only runs when this file is run directly, not when imported (e.g. by A3)

if __name__ == "__main__":

    # Number of unique countries
    n_countries = df["country"].nunique()

    # Draw 1 random standard normal number for each unique country
    country_shocks = np.random.standard_normal(n_countries)

    # Now each project can look up its country shock using the integer id from above
    f_country = country_shocks[df["country_id"].values]

    # ------------------------------------------------------------------------------------------------------------

    # Generating shocks for all 4 groups

    # 1. Number of unique categories in each group
    n_country = df["country"].nunique()
    n_developers = df["developer"].nunique()
    n_registries = df["registry"].nunique()
    n_project_types = df["project_type"].nunique()

    # 2. Draw one shared standard normal shock per unique country
    f_country_draws = np.random.standard_normal(n_country)
    f_developer_draws = np.random.standard_normal(n_developers)
    f_registry_draws = np.random.standard_normal(n_registries)
    f_project_type_draws = np.random.standard_normal(n_project_types)

    # 3. Map the shocks onto every project row in the dataframe
    f_country = f_country_draws[df["country_id"]]
    f_developer = f_developer_draws[df["developer_id"]]
    f_registry = f_registry_draws[df["registry_id"]]
    f_project_type = f_project_type_draws[df["project_type_id"]]

    # Test
    country_shocks = np.random.standard_normal(df["country"].nunique())
    f_country = country_shocks[df["country_id"].values]
    #print("Country shock for first 5 projects:")
    #print(f_country[:5])

    # ------------------------------------------------------------------------------------------------------------

    # Assemble Scenario & Evaluate Survival

    # Draw project's own private noise
    epsilon = np.random.standard_normal(len(df))

    beta_project_type = 0.30 #technology/methodology risk
    beta_country = 0.25 # geopolitical risk
    beta_developer = 0.20 # management failure or bankruptcy 
    beta_registry = 0.15 # verification body rule changes

    # Total shared variance
    sum_beta_sq = (beta_project_type**2 + beta_country**2 + 
                   beta_developer**2 + beta_registry**2)

    idiosyncratic_weight = np.sqrt(1.0 - sum_beta_sq)

    # ------------------------------------------------------------------------------------------------------------

    # Assemble the health score (Z) for every project

    Z = (beta_country * f_country +
         beta_developer * f_developer +
         beta_registry * f_registry +
         beta_project_type * f_project_type +
         idiosyncratic_weight * epsilon)

    # Evaluate Survival & Delivery Fraction
    # Compare each project's score Z_i against its crit_threshold
    # If Z_i < threshold, project fails in this scenario (delivered fraction = 1 - L_i)
    # If Z_i >= threshold, project survives (delivered fraction = 1.0)

    failed = Z < df["crit_threshold"]
    delivered_fraction = np.where(failed, 1.0 - df["L"], 1.0)

    #print(f"Total projects: {len(df)}")
    #print(f"Failed projects in this scenario: {failed.sum()} ({failed.mean():.1%})")
    #print(f"Average delivered fraction: {delivered_fraction.mean():.2%}")

    # ------------------------------------------------------------------------------------------------------------

    from A1_knapsacking import greedy_portfolio

    # 1. Generate the portfolio from Algorithm 1
    portfolio = greedy_portfolio(df, target=100_000, budget=1_000_000)
    print(f"A1 Portfolio bought from {len(portfolio)} projects for ${portfolio['cost'].sum():,.2f}")

    # 2. Map tonnes bought back to the full dataset (0 for projects not bought)
    bought_map = portfolio.set_index("credit_id")["tonnes_bought"]
    purchased_vector = df["credit_id"].map(bought_map).fillna(0).values

    # 3. Run the 5,000 Monte Carlo scenarios
    delivery_matrix = simulate_copula(df, n_scenarios=5000, seed=0)

    # 4. Multiply delivery rates by tonnes purchased (Matrix multiplication: 5000x4355 @ 4355 -> 5000 deliveries)
    scenario_deliveries = delivery_matrix @ purchased_vector

    # CVaR 5%: average delivery across the worst 5% of scenarios (what Algorithm 3 constrains)
    worst_5pct = np.sort(scenario_deliveries)[: int(0.05 * len(scenario_deliveries))]

    # 5. Display the Risk Analysis!
    target = 100_000
    print("\n" + "="*50)
    print("     MONTE CARLO STRESS TEST RESULTS (5,000 SCENARIOS)")
    print("="*50)
    print(f"Target:                   {target:,.0f} tonnes")
    print(f"Mean Expected Delivery:   {scenario_deliveries.mean():,.0f} tonnes")
    print(f"Worst Case (Min):         {scenario_deliveries.min():,.0f} tonnes")
    print(f"P5 (Value-at-Risk 5%):    {np.percentile(scenario_deliveries, 5):,.0f} tonnes")
    print(f"P1 (Extreme Tail 1%):     {np.percentile(scenario_deliveries, 1):,.0f} tonnes")
    print(f"CVaR 5% (worst-5% avg):   {worst_5pct.mean():,.0f} tonnes")
    print(f"Probability of Shortfall: {(scenario_deliveries < target).mean():.1%}")
    print("="*50)