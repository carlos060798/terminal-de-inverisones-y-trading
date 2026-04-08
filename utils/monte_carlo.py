"""
Monte Carlo Portfolio Stress Test Engine.
Runs N simulated paths of portfolio value using correlated random walks
based on historical return distributions and covariance structure.
"""
import numpy as np
import pandas as pd
import yfinance as yf


def run_monte_carlo(tickers: list, weights: list, total_value: float,
                    n_simulations: int = 1000, n_days: int = 252,
                    history_period: str = "2y") -> dict:
    """
    Execute Monte Carlo simulation on the portfolio.

    Returns dict with keys:
        - simulations: np.ndarray shape (n_simulations, n_days+1) of portfolio values
        - mean_path: np.ndarray of mean trajectory
        - p5, p25, p75, p95: percentile trajectories
        - var_95: VaR at 95% confidence (dollar loss)
        - cvar_95: CVaR (Expected Shortfall) at 95%
        - final_values: distribution of final portfolio values
        - stats: summary dict
    """
    if not tickers or not weights or total_value <= 0:
        return {"error": "Portafolio vacío o sin valor"}

    # Normalize weights
    w = np.array(weights, dtype=float)
    w = w / w.sum()

    # Download historical data
    try:
        data = yf.download(tickers, period=history_period, progress=False)["Close"]
        if isinstance(data, pd.Series):
            data = data.to_frame(name=tickers[0])
    except Exception as e:
        return {"error": f"Error descargando datos: {e}"}

    if data.empty or len(data) < 30:
        return {"error": "Datos históricos insuficientes"}

    # Clean: drop columns with all NaN, forward fill rest
    data = data.dropna(axis=1, how="all").ffill().dropna()

    # Filter tickers to those we actually have data for
    available = [t for t in tickers if t in data.columns]
    if len(available) < 1:
        return {"error": "Sin datos para los tickers del portafolio"}

    # Recompute weights for available tickers
    idx_available = [tickers.index(t) for t in available]
    w_avail = np.array([weights[i] for i in idx_available], dtype=float)
    w_avail = w_avail / w_avail.sum()

    prices = data[available]

    # Log returns
    log_returns = np.log(prices / prices.shift(1)).dropna()

    if len(log_returns) < 20:
        return {"error": "Insuficientes retornos históricos"}

    # Mean returns and covariance
    mean_returns = log_returns.mean().values  # daily
    cov_matrix = log_returns.cov().values     # daily covariance

    # --- Monte Carlo Simulation ---
    np.random.seed(42)  # Reproducible
    simulations = np.zeros((n_simulations, n_days + 1))
    simulations[:, 0] = total_value

    # Cholesky decomposition for correlated random walks
    try:
        L = np.linalg.cholesky(cov_matrix)
    except np.linalg.LinAlgError:
        # If not positive definite, add small diagonal
        cov_matrix += np.eye(len(cov_matrix)) * 1e-8
        L = np.linalg.cholesky(cov_matrix)

    for day in range(1, n_days + 1):
        # Generate correlated random returns
        Z = np.random.standard_normal((n_simulations, len(available)))
        correlated_returns = Z @ L.T  # (n_sim, n_assets)

        # Portfolio daily return = weighted sum of asset returns
        daily_returns = correlated_returns + mean_returns  # drift + random
        portfolio_returns = daily_returns @ w_avail  # weighted

        # Update portfolio value
        simulations[:, day] = simulations[:, day - 1] * np.exp(portfolio_returns)

    # --- Statistics ---
    final_values = simulations[:, -1]
    mean_path = np.mean(simulations, axis=0)
    p5 = np.percentile(simulations, 5, axis=0)
    p25 = np.percentile(simulations, 25, axis=0)
    p75 = np.percentile(simulations, 75, axis=0)
    p95 = np.percentile(simulations, 95, axis=0)

    # VaR and CVaR
    pnl = final_values - total_value
    var_95 = np.percentile(pnl, 5)  # 5th percentile of P&L = 95% VaR
    cvar_95 = pnl[pnl <= var_95].mean() if (pnl <= var_95).any() else var_95

    # Probability of loss
    prob_loss = (final_values < total_value).sum() / n_simulations * 100

    return {
        "simulations": simulations,
        "mean_path": mean_path,
        "p5": p5,
        "p25": p25,
        "p75": p75,
        "p95": p95,
        "var_95": float(var_95),
        "cvar_95": float(cvar_95),
        "final_values": final_values,
        "stats": {
            "initial_value": total_value,
            "mean_final": float(np.mean(final_values)),
            "median_final": float(np.median(final_values)),
            "best_case": float(np.max(final_values)),
            "worst_case": float(np.min(final_values)),
            "prob_loss_pct": float(prob_loss),
            "n_simulations": n_simulations,
            "n_days": n_days,
            "n_assets": len(available),
            "tickers_used": available,
        }
    }
