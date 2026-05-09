# Agentic Trading Workflow


Agentic Trading Workflow is an early-stage backend prototype for an autonomous trading workflow that turns market data, strategy signals, and retrieved context into agent-driven trading decisions. The backend now includes a minimal Interactive Brokers Gateway/TWS connection path that can read market updates from a local IB paper trading session and persist them for later execution, risk, and analysis work.

## Project Goal

The goal of this project is to explore how a trading system can be organized around an agent loop instead of a single hard-coded strategy. The backend is designed to receive market data, calculate indicators from bar data, generate strategy signals, build decision context from market summaries and RAG sources, then let AI agents choose a strategy and decide whether an order should be executed. At this stage, the project focuses on validating the workflow structure and core interfaces before connecting real broker execution, production data pipelines, and more advanced decision logic.

## Current IB Data Integration

The current market data path connects to a local Interactive Brokers TWS or IB Gateway instance using `ib_insync`.

Because this demo does not assume paid real-time market data subscriptions, the backend currently requests delayed market data with `reqMarketDataType(3)` and streams quote updates through `reqMktData`. These updates are normalized into tick-like records, cached as the latest market snapshot, and written to SQLite. 

## Run Locally

Start TWS or IB Gateway, log into the paper account, and enable API socket clients with port `7497`. Then run:

```bash
uvicorn app.main:app
```

Open:

```text
http://127.0.0.1:8000
```

## Workflow Diagram

### 1) End-to-End Overview

```mermaid
graph TD
    A[Market Data] --> G1[Feature Layer]
    D[Historical Data] --> G1
    E[News Data] --> G1
    G1 --> G2[Signal Layer]
    G2 --> G3[Hypothesis Layer]
    G3 --> H[AI Reasoning]
    H --> I[Strategy Agent]
    I --> J[Execution Decision]
```

### 2) G1 Feature Layer (No AI)

```mermaid
graph LR
    A[Market tick/bar/orderbook] --> G1
    D[Historical OHLCV + indicators] --> G1
    E[News text/events] --> G1

    G1[Build Structured Features<br/>Describe facts only] --> O1["trend"]
    G1 --> O2["rsi / sma / volatility"]
    G1 --> O3["rsi_state / volume_spike"]
    G1 --> O4["news_sentiment"]
```

### 3) G2 Signal Layer

```mermaid
graph LR
    F1["trend, rsi_state, volume_spike, sentiment"] --> G2
    G2[Map Features to Strategy Signals] --> S1["mean_reversion_signal"]
    G2 --> S2["trend_follow_signal"]
    G2 --> S3["breakout_signal"]
    N[Not a final trade decision] --> G2
```

### 4) G3 Hypothesis Layer

```mermaid
graph LR
    G1F[G1 Features] --> G3
    G2S[G2 Signals] --> G3
    G3[Build Market Hypothesis] --> H1["market_regime"]
    G3 --> H2["dominant_logic"]
    G3 --> H3["risk"]
    G3 --> H4["confidence"]
```

### 5) H AI Reasoning

```mermaid
graph LR
    G3O[Hypothesis Context] --> H
    H[AI Reasoning<br/>Interpret and choose strategy] --> R1["selected_strategy"]
    H --> R2["reason"]
```

### 6) I + J Execution Path

```mermaid
graph LR
    HOUT["selected_strategy + reason"] --> I
    I[Strategy Agent<br/>Deterministic / Semi-rule] --> P1["action"]
    I --> P2["entry / stop_loss / take_profit"]
    P2 --> J
    P1 --> J
    J[Execution Decision<br/>Risk / account / permission checks] --> X1["approve_order"]
    J --> X2["reject_order"]
    J --> X3["hold"]
```
