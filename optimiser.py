import numpy as np
import pandas as pd

# risk ratings

df = pd.read_csv("credits.csv", sep="\t", thousands=",")

# base failure rates 
base = {"AAA": 0.01, "AA": 0.02, "A": 0.04, "BBB": 0.07,
        "BB": 0.12, "B": 0.20, "CCC": 0.35}
# failure rates if raing N/A
unrated = 0.15

# base (r_i ): look up each ratings failure rate
def base_failure(rating):
    return rating.map(base).fillna(unrated)

# failure probability (q_i) - calculate each rows failure probability 
def failure_probability(base, had_reversal):
    return np.minimum(1.0, base * np.where(had_reversal, 1.5, 1.0))

# Loss fraction if it fails
def loss_fraction(has_buffer_pool):
    return np.where(has_buffer_pool, 0.5, 1.0)

# Expected tonnes delivery per tonne bought
def expected_deliery(fp, lf):
    return (1 - fp * lf) 

# p_i / m_i: price per expected tonne delivered (Algorithm 1 sort key)
def effective_price(p, m):
    return p / m


# Expected delivery per tonne bought: mᵢ = 1 − qᵢ·Lᵢ
# Effective price per expected tonne: eᵢ = pᵢ / mᵢ.
exp_deli_per_tonne = 
