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
    print(f"{group} ({len(uniques)} unique):" , uniques[:5])