# AutoSphere AI — Supply Chain Decision Engine Prototype

**AutoSphere AI** is a modular, high-fidelity supply chain decision engine prototype for the automotive industry. It forecasts market demand trends, parses real-time customer feedback text utilizing simulated Natural Language Processing (NLP) heuristics, and executes a multi-criteria procurement scoring algorithm to optimize supplier sourcing.

---

## 🌟 Key Architecture & Modular Design

```
hackathon_project/
│
├── models/
│   ├── __init__.py
│   ├── supplier.py         # Supplier Pydantic model
│   └── demand.py           # MarketDemand Pydantic model
│
├── engines/
│   ├── __init__.py
│   ├── procurement.py      # Multi-criteria sourcing optimization
│   ├── forecasting.py      # Demand trend forecasting (numpy linear regression)
│   └── feedback.py         # Simulated NLP feedback parser & risk analyzer
│
├── main.py                 # Simulation orchestrator & interactive CLI
├── test_suite.py           # Automated unit and integration test suite
├── requirements.txt        # Package dependencies
└── README.md               # User guide & documentation
```

---

## 📊 Engines and Core Mathematical Formulations

### 1. Demand Forecasting Engine
AutoSphere AI analyzes historical trends by performing **Least-Squares Linear Regression** over past monthly demand values.
- Given historical periods $t = 1 \dots N$ and demand $y_t$, it solves for the trend line $y = m \cdot t + c$.
- It projects the demand for period $N+1$.
- **Robust Fallback**: If the linear trend is negative, it falls back to a **Simple Moving Average (SMA)** of the last 3 periods, clamping the forecast to a minimum of `0`.

### 2. NLP Feedback Parser & Risk Adjuster
An NLP heuristic processor scans unstructured customer feedback to detect risk indicators and calculate dynamic risk penalties.
- **Entity Matching**: Uses case-insensitive regex pattern boundaries to extract Supplier Names/IDs and Component references.
- **Sentiment Keyword Severity Classification**:
  - **Critical (penalty +0.30)**: `"recall"`, `"hazard"`, `"dangerous"`, `"crack"`, `"fire"`, etc.
  - **Severe (penalty +0.15)**: `"fail"`, `"defect"`, `"faulty"`, `"leak"`, etc.
  - **Moderate (penalty +0.08)**: `"wear"`, `"wearing out"`, `"slow"`, `"delay"`, etc.
- **Clamped Risk Updates**: The supplier's risk score is updated via:
  $$\text{New Risk} = \min(1.0, \text{Old Risk} + \sum \text{Penalties})$$

### 3. Sourcing Procurement Optimization Engine
To make optimal sourcing recommendations, the engine evaluates matching suppliers using three weighted criteria:
- **Cost**: 40% (minimized)
- **Risk**: 40% (minimized)
- **Capacity**: 20% (maximized)

Since these metrics are on different scales, we normalize them to a uniform $[0.0, 1.0]$ range using **Min-Max Normalization** relative to the active supplier pool:

1. **Cost Score ($CS_i$)**:
   $$CS_i = 1.0 - \frac{\text{Cost}_i - \min(\text{Costs})}{\max(\text{Costs}) - \min(\text{Costs})}$$
2. **Risk Score ($RS_i$)**:
   $$RS_i = 1.0 - \text{Risk}_i$$
3. **Capacity Score ($CapS_i$)**:
   $$CapS_i = \frac{\text{Capacity}_i - \min(\text{Capacities})}{\max(\text{Capacities}) - \min(\text{Capacities})}$$
4. **Composite Score ($Score_i$)**:
   $$Score_i = 0.4 \times CS_i + 0.4 \times RS_i + 0.2 \times CapS_i$$

---

## 🚀 Getting Started

### 📋 Prerequisites
Ensure you have **Python 3.9+** installed.

### 🔧 Installation
Install the required packages:
```bash
pip install -r requirements.txt
```

### 🎮 Running the Simulation
Execute the main orchestrator script to run the full supply chain lifecycle simulation:
```bash
python main.py
```

### 🧪 Running the Automated Verification Tests
Execute the unit and integration tests to verify the system logic:
```bash
python -m unittest test_suite.py
```
