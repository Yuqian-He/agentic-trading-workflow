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

```mermaid
graph TD
    A[Market Data<br/>tick / bar / orderbook] --> G1
    D[Historical Data<br/>OHLCV / indicators history] --> G1
    E[News Data<br/>headlines / article text / events] --> G1

    subgraph L1[G1 Feature Layer - Fact Description Only]
        G1[Build Structured Features<br/>No AI in this layer]
        G1IN["Input (raw):<br/>tick, bar, RSI, SMA, news text"]
        G1OUT["Output (features):<br/>{trend, rsi, rsi_state,<br/>volume_spike, news_sentiment}"]
        G1NOTE["Responsibility:<br/>Describe what is happening now.<br/>No buy/sell judgment."]
        G1IN --> G1
        G1 --> G1OUT
        G1 --> G1NOTE
    end

    subgraph L2[G2 Signal Layer - Strategy-Oriented Signals]
        G2[Generate Signal Candidates<br/>Rule/Model Based, Not Final Decision]
        G2IN["Input:<br/>G1 structured features"]
        G2OUT["Output (signals):<br/>{mean_reversion_signal,<br/>trend_follow_signal,<br/>breakout_signal}"]
        G2NOTE["Responsibility:<br/>Map features to strategy tendencies.<br/>Still not an execution decision."]
        G2IN --> G2
        G2 --> G2OUT
        G2 --> G2NOTE
    end

    subgraph L3[G3 Hypothesis Layer - Market Story Synthesis]
        G3[Build Market Hypothesis Context]
        G3IN["Input:<br/>G2 signals + G1 features"]
        G3OUT["Output (hypothesis):<br/>{market_regime,<br/>dominant_logic,<br/>risk, confidence}"]
        G3NOTE["Responsibility:<br/>Explain what market is doing,<br/>why it moves, where risk is."]
        G3IN --> G3
        G3 --> G3OUT
        G3 --> G3NOTE
    end

    subgraph AI[AI Reasoning and Action]
        H[H AI Reasoning<br/>Interpret G3 and choose strategy]
        HIN["Input:<br/>G3 market hypothesis"]
        HOUT["Output:<br/>{selected_strategy, reason}"]
        I[I Strategy Agent<br/>Deterministic / Semi-rule Execution Plan]
        IOUT["Output:<br/>{action, entry, stop_loss, take_profit}"]
        J[J Execution Decision<br/>Risk + Account + Permission Checks]
        JOUT["Output:<br/>approve_order / reject_order / hold"]
        HIN --> H
        H --> HOUT
        HOUT --> I
        I --> IOUT
        IOUT --> J
        J --> JOUT
    end

    G1 --> G2
    G2 --> G3
    G3 --> H
```
