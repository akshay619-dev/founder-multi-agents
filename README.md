# Founder Intelligence Copilot

A multi-agent CLI tool that detects fintech opportunities in real-time, analyzes them using AI, generates execution plans, and delivers reports via Telegram and email.

Built as a single Python file with zero frameworks — just `rich` for the dashboard UI.

---

## What It Does

The Copilot runs five AI agents in parallel to scan the market and produce actionable intelligence for fintech founders:

```
Signal Agent     →  Fetches real-time fintech signals from SerpAPI / Perplexity
Analyst Agent    →  Evaluates each company using Claude (Anthropic API)
Execution Agent  →  Generates integration plans, APIs, and GTM steps
Memory Agent     →  Tracks past analyses and surfaces reusable patterns
Delivery Agent   →  Sends reports via Telegram and email
```

### The Pipeline

```
┌─────────────┐     ┌───────────────┐     ┌──────────────────┐
│ SerpAPI /    │────→│ Claude Filter │────→│ Company Signals   │
│ Perplexity   │     │ (removes junk) │     │ (clean names)     │
└─────────────┘     └───────────────┘     └────────┬─────────┘
                                                    │
                    ┌───────────────┐               │
                    │ Memory Agent  │◄──────────────┤
                    │ (past data)   │               │
                    └───────┬───────┘               │
                            │                       ▼
                    ┌───────▼───────┐     ┌──────────────────┐
                    │ Pattern Match │────→│ Analyst Agent     │
                    │ (reuse APIs)  │     │ (Claude analysis) │
                    └───────────────┘     └────────┬─────────┘
                                                    │
                                          ┌────────▼─────────┐
                                          │ Execution Agent   │
                                          │ (plan + APIs)     │
                                          └────────┬─────────┘
                                                    │
                                          ┌────────▼─────────┐
                                          │ Delivery Agent    │
                                          │ Telegram + Email  │
                                          └──────────────────┘
```

---

## Features

- **Real-time signal detection** — fetches live fintech funding news, product launches, and partnerships via SerpAPI
- **AI-powered analysis** — Claude evaluates each company with domain-specific prompts (not generic summaries)
- **Multi-domain support** — lending, payments, and insurance — each with tailored prompts, APIs, risk checks, and display labels
- **Dynamic target context** — evaluates fit against a specific target (e.g., "Apollo Finvest", "Razorpay", "Plum") rather than generic scoring
- **Memory system** — JSON-based persistence tracks past analyses, skips duplicates, and surfaces reusable integration patterns
- **Multi-agent dashboard** — `rich` Layout with 5 live-updating panels showing each agent's progress in real-time
- **Threaded execution** — agents run as parallel threads coordinated via `threading.Event` gates
- **Telegram bot mode** — long-polling bot that accepts `/scan <company> <domain>` commands and auto-scans when idle
- **Email reports** — plain-text SMTP delivery with domain-aware formatting
- **Graceful fallbacks** — mock data at every layer (search, Claude, signals) so the tool works without any API keys

---

## Quick Start

### 1. Clone and configure

```bash
cd /path/to/copilot
```

Create a `.env` file:

```env
# Required for AI analysis
ANTHROPIC_API_KEY=sk-ant-...

# Required for live signal detection
SERPAPI_API_KEY=your-serpapi-key

# Optional: Telegram notifications
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Optional: Email reports
EMAIL_USER=you@example.com
EMAIL_PASS=your-app-password
EMAIL_TO=recipient@example.com
```

### 2. Install dependencies

```bash
pip install rich
```

That's it. Everything else uses Python standard library (`urllib`, `smtplib`, `threading`, `json`).

### 3. Run

```bash
# Full scan with default domain (lending)
python copilot.py

# Scan with a specific domain
python copilot.py payments
python copilot.py insurance
python copilot.py lending

# Start Telegram bot
python copilot.py bot

# Help
python copilot.py --help
```

---

## Domains

Each domain configures the entire pipeline — search queries, Claude prompts, display labels, and risk categories.

| Domain | Target Context | Focus | Flow |
|---|---|---|---|
| **lending** | Apollo Finvest (Lending Infra) | Underwriting, credit scoring, NBFC, disbursement | Origination → KYC → Underwriting → Disbursement → Servicing → Collections |
| **payments** | Razorpay (Payments) | Checkout, settlement, UPI, merchant acquiring | Initiation → Auth → Capture → Settlement → Reconciliation → Dispute |
| **insurance** | Plum (Insurance) | Claims, policy lifecycle, premium pricing, distribution | Quote → Bind → Issue → Endorse → Claim → Settle |

---

## Telegram Bot Commands

Start with `python copilot.py bot`, then send these commands to your bot:

| Command | Example | Description |
|---|---|---|
| `/scan <company> <domain>` | `/scan razorpay payments` | Analyze a specific company in a domain |
| `/scan <company>` | `/scan kreditbee` | Analyze with default domain (lending) |
| `/autoscan` | `/autoscan` | Trigger auto-scan for trending signals |
| `/domains` | `/domains` | List available domains |
| `/help` | `/help` | Show command reference |

The bot also **auto-scans every 5 minutes** when idle, fetching trending lending signals and sending reports for high-scoring companies.

---

## Output Format

Each company gets a unified dashboard panel:

```
╭────────────── 🚨 KreditBee  8/10  ● High Fit ──────────────╮
│                                                              │
│  🎯 Target Context: Apollo Finvest (Lending Infra)          │
│  🧭 Lending & Credit  │  Loan Flow: Origination → KYC → ... │
│                                                              │
│  💳 Business Model                                           │
│    Digital lending platform...                               │
│                                                              │
│  🧠 Underwriting & Credit Angle                             │
│    Transaction data enables underwriting...                  │
│                                                              │
│  🎯 Fit for Apollo Finvest (Lending Infra): High            │
│                                                              │
│  💡 Why Now                                                  │
│    Series E at $1.5B valuation...                           │
│                                                              │
│  ⚠️ Key Risks                                                │
│    • RBI regulatory tightening...                           │
│    • Competition from PhonePe...                            │
│                                                              │
│  ──────────────────────────────────────                      │
│                                                              │
│  🚀 Integration Plan                                         │
│    Phase 1: API integration...                              │
│                                                              │
│  Loan Lifecycle APIs (8):                                    │
│    • POST /loan-applications ...                            │
│                                                              │
│  Credit Risk Checks (7):                                     │
│    ▶ RBI compliance validation...                           │
╰──────────────────────────────────────────────────────────────╯
```

---

## Architecture

```
copilot.py          Single-file CLI tool (~1700 lines)
.env                API keys (not committed)
memory.json         Persistent analysis memory (auto-created)
```

### Key Components

| Component | What It Does |
|---|---|
| `DOMAIN_CONFIG` | Per-domain prompts, APIs, risks, search terms, display labels |
| `call_claude()` | Anthropic Messages API with mock fallback |
| `fetch_signals()` | SerpAPI → Claude filter → clean company signals |
| `analyze_company()` | Domain-aware Claude analysis with target context |
| `generate_execution_plan()` | Domain-aware execution plan with memory context |
| `Dashboard` | Thread-safe `rich.Layout` with 5 agent panels + status bar |
| `LiveFeed` / `AgentPanel` | Scrolling log panels updated via `rich.Live` |
| `auto_scan()` | Periodic signal fetcher for Telegram bot idle mode |
| `scan_company()` | Single-company pipeline for Telegram `/scan` commands |

### Thread Coordination

```
memory_agent ──→ memory_loaded ──→ signal_agent ──→ signals_ready
                                                         │
                                              analyst_agent (+ execution)
                                                         │
                                              analysis_done ──→ delivery_agent
                                                                      │
                                                              delivery_done ──→ stop
```

Four daemon threads coordinated via `threading.Event` gates. All dashboard updates are protected by `threading.Lock`.

---

## API Keys

| Key | Required | Used For |
|---|---|---|
| `ANTHROPIC_API_KEY` | For AI analysis | Claude API (analysis + execution plans) |
| `SERPAPI_API_KEY` | For live signals | Google Search via SerpAPI |
| `PERPLEXITY_API_KEY` | Alternative search | Perplexity API (fallback for SerpAPI) |
| `TELEGRAM_BOT_TOKEN` | For Telegram | Telegram Bot API |
| `TELEGRAM_CHAT_ID` | For Telegram | Target chat for notifications |
| `EMAIL_USER` | For email | SMTP login (Gmail, Outlook, etc.) |
| `EMAIL_PASS` | For email | SMTP password (use app passwords for Gmail) |
| `EMAIL_TO` | For email | Report recipient address |
| `EMAIL_SMTP_HOST` | Optional | Override SMTP host (e.g., `smtp.gmail.com:587`) |

The tool works without any keys — it falls back to mock data at every layer.

---

## How It Works — Step by Step

1. **Signal Detection** — SerpAPI searches for domain-specific fintech news (funding rounds, product launches, acquisitions). Results are filtered through Claude to extract real company signals and drop market reports.

2. **AI Analysis** — Each company is evaluated by Claude using a domain-aware prompt that includes the target context, analysis lens, known risks, and relevant API types. The prompt forces opinionated, founder-level reasoning — not generic summaries.

3. **Execution Planning** — Claude generates a concrete integration plan with domain-specific API endpoints, data requirements, risk checks, and GTM steps. Memory context is injected so the model can suggest reusable patterns from past analyses.

4. **Memory Persistence** — Every analysis is saved to `memory.json` with timestamps. On subsequent runs, the memory agent surfaces reusable APIs and integration shortcuts, and the signal agent skips already-analyzed companies.

5. **Delivery** — Reports are sent via Telegram (compact HTML summary of top 2 opportunities) and email (full plain-text report). The Telegram bot also supports on-demand `/scan` commands and periodic auto-scanning.

---

## Extending

**Add a new domain:**

Add an entry to `DOMAIN_CONFIG` with all required keys (`label`, `focus`, `apis`, `risks`, `analysis_lens`, `execution_lens`, `search_terms`, `use_case_key`, `operator_role`, `target_context`, `icon`, `use_case_label`, `api_section_label`, `risk_section_label`, `flow_label`). The entire pipeline adapts automatically.

**Connect real APIs:**

Replace `call_claude()` body with the Anthropic SDK (commented example in the code). Replace `_fetch_serpapi()` with any search provider. The dataclass contracts (`Signal`, `Analysis`, `ExecutionPlan`) stay the same.

**Add new notification channels:**

Follow the pattern of `send_to_telegram()` / `send_email()` — add a new function, wire it into the delivery agent thread.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License





