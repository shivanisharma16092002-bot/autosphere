from typing import List
import numpy as np

def forecast_next_demand(historical_demand: List[int]) -> int:
    """
    Predicts the next month's demand using simple linear regression (least squares trend line).
    If the historical demand has fewer than 2 data points, or if the projected trend is negative,
    falls back to a Simple Moving Average (SMA). Clamps the final forecast to a minimum of 0.
    
    Parameters:
    - historical_demand: List of monthly historical demand values (integers).
    
    Returns:
    - Forecasted demand for the next month (integer).
    """
    if not historical_demand:
        return 0
    
    n = len(historical_demand)
    if n < 2:
        return historical_demand[0]
        
    # Time steps: [1, 2, ..., n]
    x = np.arange(1, n + 1)
    y = np.array(historical_demand)
    
    # Fit line: y = m * x + c
    # Create design matrix: A = [[x1, 1], [x2, 1], ...]
    A = np.vstack([x, np.ones(n)]).T
    
    # Solve least squares regression
    m, c = np.linalg.lstsq(A, y, rcond=None)[0]
    
    # Project for the next month (n + 1)
    next_month = n + 1
    forecast = m * next_month + c
    
    # If the trend leads to a negative number, fall back to simple moving average of last 3 periods
    if forecast < 0:
        last_periods = min(3, n)
        forecast = np.mean(y[-last_periods:])
        
    return max(0, int(round(forecast)))
