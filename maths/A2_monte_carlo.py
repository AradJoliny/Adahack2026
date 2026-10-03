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

# Number of unique countries
n_countries = df["country"].nunique()

# Draw 1 random standard normal number for each unique country
country_shocks = np.random.standard_normal(n_countries)

# Now each project can look up its country shock using the integer id from above
f_country = country_shocks[df["country_id"].values]

# ----------------------------------------------------------------------------------------------------------------

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
print("Country shock for first 5 projects:")
print(f_country[:5])
