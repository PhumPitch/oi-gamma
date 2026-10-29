"""Black-Scholes greeks (vectorized: inputs can be numpy arrays or pandas Series)."""
import numpy as np
from scipy.stats import norm


def d1_d2(S, K, T, sigma, r=0.0, q=0.0):
    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * sqrt_t)
    return d1, d1 - sigma * sqrt_t


def gamma(S, K, T, sigma, r=0.0, q=0.0):
    d1, _ = d1_d2(S, K, T, sigma, r, q)
    return np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))


def vanna(S, K, T, sigma, r=0.0, q=0.0):
    """dDelta/dSigma (same for calls and puts)."""
    d1, d2 = d1_d2(S, K, T, sigma, r, q)
    return -np.exp(-q * T) * norm.pdf(d1) * d2 / sigma
