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

### 0) End-to-End Overview

```mermaid
graph TD
    A[Live Market Data<br/>tick / bar] --> G1
    B[Historical OHLCV<br/>20 years] --> HE[Historical Statistical Engine]
    C[News Raw] --> NLP[News NLP Processor]

    HE --> G1[Feature Layer<br/>Market Statistical Representation]
    NLP --> G1

    G1 --> G2[Signal Layer<br/>Explainable Signal Scoring]
    G2 --> G3[Hypothesis Layer<br/>Market Hypothesis Builder]
    G3 --> SM[State Manager<br/>Temporal Smoothing]

    SM --> H[AI Reasoning<br/>Strategy Interpretation]
    H --> I[Strategy Agent<br/>Trade Logic Builder]
    I --> J[Execution Decision<br/>Risk / Account / Permission Checks]

    J --> K[Order / Hold / Reject]
```

### 1) Historical Statistical Engine
```mermaid
graph LR
    H[20 Years Historical OHLCV] --> P[Percentile Engine]
    H --> F[Forward Outcome Engine]
    H --> R[Regime Tagger]
    H --> S[Similarity Search Engine]
    H --> ST[Feature Stability Engine]

    P --> O1["historical_percentile<br/>zscore / rarity"]
    F --> O2["forward_expectancy<br/>future return / drawdown / probability"]
    R --> O3["historical_regime_label<br/>trend / chop / panic / breakout"]
    S --> O4["similar_cases<br/>nearest historical analogs"]
    ST --> O5["feature_reliability<br/>feature weight by regime"]
```

### 2) G1 Feature Layer (No AI)

```mermaid
graph LR
    L[Live Market tick/bar] --> I[Indicator Engine]
    HSE[Historical Statistical Engine Output] --> G1
    NLP[News NLP Output] --> G1

    I --> A1["raw indicators<br/>RSI / SMA / ATR / volume"]
    A1 --> G1

    G1[Build Market Statistical Features] --> F1["raw_feature<br/>RSI = 72"]
    G1 --> F2["context_feature<br/>RSI percentile = 94%"]
    G1 --> F3["anomaly_feature<br/>volume zscore = 3.2"]
    G1 --> F4["regime_feature<br/>current regime = low-vol uptrend"]
    G1 --> F5["similarity_feature<br/>closest historical cases"]
    G1 --> F6["expectancy_feature<br/>historical forward outcome"]
    G1 --> F7["news_feature<br/>sentiment / topic / event impact"]
```

### 2.1) News NLP Processor (Outside G1)

```mermaid
graph LR
    N[Raw News / Events] --> NLP[NLP Processor<br/>LLM or NLP Model]

    NLP --> S["sentiment_score / sentiment_label"]
    NLP --> T["topics"]
    NLP --> E["entities"]
    NLP --> I["event_impact_tags"]

    S --> G1IN[Feed into G1 as structured features]
    T --> G1IN
    E --> G1IN
    I --> G1IN
```

### 3) G2 Signal Layer

```mermaid
graph LR
    F[Structured Features from G1] --> G2[Signal Layer]

    G2 --> S1["mean_reversion_signal<br/>{score, drivers, reliability}"]
    G2 --> S2["trend_follow_signal<br/>{score, drivers, reliability}"]
    G2 --> S3["breakout_signal<br/>{score, drivers, reliability}"]
    G2 --> S4["risk_warning_signal<br/>{score, drivers}"]

    H[Historical Expectancy] --> G2
    R[Feature Reliability] --> G2
```

### 4) G3 Hypothesis Layer

```mermaid
graph LR
    G1F[G1 Features] --> G3
    G2S[G2 Signals] --> G3

    G3[Build Market Hypothesis] --> H1["market_regime"]
    G3 --> H2["dominant_logic<br/>trend / mean reversion / breakout"]
    G3 --> H3["risk_level"]
    G3 --> H4["confidence"]
    G3 --> H5["historical_analog_summary"]
    G3 --> H6["expected_scenario"]
```

### 5) State Manager
```mermaid
graph LR
    G3O[Current Hypothesis] --> SM
    M[Previous State Memory] --> SM

    SM[State Manager<br/>debounce + persistence + switch control] --> O1["current_regime"]
    SM --> O2["regime_duration"]
    SM --> O3["stability_score"]
    SM --> O4["switch_allowed"]
    SM --> O5["state_change_reason"]
```

### 6) AI Reasoning Layer
```mermaid
graph LR
    S[State Context] --> AI
    H[Current Hypothesis] --> AI
    A[Historical Analog Summary] --> AI
    E[Forward Expectancy] --> AI
    R[Risk Context] --> AI

    AI[AI Reasoning<br/>Interpret context and choose strategy] --> O1["selected_strategy"]
    AI --> O2["reason"]
    AI --> O3["strategy_confidence"]
    AI --> O4["avoid_trade_reason"]
```

### 7) Strategy Agent + Execution Decision
```mermaid
graph LR
    AI[AI Output<br/>selected_strategy + reason] --> SA

    SA[Strategy Agent<br/>Deterministic / Semi-rule] --> A["action<br/>buy / sell / hold"]
    SA --> E["entry"]
    SA --> SL["stop_loss"]
    SA --> TP["take_profit"]
    SA --> SZ["position_size"]

    A --> ED
    E --> ED
    SL --> ED
    TP --> ED
    SZ --> ED

    ED[Execution Decision<br/>risk / account / permission checks] --> X1["approve_order"]
    ED --> X2["reject_order"]
    ED --> X3["hold"]
```

