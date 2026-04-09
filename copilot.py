#!/usr/bin/env python3
"""Founder Intelligence Copilot — fintech signal detection and execution planning."""

import json
import os
import smtplib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

BASE_DIR = Path(__file__).parent
MEMORY_FILE = BASE_DIR / "memory.json"
ENV_FILE = BASE_DIR / ".env"


def load_env() -> None:
    """Load variables from .env file into os.environ (no dependencies)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


load_env()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    company: str
    sector: str
    trigger: str
    source: str


@dataclass
class Analysis:
    company: str
    business_model: str
    lending_use_case: str
    target_fit: str          # High / Medium / Low
    why: str
    risks: list[str]
    opportunity_score: int   # 1-10


@dataclass
class ExecutionPlan:
    company: str
    integration_plan: str
    apis: list[str]
    data_needed: list[str]
    risk_checks: list[str]
    gtm_steps: list[str]
    reusable_from_memory: list[str]


# ---------------------------------------------------------------------------
# Domain configuration
# ---------------------------------------------------------------------------

DOMAIN_CONFIG: dict[str, dict] = {
    "lending": {
        "label": "Lending & Credit",
        "focus": "credit decisioning, underwriting models, NBFC infrastructure, loan origination, collections, risk scoring, disbursement rails",
        "apis": ["loan origination", "KYC/KYB verification", "credit score pull", "underwriting engine", "disbursement", "collections", "bureau integration"],
        "risks": ["borrower default and NPA spikes", "fraud in loan applications", "RBI/regulatory tightening on digital lending", "interest rate exposure on floating-rate books", "concentration risk in borrower segments"],
        "analysis_lens": "Evaluate how this company generates underwriting signals, controls credit risk, or enables loan distribution. Prioritize transaction data access, borrower reach, and regulatory positioning.",
        "execution_lens": "Design APIs around the full loan lifecycle: origination, KYC, credit pull, decisioning, disbursement, servicing, collections. Risk checks must cover NPA scenarios, regulatory compliance, and portfolio stress tests.",
        "search_terms": ["lending fintech", "NBFC startup", "credit platform", "underwriting", "digital lending"],
        "use_case_key": "lending_use_case",
        "operator_role": "lending founder who has built underwriting systems and managed loan books",
        "target_context": "Apollo Finvest (Lending Infra)",
        # Display
        "icon": "\U0001f4b3",
        "use_case_label": "Underwriting & Credit Angle",
        "api_section_label": "Loan Lifecycle APIs",
        "risk_section_label": "Credit Risk Checks",
        "flow_label": "Loan Flow: Origination \u2192 KYC \u2192 Underwriting \u2192 Disbursement \u2192 Servicing \u2192 Collections",
    },
    "payments": {
        "label": "Payments & Transactions",
        "focus": "payment rails, checkout conversion, settlement infrastructure, UPI/IMPS integration, cross-border remittance, merchant acquiring, recurring billing",
        "apis": ["payment initiation", "refund processing", "webhook events", "settlement reconciliation", "checkout SDK", "payout rails", "dispute management"],
        "risks": ["transaction fraud and chargebacks", "settlement delays and reconciliation gaps", "payment gateway downtime and SLA breaches", "regulatory changes on MDR and interchange", "cross-border compliance and currency volatility"],
        "analysis_lens": "Evaluate how this company moves money, what payment rails they control, and where transaction volume creates leverage. Prioritize checkout conversion, settlement speed, and merchant stickiness.",
        "execution_lens": "Design APIs around the full payment lifecycle: initiation, authorization, capture, settlement, refund, dispute. Risk checks must cover fraud detection, chargeback ratios, PCI compliance, and uptime SLAs.",
        "search_terms": ["payments fintech", "checkout startup", "UPI platform", "settlement infrastructure", "payment gateway"],
        "use_case_key": "payments_use_case",
        "operator_role": "payments founder who has built transaction infrastructure and managed merchant relationships",
        "target_context": "Razorpay (Payments)",
        # Display
        "icon": "\U0001f4b8",
        "use_case_label": "Transaction Flow & Settlement Angle",
        "api_section_label": "Payment Lifecycle APIs",
        "risk_section_label": "Transaction Risk Checks",
        "flow_label": "Txn Flow: Initiation \u2192 Auth \u2192 Capture \u2192 Settlement \u2192 Reconciliation \u2192 Dispute",
    },
    "insurance": {
        "label": "Insurance & Insurtech",
        "focus": "policy lifecycle management, claims automation, actuarial underwriting, premium optimization, embedded distribution, reinsurance, fraud detection",
        "apis": ["policy issuance", "claims submission", "premium calculation", "underwriting assessment", "distribution integration", "fraud scoring", "reinsurance placement"],
        "risks": ["fraudulent claims inflating loss ratios", "actuarial mispricing leading to underwriting losses", "IRDAI regulatory compliance and license requirements", "catastrophic event exposure and reinsurance gaps", "distribution channel dependency and commission compression"],
        "analysis_lens": "Evaluate how this company underwrites risk, processes claims, or distributes policies. Prioritize data advantage in pricing, claims automation efficiency, and distribution channel control.",
        "execution_lens": "Design APIs around the full policy lifecycle: quote, bind, issue, endorse, claim, settle. Risk checks must cover loss ratio sustainability, claims fraud detection, regulatory filings, and reinsurance adequacy.",
        "search_terms": ["insurtech startup", "insurance platform", "claims automation", "policy management", "embedded insurance"],
        "use_case_key": "insurance_use_case",
        "operator_role": "insurance founder who has built claims systems and managed underwriting portfolios",
        "target_context": "Plum (Insurance)",
        # Display
        "icon": "\U0001f6e1\ufe0f",
        "use_case_label": "Claims & Policy Lifecycle Angle",
        "api_section_label": "Policy Lifecycle APIs",
        "risk_section_label": "Underwriting & Claims Risk Checks",
        "flow_label": "Policy Flow: Quote \u2192 Bind \u2192 Issue \u2192 Endorse \u2192 Claim \u2192 Settle",
    },
}

DEFAULT_DOMAIN = "lending"
DEFAULT_TARGET = "Lending/NBFC"


def get_domain(name: str | None = None) -> dict:
    """Return a domain config dict. Falls back to DEFAULT_DOMAIN."""
    key = (name or DEFAULT_DOMAIN).lower()
    if key not in DOMAIN_CONFIG:
        print(f"  [warn] Unknown domain '{key}', falling back to '{DEFAULT_DOMAIN}'")
        key = DEFAULT_DOMAIN
    cfg = DOMAIN_CONFIG[key].copy()
    cfg["key"] = key
    return cfg


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

ANALYSIS_SYSTEM = """\
You are a startup operator evaluating companies for {target_context}.
You return ONLY valid JSON — no markdown, no commentary, no preamble.

The JSON must have these exact keys:
  business_model (string), {use_case_key} (string),
  target_fit (string: High, Medium, or Low), why (string),
  risks (array of 2-3 strings), opportunity_score (integer 1-10).\
"""

ANALYSIS_PROMPT = """\
You are a startup operator.

Evaluate this company based on its fit for:
{target_context}

Domain: {domain_label}
Domain focus: {domain_focus}
Key APIs: {domain_apis}
Known risks: {domain_risks}
Analysis lens: {analysis_lens}

Company:
{company}

Sector: {sector}
Trigger: {trigger}
Source: {source}

Return:

1. What they do (clear, no fluff)
2. Use case relevance for {target_context} — be specific about the exact \
integration or partnership opportunity, not a generic "could be useful" answer
3. \U0001f3af Fit for {target_context} (High / Medium / Low)
4. Why it fits (specific to {target_context} — tie it to their unit economics, \
data assets, or distribution advantage)
5. Risks (2-3, context-specific to {target_context} and {domain_label} — \
not generic startup risks)
6. Opportunity Score (1-10)

Be sharp and contextual. Avoid generic answers.\
"""

FILTER_SYSTEM = """\
You return ONLY valid JSON — no markdown, no commentary, no preamble.

The JSON must be an array of objects, each with these exact keys:
  name (string: clean company name only, no funding amounts or descriptions),
  sector (string: specific fintech sub-sector),
  trigger (string: one-sentence event that makes this relevant now),
  source (string: original URL, passed through unchanged).\
"""

FILTER_PROMPT = """\
You are a fintech signal analyst specializing in {domain_label}.
Domain focus: {domain_focus}

Extract real company signals from these raw search results. \
Prioritize companies relevant to {domain_label} — those building \
or enabling {domain_focus}.

For EACH result, do one of:
1. If it's about a specific company event (funding, launch, acquisition, \
partnership) — include it with a clean company name.
2. If it's a roundup/listicle that MENTIONS specific companies with concrete \
events — extract those individual companies as separate signals.
3. If it's purely a market report with no specific company — drop it.

Raw results:
{results}

Rules:
- Clean company names only (e.g. "KreditBee" not "KreditBee raises $280m...")
- Deduplicate — if the same company appears multiple times, keep the most informative one
- Rank companies with direct {domain_label} relevance higher
- Return up to 5 signals, minimum 1
- Every signal MUST have a real company name, not an article title\
"""

EXECUTION_SYSTEM = """\
You are a senior backend engineer specializing in {domain_label} infrastructure.
You return ONLY valid JSON — no markdown, no commentary.

The JSON must have these exact keys:
  integration_plan (string), apis (array of strings with HTTP method + endpoint + description),
  data_needed (array of strings), risk_checks (array of strings),
  gtm_steps (array of strings), reusable_from_memory (array of strings, empty if none).\
"""

EXECUTION_PROMPT = """\
You are building {domain_label} infrastructure.

Focus on: {domain_focus}

While generating the plan:
- APIs MUST use domain-specific endpoints from: {domain_apis}
- Risk checks MUST cover: {domain_risks}
- GTM steps should target {domain_label} buyers and distribution channels

Execution lens: {execution_lens}

Based on this analysis:
{analysis}

Use past patterns if relevant:
{memory}

Generate a concrete integration and go-to-market plan. \
Every API endpoint must be specific to {domain_label} operations — \
no generic CRUD. Every risk check must be a real {domain_label} failure mode.\
"""


# ---------------------------------------------------------------------------
# Memory system
# ---------------------------------------------------------------------------

def load_memory() -> dict:
    """Load persistent memory from disk. Creates file if missing."""
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    default: dict = {"companies": {}}
    MEMORY_FILE.write_text(json.dumps(default, indent=2))
    return default


def save_memory(memory: dict) -> None:
    """Persist memory back to disk."""
    MEMORY_FILE.write_text(json.dumps(memory, indent=2))


def save_to_memory(company: str, analysis: Analysis, memory: dict) -> None:
    """Store a company analysis in memory for future reference."""
    memory["companies"][company] = {
        "sector": "",   # filled by caller
        "analysis": asdict(analysis),
        "analysed_at": datetime.now(timezone.utc).isoformat(),
    }


def get_memory_context(memory: dict) -> str:
    """Build a text summary of past analyses for prompt injection.

    Returns a human-readable block that Claude can use to identify
    reusable APIs, overlapping sectors, and integration shortcuts.
    """
    companies = memory.get("companies", {})
    if not companies:
        return "No prior analyses available."

    lines: list[str] = []
    for name, entry in companies.items():
        a = entry["analysis"]
        lines.append(
            f"- {name} (sector: {entry.get('sector', 'unknown')}, "
            f"fit: {a.get('target_fit', a.get('apollo_fit', 'N/A'))}, score: {a['opportunity_score']}/10): "
            f"{a['business_model'][:120]}..."
        )
        lines.append(f"  Risks: {', '.join(a['risks'][:2])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM interface — real Claude API with mock fallback
# ---------------------------------------------------------------------------

def call_claude(prompt: str, system: str = "") -> str:
    """Call the Anthropic Messages API. Falls back to mock if no API key.

    Args:
        prompt:  User message content.
        system:  System message (instructions, output format).

    Returns:
        Raw text from Claude (expected to be JSON).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return _mock_fallback(prompt)

    body: dict = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system

    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        CLAUDE_API_URL,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        text = data["content"][0]["text"]
        # Strip markdown fences if Claude wraps the JSON
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return text
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        print(f"  [error] Claude API {e.code}: {error_body[:200]}")
        print("  [fallback] Using mock response")
        return _mock_fallback(prompt)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"  [error] Claude API failed: {e}")
        print("  [fallback] Using mock response")
        return _mock_fallback(prompt)


def _mock_fallback(prompt: str) -> str:
    """Route to mock responses when the API is unavailable."""
    if "Analyze" in prompt and "company" in prompt.lower():
        return _mock_analysis_response(prompt)
    if "analysis" in prompt.lower() and "plan" in prompt.lower():
        return _mock_execution_response(prompt)
    return '{"error": "unknown prompt type"}'


def _find_target_company(prompt: str, companies: list[str]) -> str | None:
    """Match the target company — prefer 'Company: <name>' over bare name."""
    for name in companies:
        if f"Company: {name}" in prompt or f"company:\n{name}" in prompt:
            return name
    for name in companies:
        if name in prompt:
            return name
    return None


def _mock_analysis_response(prompt: str) -> str:
    """Hardcoded analysis JSON — written in founder-operator tone."""
    responses = {
        "NovaPay": {
            "business_model": "Payment rails for marketplaces. One API, handles checkout + payouts. They clip 0.5-1.2% per transaction and charge a monthly platform fee. Not novel, but the SE-Asia focus is the wedge — most competitors haven't localised there yet.",
            "lending_use_case": "They sit on real-time transaction data for every merchant. That's an underwriting goldmine — you can offer merchant cash advances without asking for a single bank statement. The data moat is the product.",
            "target_fit": "High",
            "why": "Series B at $40M means they've proven PMF. API-first means we can plug in fast. The SE-Asia expansion is a timing play — if we move now, we're the lending layer before Stripe even shows up in those markets.",
            "risks": ["ASEAN is 10 countries with 10 regulatory regimes — licensing alone could stall us 6+ months per market", "Stripe and Adyen are circling the same region; if they launch embedded lending, NovaPay's moat shrinks overnight"],
            "opportunity_score": 9,
        },
        "LendStack": {
            "business_model": "Underwriting-as-a-service. Lenders plug in via API, get credit decisions back. They charge per decision ($0.50-$2) plus monthly platform fees. Think Plaid but for credit scoring.",
            "lending_use_case": "This IS lending infra. They don't do loans themselves — they power the decisioning for everyone else. If we partner, we skip building our own underwriting engine entirely.",
            "target_fit": "Medium",
            "why": "The API is clean and the non-bank lender market is growing fast. But they're pre-scale — top 3 clients probably drive 70%+ of revenue. If one churns, the whole business wobbles. Worth a pilot, not a bet-the-farm move.",
            "risks": ["Unit economics are unproven — per-decision pricing gets squeezed hard when volumes scale", "Fair-lending regulators are starting to look at black-box ML scoring; one enforcement action could freeze their pipeline"],
            "opportunity_score": 6,
        },
        "VaultBridge": {
            "business_model": "Crypto custody for institutions — MPC key sharding, targeting hedge funds and family offices. Revenue is basis points on AUM plus implementation fees. Classic enterprise sales, painfully slow.",
            "lending_use_case": "Collateralised crypto lending — they custody the assets, we could build a lending product on top. But the DeFi-to-TradFi bridge is more whitepaper than reality right now.",
            "target_fit": "Low",
            "why": "They just acqui-hired an MPC team and are mid-SOC-2 certification. That's at least 6 months of integration risk before they're even stable. The TAM is real but tiny, and every deal takes 3-6 months to close. Not worth the calories right now.",
            "risks": ["Post-acquisition team retention is a coin flip — if the MPC engineers leave, the core product is gutted", "One regulatory crackdown on crypto custody and their entire client pipeline freezes"],
            "opportunity_score": 3,
        },
    }
    match = _find_target_company(prompt, list(responses.keys()))
    return json.dumps(responses[match]) if match else json.dumps(responses["NovaPay"])


def _mock_execution_response(prompt: str) -> str:
    """Hardcoded execution plan JSON for the three mock companies."""
    has_memory = "No prior analyses available" not in prompt
    responses = {
        "NovaPay": {
            "integration_plan": "Phase 1: Enrich company profile and map org chart via Apollo. Phase 2: Build transaction-data ingestion pipeline for underwriting POC. Phase 3: Launch co-branded merchant cash advance pilot in Singapore.",
            "apis": ["POST /v1/enrichment/company — Apollo company lookup", "GET /v1/contacts/search — find decision-makers (VP Payments, CTO)", "POST /v1/sequences — enrol contacts into outbound sequence", "GET /v1/payments/transactions — pull merchant transaction history", "POST /v1/underwriting/evaluate — score merchant for cash advance"],
            "data_needed": ["Company firmographics (headcount, revenue, tech stack)", "Key decision-maker emails and LinkedIn profiles", "Recent hiring activity for payments engineering roles", "Merchant transaction volumes (last 12 months)", "Default rates by merchant segment"],
            "risk_checks": ["Verify PCI-DSS compliance before any data integration", "Confirm ASEAN data-residency requirements per country", "Validate AML/KYC pipeline covers all target geographies", "Stress-test underwriting model against 2x default scenario"],
            "gtm_steps": ["Enrich NovaPay profile via Apollo + Clearbit", "Identify VP-level contacts in payments and partnerships", "Draft personalised outreach referencing SE-Asia expansion", "Launch 3-touch email sequence with case-study attach", "Set follow-up cadence: Day 1, Day 4, Day 9", "Prepare merchant cash advance POC deck for first call"],
            "reusable_from_memory": [],
        },
        "LendStack": {
            "integration_plan": "Phase 1: API sandbox integration and model benchmarking. Phase 2: Connect internal credit data sources to LendStack pipeline. Phase 3: Co-market underwriting API to shared customer base.",
            "apis": ["POST /v1/enrichment/company — Apollo company lookup", "GET /v1/contacts/search — find Head of Partnerships", "GET /v1/opportunities — check existing CRM overlap", "POST /v1/underwriting/models — register custom credit model", "GET /v1/underwriting/decisions — pull decision audit trail"],
            "data_needed": ["API documentation and pricing model", "Current partner/customer list (public references)", "Founder backgrounds and investor syndicate", "Model performance benchmarks (Gini, KS, PSI)", "Data source catalogue and refresh frequencies"],
            "risk_checks": ["Audit model explainability for fair-lending compliance", "Review data-sharing agreement for PII handling", "Validate uptime SLA meets production requirements (99.95%+)", "Check vendor lock-in risk — can models be exported?"],
            "gtm_steps": ["Review public API docs and integration guides", "Identify partnership or BD leads via Apollo", "Prepare co-marketing proposal for underwriting API", "Schedule intro call within 10 business days", "Run sandbox POC with sample loan applications"],
            "reusable_from_memory": ["Reuse POST /v1/enrichment/company from NovaPay integration", "Reuse Apollo contact-search pipeline — same auth and pagination logic", "Reuse underwriting risk-check template from NovaPay (AML/KYC, compliance)"] if has_memory else [],
        },
        "VaultBridge": {
            "integration_plan": "Phase 1: Monitor only — track SOC 2 progress and team stability. Phase 2 (post-certification): Evaluate custody API for collateral management integration. Phase 3: Pilot collateralised lending product.",
            "apis": ["POST /v1/enrichment/company — Apollo company lookup", "GET /v1/contacts/search — find CEO / Head of BD", "GET /v1/custody/assets — retrieve custodied asset balances"],
            "data_needed": ["SOC 2 certification timeline and current status", "MPC technology vendor and architecture details", "Institutional AUM under custody", "Insurance coverage limits for custodied assets"],
            "risk_checks": ["Confirm SOC 2 Type II before any integration work", "Validate MPC key-recovery procedures under edge cases", "Review insurance adequacy for target AUM thresholds", "Assess post-acquisition team retention (key-person risk)"],
            "gtm_steps": ["Monitor SOC 2 progress — revisit after certification", "Add to watch-list; no active outreach at this stage", "Set 90-day reminder to re-evaluate fit", "Prepare collateral-lending concept note for future pitch"],
            "reusable_from_memory": ["Reuse POST /v1/enrichment/company from NovaPay integration", "Reuse Apollo contact-search and sequence-enrolment boilerplate", "Reuse regulatory risk-check framework from NovaPay (adapt for crypto regs)", "Shortcut: skip GTM outreach build — use existing sequence templates from LendStack"] if has_memory else [],
        },
    }
    match = _find_target_company(prompt, list(responses.keys()))
    return json.dumps(responses[match]) if match else json.dumps(responses["NovaPay"])


# ---------------------------------------------------------------------------
# Signal fetching — real APIs with mock fallback
# ---------------------------------------------------------------------------

def _build_search_queries(domain: dict) -> list[str]:
    """Build search queries tailored to the active domain."""
    base = [f"{term} startup raised funding 2026 India" for term in domain["search_terms"]]
    base.append(f"{domain['label']} fintech Series A B C India 2026")
    return base


def _fetch_serpapi(queries: list[str], max_results: int = 3) -> list[dict]:
    """Fetch search results from SerpAPI.com (Google Search API)."""
    api_key = os.environ.get("SERPAPI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("SERPAPI_API_KEY not set")

    results: list[dict] = []
    seen: set[str] = set()

    for query in queries:
        if len(results) >= max_results:
            break
        params = urllib.parse.urlencode({
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": max_results,
        })
        url = f"https://serpapi.com/search.json?{params}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())

        for item in data.get("organic_results", []):
            title = item.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            results.append({
                "name": title.split(" - ")[0].split(" | ")[0].strip()[:60],
                "description": item.get("snippet", ""),
                "source": item.get("link", ""),
            })
            if len(results) >= max_results:
                break

    return results


def _fetch_perplexity(queries: list[str], max_results: int = 3) -> list[dict]:
    """Fetch search results from Perplexity API."""
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise EnvironmentError("PERPLEXITY_API_KEY not set")

    combined_query = " OR ".join(queries)
    payload = json.dumps({
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return exactly 3 recent fintech signals as a JSON array. "
                    "Each object must have: name (company name), description "
                    "(one sentence), source (URL). Return ONLY the JSON array."
                ),
            },
            {"role": "user", "content": combined_query},
        ],
    }).encode()

    req = urllib.request.Request(
        "https://api.perplexity.ai/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    content = data["choices"][0]["message"]["content"]
    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(content)[:max_results]


def fetch_real_signals(domain: dict, max_results: int = 3) -> tuple[list[dict], str]:
    """Try SerpAPI first, then Perplexity. Returns (results, api_name)."""
    queries = _build_search_queries(domain)

    if os.environ.get("SERPAPI_API_KEY"):
        try:
            results = _fetch_serpapi(queries, max_results)
            if results:
                return results, "SerpAPI"
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as e:
            print(f"  \u26a0\ufe0f  SerpAPI failed: {e}")

    if os.environ.get("PERPLEXITY_API_KEY"):
        try:
            results = _fetch_perplexity(queries, max_results)
            if results:
                return results, "Perplexity"
        except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
            print(f"  \u26a0\ufe0f  Perplexity failed: {e}")

    return [], ""


def _mock_signals() -> list[Signal]:
    """Hardcoded fallback signals."""
    return [
        Signal(
            company="NovaPay",
            sector="Embedded Payments",
            trigger="Series B — $40M raised, expanding to Southeast Asia",
            source="mock/crunchbase",
        ),
        Signal(
            company="LendStack",
            sector="SMB Lending Infrastructure",
            trigger="Launched open API for underwriting-as-a-service",
            source="mock/techcrunch",
        ),
        Signal(
            company="VaultBridge",
            sector="Digital Asset Custody",
            trigger="Acquired MPC wallet startup, pursuing SOC 2 Type II",
            source="mock/coindesk",
        ),
    ]


def filter_signals(raw_results: list[dict], domain: dict) -> list[Signal]:
    """Use Claude to filter raw search results into clean company signals."""
    prompt = FILTER_PROMPT.format(
        results=json.dumps(raw_results, indent=2),
        domain_label=domain["label"],
        domain_focus=domain["focus"],
    )
    raw = call_claude(prompt, system=FILTER_SYSTEM)
    try:
        filtered = json.loads(raw)
        return [
            Signal(
                company=r["name"],
                sector=r.get("sector", "Fintech"),
                trigger=r.get("trigger", r.get("description", "")),
                source=r.get("source", ""),
            )
            for r in filtered
        ]
    except (json.JSONDecodeError, KeyError):
        # If filtering fails, pass through raw results unfiltered
        return [
            Signal(
                company=r["name"],
                sector="Fintech",
                trigger=r["description"],
                source=r["source"],
            )
            for r in raw_results
        ]


def fetch_signals(domain: dict) -> tuple[list[Signal], str]:
    """Fetch fintech signals — real APIs first, mock fallback."""
    real, api_name = fetch_real_signals(domain, max_results=10)
    if real:
        signals = filter_signals(real, domain)
        if signals:
            return signals, api_name

    return _mock_signals(), ""


def analyze_company(signal: Signal, domain: dict) -> Analysis:
    """Analyze a company signal via Claude, using domain context."""
    use_case_key = domain["use_case_key"]
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    system = ANALYSIS_SYSTEM.format(
        use_case_key=use_case_key,
        target_context=target_ctx,
    )
    prompt = ANALYSIS_PROMPT.format(
        company=signal.company,
        sector=signal.sector,
        trigger=signal.trigger,
        source=signal.source,
        domain_focus=domain["focus"],
        domain_apis=", ".join(domain["apis"]),
        domain_risks=", ".join(domain["risks"]),
        domain_label=domain["label"],
        analysis_lens=domain["analysis_lens"],
        target_context=target_ctx,
    )
    raw = call_claude(prompt, system=system)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Analysis(
            company=signal.company,
            business_model="Unable to parse analysis",
            lending_use_case="N/A",
            target_fit="Low",
            why="Claude returned malformed JSON — retry or check API",
            risks=["Parse failure — raw response could not be decoded"],
            opportunity_score=1,
        )
    return Analysis(
        company=signal.company,
        business_model=data.get("business_model", "Unknown"),
        lending_use_case=data.get(use_case_key, data.get("lending_use_case", "")),
        target_fit=data.get("target_fit", data.get("apollo_fit", "Medium")),
        why=data.get("why", ""),
        risks=data.get("risks", []),
        opportunity_score=data.get("opportunity_score", 1),
    )


def generate_execution_plan(analysis: Analysis, memory: dict, domain: dict) -> ExecutionPlan:
    """Generate an execution plan via Claude, enriched with memory and domain context."""
    analysis_summary = (
        f"Company: {analysis.company}\n"
        f"Business Model: {analysis.business_model}\n"
        f"{domain['label']} Use Case: {analysis.lending_use_case}\n"
        f"Target Fit: {analysis.target_fit}\n"
        f"Why: {analysis.why}\n"
        f"Risks: {', '.join(analysis.risks)}\n"
        f"Opportunity Score: {analysis.opportunity_score}/10"
    )
    memory_context = get_memory_context(memory)
    system = EXECUTION_SYSTEM.format(domain_label=domain["label"])
    prompt = EXECUTION_PROMPT.format(
        analysis=analysis_summary,
        memory=memory_context,
        domain_label=domain["label"],
        domain_focus=domain["focus"],
        domain_apis=", ".join(domain["apis"]),
        domain_risks=", ".join(domain["risks"]),
        execution_lens=domain["execution_lens"],
    )
    raw = call_claude(prompt, system=system)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ExecutionPlan(
            company=analysis.company,
            integration_plan="Unable to parse execution plan — retry or check API",
            apis=[],
            data_needed=[],
            risk_checks=[],
            gtm_steps=[],
            reusable_from_memory=[],
        )
    return ExecutionPlan(
        company=analysis.company,
        integration_plan=data.get("integration_plan", ""),
        apis=data.get("apis", []),
        data_needed=data.get("data_needed", []),
        risk_checks=data.get("risk_checks", []),
        gtm_steps=data.get("gtm_steps", []),
        reusable_from_memory=data.get("reusable_from_memory", []),
    )


# ---------------------------------------------------------------------------
# Rich UI
# ---------------------------------------------------------------------------

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.text import Text
from rich.rule import Rule

console = Console()


# ---------------------------------------------------------------------------
# Multi-agent dashboard
# ---------------------------------------------------------------------------

class AgentPanel:
    """A single agent's scrolling log panel."""

    MAX_LINES = 5

    def __init__(self, name: str, icon: str, style: str) -> None:
        self.name = name
        self.icon = icon
        self.style = style
        self.lines: list[str] = []
        self.active = False

    def log(self, message: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.lines.append(f"[dim]{ts}[/dim]  {message}")
        if len(self.lines) > self.MAX_LINES:
            self.lines = self.lines[-self.MAX_LINES:]
        self.active = True

    def render(self) -> Panel:
        status = f"[{self.style}]\u25cf[/{self.style}]" if self.active else "[dim]\u25cb[/dim]"
        body = "\n".join(self.lines) if self.lines else "[dim]Waiting...[/dim]"
        return Panel(
            body,
            title=f"{status} {self.icon} [{self.style}]{self.name}[/{self.style}]",
            border_style=self.style,
            padding=(1, 1),
        )


class Dashboard:
    """Thread-safe multi-agent dashboard with 2x2 grid + full-width delivery panel."""

    def __init__(self) -> None:
        self.signal = AgentPanel("SIGNAL AGENT", "\U0001f50e", "blue")
        self.analyst = AgentPanel("ANALYST AGENT", "\U0001f9e0", "yellow")
        self.execution = AgentPanel("EXECUTION AGENT", "\u2699\ufe0f ", "green")
        self.memory = AgentPanel("MEMORY AGENT", "\U0001f4be", "magenta")
        self.delivery = AgentPanel("DELIVERY AGENT", "\U0001f4e4", "cyan")
        self.status = "INITIALIZING"
        self.signals_found = 0
        self.analyzed = 0
        self.high_priority = 0
        self._live: Live | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self.status = "RUNNING"
        self._live = Live(self._build_layout(), console=console, refresh_per_second=4)
        self._live.start()

    def stop(self) -> None:
        with self._lock:
            if self._live:
                self.status = "COMPLETE"
                self._refresh()
                time.sleep(0.4)
                self._live.stop()
                self._live = None

    def log(self, agent: str, message: str, delay: float = 0.5) -> None:
        with self._lock:
            panel = self._get_panel(agent)
            panel.log(message)
            self._refresh()
        time.sleep(delay)

    def _get_panel(self, agent: str) -> AgentPanel:
        return {
            "SIGNAL": self.signal,
            "ANALYST": self.analyst,
            "EXECUTION": self.execution,
            "MEMORY": self.memory,
            "DELIVERY": self.delivery,
        }[agent]

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._build_layout())

    def _status_bar(self) -> Panel:
        if self.status == "RUNNING":
            s = "[bold green]\u25cf RUNNING[/bold green]"
        elif self.status == "COMPLETE":
            s = "[bold cyan]\u25cf COMPLETE[/bold cyan]"
        else:
            s = f"[bold yellow]\u25cf {self.status}[/bold yellow]"
        active = sum(1 for p in [self.signal, self.analyst, self.execution, self.memory, self.delivery] if p.active)
        body = (
            f" {s}  [dim]\u2502[/dim]  "
            f"Agents [bold]{active}[/bold]/5  [dim]\u2502[/dim]  "
            f"Signals [bold blue]{self.signals_found}[/bold blue]  [dim]\u2502[/dim]  "
            f"Analyzed [bold yellow]{self.analyzed}[/bold yellow]  [dim]\u2502[/dim]  "
            f"High Priority [bold green]{self.high_priority}[/bold green]"
        )
        return Panel(body, border_style="bright_blue", padding=(0, 0))

    def _build_layout(self) -> Group:
        layout = Layout()
        layout.split_column(
            Layout(name="top", ratio=2),
            Layout(name="bottom", ratio=1),
        )
        layout["top"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        layout["left"].split_column(
            Layout(self.signal.render(), name="signal"),
            Layout(self.memory.render(), name="memory"),
        )
        layout["right"].split_column(
            Layout(self.analyst.render(), name="analyst"),
            Layout(self.execution.render(), name="execution"),
        )
        layout["bottom"].update(self.delivery.render())
        return Group(self._status_bar(), layout)

AGENT_STYLES = {
    "SIGNAL":    ("bold blue",        "\U0001f50e SIGNAL AGENT"),
    "ANALYST":   ("bold yellow",      "\U0001f9e0 ANALYST AGENT"),
    "EXECUTION": ("bold green",       "\u2699\ufe0f  EXECUTION AGENT"),
    "MEMORY":    ("bold magenta",     "\U0001f4be MEMORY AGENT"),
    "DELIVERY":  ("bold cyan",        "\U0001f4e4 DELIVERY AGENT"),
}


def agent_log(agent: str, message: str, delay: float = 0.5) -> None:
    """Print a styled agent log line with a small delay."""
    style, label = AGENT_STYLES.get(agent, ("bold white", agent))
    console.print(f"[{style}]\\[{label}][/{style}] {message}")
    time.sleep(delay)


def print_company_dashboard(signal: Signal, analysis: Analysis, plan: ExecutionPlan, domain: dict) -> None:
    """Print a unified company dashboard panel with domain-specific labels."""
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    fit_color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(analysis.target_fit, "white")
    score_color = "green" if analysis.opportunity_score >= 7 else ("yellow" if analysis.opportunity_score >= 5 else "red")
    score_bar = "\u2588" * analysis.opportunity_score + "[dim]" + "\u2591" * (10 - analysis.opportunity_score) + "[/dim]"

    d_icon = domain.get("icon", "\U0001f6a8")
    use_case_label = domain.get("use_case_label", "Use Case")
    api_label = domain.get("api_section_label", "APIs")
    risk_label = domain.get("risk_section_label", "Risk Checks")
    flow_label = domain.get("flow_label", "")

    # Title line
    title = (
        f"\U0001f6a8 [bold]{analysis.company}[/bold]  "
        f"[{score_color}]{analysis.opportunity_score}/10[/{score_color}]  "
        f"[{fit_color}]\u25cf {analysis.target_fit} Fit[/{fit_color}]"
    )

    # --- Target context + domain badge ---
    domain_badge = (
        f"\U0001f3af [bold]Target Context: {target_ctx}[/bold]\n"
        f"\U0001f9ed {domain['label']}  [dim]\u2502  {flow_label}[/dim]"
    )

    # --- Opportunity section ---
    risks = "\n".join(f"    [red]\u2022[/red] {r}" for r in analysis.risks)
    opportunity = (
        f"{domain_badge}\n\n"
        f"[dim]\U0001f517 {signal.source}[/dim]\n\n"
        f"  [{score_color}]{score_bar}[/{score_color}]  {analysis.opportunity_score}/10\n"
        f"  \U0001f3af [{fit_color}]Fit for {target_ctx}: [bold]{analysis.target_fit}[/bold][/{fit_color}]\n\n"
        f"{d_icon} [bold]Business Model[/bold]\n"
        f"  {analysis.business_model}\n\n"
        f"\U0001f9e0 [bold]{use_case_label}[/bold]\n"
        f"  {analysis.lending_use_case}\n\n"
        f"\U0001f4a1 [bold]Why Now[/bold]\n"
        f"  {analysis.why}\n\n"
        f"\u26a0\ufe0f  [bold]Key Risks[/bold]\n{risks}"
    )

    # --- Execution section ---
    apis = "\n".join(f"    [green]\u2022[/green] {a}" for a in plan.apis[:5])
    steps = "\n".join(f"    [blue]\u2022[/blue] {s}" for s in plan.gtm_steps[:5])
    api_overflow = f"\n    [dim]+ {len(plan.apis) - 5} more[/dim]" if len(plan.apis) > 5 else ""
    step_overflow = f"\n    [dim]+ {len(plan.gtm_steps) - 5} more[/dim]" if len(plan.gtm_steps) > 5 else ""

    execution = (
        f"\U0001f680 [bold]Integration Plan[/bold]\n"
        f"  {plan.integration_plan}\n\n"
        f"[bold green]{api_label} ({len(plan.apis)}):[/bold green]\n{apis}{api_overflow}\n\n"
        f"[bold blue]GTM Steps ({len(plan.gtm_steps)}):[/bold blue]\n{steps}{step_overflow}"
    )

    if plan.reusable_from_memory:
        reuse = "\n".join(f"    [magenta]\u2192[/magenta] {r}" for r in plan.reusable_from_memory)
        execution += f"\n\n[bold magenta]\U0001f504 Reusable from Memory ({len(plan.reusable_from_memory)}):[/bold magenta]\n{reuse}"

    # --- Risk checks as compact table ---
    risk_table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    risk_table.add_column(ratio=1)
    for check in plan.risk_checks[:4]:
        risk_table.add_row(f"  [yellow]\u25b6[/yellow] {check}")
    if len(plan.risk_checks) > 4:
        risk_table.add_row(f"  [dim]+ {len(plan.risk_checks) - 4} more[/dim]")

    # --- Compose full body ---
    body = (
        f"{opportunity}\n\n"
        f"{'─' * 60}\n\n"
        f"{execution}\n\n"
        f"{'─' * 60}\n\n"
        f"[bold yellow]{risk_label} ({len(plan.risk_checks)}):[/bold yellow]"
    )

    console.print(Panel(body, title=title, border_style=fit_color, padding=(1, 2)))
    console.print(risk_table)
    console.print()


# ---------------------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------------------

TELEGRAM_MAX_LENGTH = 4096


def send_to_telegram(message: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    # Split into chunks if message exceeds Telegram limit
    chunks = _split_message(message, TELEGRAM_MAX_LENGTH)
    for chunk in chunks:
        payload = json.dumps({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if not data.get("ok"):
                    print(f"  [warn] Telegram API error: {data}")
                    return False
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            print(f"  [warn] Telegram send failed: {e}")
            return False
    return True


def _split_message(text: str, max_len: int) -> list[str]:
    """Split text into chunks that fit within Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Find last newline before the limit to split cleanly
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_telegram_message(
    results: list[tuple[Signal, Analysis, ExecutionPlan]],
    memory: dict,
    domain: dict,
) -> str:
    """Format the top 2 opportunities + summary for Telegram."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    use_case_label = domain.get("use_case_label", "Use Case")

    top = sorted(results, key=lambda r: r[1].opportunity_score, reverse=True)[:2]

    lines: list[str] = []
    lines.append(f"\U0001f4e1 <b>Founder Intelligence Copilot</b>")
    lines.append(f"\U0001f552 {ts}")
    lines.append(f"\U0001f3af Target: <b>{_escape_html(target_ctx)}</b>")
    lines.append(f"\U0001f9ed Domain: {_escape_html(domain['label'])}")
    lines.append("")

    for signal, analysis, plan in top:
        fit_icon = {
            "High": "\U0001f7e2",
            "Medium": "\U0001f7e1",
            "Low": "\U0001f534",
        }.get(analysis.target_fit, "\u26aa")

        lines.append(f"\U0001f6a8 <b>{_escape_html(analysis.company)}</b>  \u2014  {analysis.opportunity_score}/10")
        lines.append(f"{fit_icon} \U0001f3af Fit for {_escape_html(target_ctx)}: {analysis.target_fit}")
        lines.append(f"\U0001f517 {_escape_html(signal.source)}")
        lines.append("")
        lines.append(f"<b>What they do:</b> {_escape_html(analysis.business_model[:200])}")
        lines.append("")
        lines.append(f"<b>{_escape_html(use_case_label)}:</b> {_escape_html(analysis.lending_use_case[:200])}")
        lines.append("")
        lines.append(f"<b>Why ({_escape_html(target_ctx)}):</b> {_escape_html(analysis.why[:200])}")
        lines.append("")

        risks = " | ".join(_escape_html(r) for r in analysis.risks[:2])
        lines.append(f"\u26a0\ufe0f <b>Risks:</b> {risks}")
        lines.append("")

        gtm = "\n".join(f"  \u2022 {_escape_html(s)}" for s in plan.gtm_steps[:3])
        lines.append(f"\U0001f680 <b>Next steps:</b>\n{gtm}")
        lines.append("")
        lines.append("\u2500" * 30)
        lines.append("")

    companies = memory.get("companies", {})
    if companies:
        lines.append(f"\U0001f9e0 <b>Memory:</b> {len(companies)} companies tracked")
        for name, entry in companies.items():
            a = entry["analysis"]
            fit = a.get("target_fit", a.get("apollo_fit", "N/A"))
            lines.append(f"  \u2022 {_escape_html(name)} \u2014 {fit} fit, {a['opportunity_score']}/10")
    lines.append("")
    lines.append("\U0001f916 <i>Generated by Founder Intelligence Copilot</i>")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Email notifications
# ---------------------------------------------------------------------------

EMAIL_SUBJECT = "Daily Fintech Intelligence Report"


def send_email(report: str) -> bool:
    """Send a plain-text email via SMTP. Returns True on success."""
    user = os.environ.get("EMAIL_USER", "")
    password = os.environ.get("EMAIL_PASS", "")
    to_addr = os.environ.get("EMAIL_TO", "")
    if not all([user, password, to_addr]):
        return False

    msg = EmailMessage()
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(report)

    # Detect SMTP host from email domain (or EMAIL_SMTP_HOST override)
    smtp_override = os.environ.get("EMAIL_SMTP_HOST", "")
    if smtp_override:
        host, _, port_str = smtp_override.partition(":")
        port = int(port_str) if port_str else 587
    else:
        domain = user.split("@")[-1].lower()
        smtp_hosts = {
            "gmail.com": ("smtp.gmail.com", 587),
            "googlemail.com": ("smtp.gmail.com", 587),
            "outlook.com": ("smtp-mail.outlook.com", 587),
            "hotmail.com": ("smtp-mail.outlook.com", 587),
            "yahoo.com": ("smtp.mail.yahoo.com", 587),
        }
        host, port = smtp_hosts.get(domain, ("smtp.gmail.com", 587))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"  [warn] Email send failed: {e}")
        return False


def format_email_report(
    results: list[tuple[Signal, Analysis, ExecutionPlan]],
    memory: dict,
    domain: dict,
) -> str:
    """Format a plain-text email with top opportunities + summary."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    use_case_label = domain.get("use_case_label", "Use Case")
    top = sorted(results, key=lambda r: r[1].opportunity_score, reverse=True)[:2]

    lines: list[str] = []
    lines.append("FOUNDER INTELLIGENCE COPILOT")
    lines.append(f"Generated: {ts}")
    lines.append(f"Target Context: {target_ctx}")
    lines.append(f"Domain: {domain['label']}")
    lines.append("=" * 50)
    lines.append("")

    for signal, analysis, plan in top:
        lines.append(f"OPPORTUNITY: {analysis.company}  —  Score: {analysis.opportunity_score}/10")
        lines.append(f"Fit for {target_ctx}: {analysis.target_fit}")
        lines.append(f"Source: {signal.source}")
        lines.append("")
        lines.append(f"Business Model:")
        lines.append(f"  {analysis.business_model[:300]}")
        lines.append("")
        lines.append(f"{use_case_label}:")
        lines.append(f"  {analysis.lending_use_case[:300]}")
        lines.append("")
        lines.append(f"Why ({target_ctx}):")
        lines.append(f"  {analysis.why[:300]}")
        lines.append("")
        lines.append("Risks:")
        for r in analysis.risks[:3]:
            lines.append(f"  - {r}")
        lines.append("")
        lines.append("Next Steps:")
        for s in plan.gtm_steps[:4]:
            lines.append(f"  * {s}")
        lines.append("")
        lines.append("-" * 50)
        lines.append("")

    companies = memory.get("companies", {})
    if companies:
        lines.append(f"MEMORY: {len(companies)} companies tracked")
        lines.append("")
        for name, entry in companies.items():
            a = entry["analysis"]
            fit = a.get("target_fit", a.get("apollo_fit", "N/A"))
            lines.append(f"  {name} — {fit} fit, {a['opportunity_score']}/10")
        lines.append("")

    lines.append("-" * 50)
    lines.append("Generated by Founder Intelligence Copilot")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Single-company scan (used by Telegram bot)
# ---------------------------------------------------------------------------

def scan_company(company: str, domain: dict) -> str:
    """Run the full pipeline for a single company and return formatted text."""
    memory = load_memory()

    signal = Signal(
        company=company,
        sector=domain["label"],
        trigger=f"Manual scan requested for {company}",
        source="telegram/scan",
    )

    analysis = analyze_company(signal, domain)
    plan = generate_execution_plan(analysis, memory, domain)

    save_to_memory(company, analysis, memory)
    memory["companies"][company]["sector"] = signal.sector
    save_memory(memory)

    # Build plain-text report for Telegram
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    fit_icon = {"High": "\U0001f7e2", "Medium": "\U0001f7e1", "Low": "\U0001f534"}.get(analysis.target_fit, "")
    risks = "\n".join(f"  \u2022 {r}" for r in analysis.risks)
    apis = "\n".join(f"  \u2022 {a}" for a in plan.apis[:5])
    steps = "\n".join(f"  \u2022 {s}" for s in plan.gtm_steps[:4])
    reuse = ""
    if plan.reusable_from_memory:
        items = "\n".join(f"  \u2192 {r}" for r in plan.reusable_from_memory)
        reuse = f"\n\U0001f504 <b>Reusable Patterns:</b>\n{items}\n"

    return (
        f"\U0001f6a8 <b>Scan: {_escape_html(company)}</b>\n"
        f"Domain: {_escape_html(domain['label'])}\n\n"
        f"<b>Business Model:</b>\n  {_escape_html(analysis.business_model[:300])}\n\n"
        f"<b>{_escape_html(domain['label'])} Use Case:</b>\n  {_escape_html(analysis.lending_use_case[:300])}\n\n"
        f"{fit_icon} \U0001f3af <b>Fit for {_escape_html(target_ctx)}:</b> {analysis.target_fit}  |  "
        f"<b>Score:</b> {analysis.opportunity_score}/10\n\n"
        f"<b>Why:</b>\n  {_escape_html(analysis.why[:300])}\n\n"
        f"\u26a0\ufe0f <b>Risks:</b>\n{_escape_html(risks)}\n\n"
        f"\U0001f680 <b>Integration Plan:</b>\n  {_escape_html(plan.integration_plan[:300])}\n\n"
        f"<b>APIs ({len(plan.apis)}):</b>\n{_escape_html(apis)}\n\n"
        f"<b>GTM Steps ({len(plan.gtm_steps)}):</b>\n{_escape_html(steps)}\n"
        f"{reuse}\n"
        f"\U0001f916 <i>Founder Intelligence Copilot</i>"
    )


# ---------------------------------------------------------------------------
# Telegram bot (polling mode)
# ---------------------------------------------------------------------------

def _telegram_get_updates(token: str, offset: int) -> list[dict]:
    """Fetch new updates from Telegram Bot API."""
    params = urllib.parse.urlencode({"offset": offset, "timeout": 30})
    url = f"https://api.telegram.org/bot{token}/getUpdates?{params}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode())
        return data.get("result", [])
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return []


def _telegram_reply(token: str, chat_id: int, text: str) -> None:
    """Send a reply to a specific Telegram chat."""
    chunks = _split_message(text, TELEGRAM_MAX_LENGTH)
    for chunk in chunks:
        payload = json.dumps({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except urllib.error.URLError:
            pass


AUTO_SCAN_QUERIES = [
    "fast growing NBFC or lending startups India",
    "lending fintech funding news India 2026",
    "fintech product launch lending India",
]

AUTO_SCAN_INTERVAL = 300  # seconds between auto-scans


def auto_scan(token: str, chat_id: int) -> None:
    """Fetch trending lending signals and send reports to Telegram."""
    domain = get_domain("lending")
    console.print("  [magenta]Auto-scan: fetching lending signals...[/magenta]")

    # Fetch raw results using auto-scan queries
    raw: list[dict] = []
    if os.environ.get("SERPAPI_API_KEY"):
        try:
            raw = _fetch_serpapi(AUTO_SCAN_QUERIES, max_results=8)
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError) as e:
            console.print(f"  [yellow]Auto-scan search failed: {e}[/yellow]")

    if not raw:
        console.print("  [dim]Auto-scan: no results from search, skipping.[/dim]")
        return

    # Filter to real company signals
    signals = filter_signals(raw, domain)
    if not signals:
        console.print("  [dim]Auto-scan: no company signals after filtering.[/dim]")
        return

    console.print(f"  [magenta]Auto-scan: found {len(signals)} companies, analyzing...[/magenta]")

    memory = load_memory()
    seen = set(memory.get("companies", {}).keys())
    sent = 0

    for signal in signals:
        # Skip companies already in memory
        if signal.company in seen:
            console.print(f"  [dim]Auto-scan: skipping {signal.company} (already tracked)[/dim]")
            continue

        try:
            analysis = analyze_company(signal, domain)

            # Only send high-growth / high-score signals
            if analysis.opportunity_score < 5:
                console.print(f"  [dim]Auto-scan: {signal.company} scored {analysis.opportunity_score}/10, skipping.[/dim]")
                continue

            plan = generate_execution_plan(analysis, memory, domain)
            save_to_memory(signal.company, analysis, memory)
            memory["companies"][signal.company]["sector"] = signal.sector

            # Build and send report
            fit_icon = {"High": "\U0001f7e2", "Medium": "\U0001f7e1", "Low": "\U0001f534"}.get(analysis.target_fit, "")
            risks = "\n".join(f"  \u2022 {r}" for r in analysis.risks)
            steps = "\n".join(f"  \u2022 {s}" for s in plan.gtm_steps[:3])

            report = (
                f"\U0001f4e1 <b>Auto-Scan Alert</b>\n"
                f"[dim]Domain: Lending & Credit[/dim]\n\n"
                f"\U0001f6a8 <b>{_escape_html(signal.company)}</b>\n"
                f"\U0001f517 {_escape_html(signal.source)}\n"
                f"Trigger: {_escape_html(signal.trigger[:200])}\n\n"
                f"<b>Business Model:</b>\n  {_escape_html(analysis.business_model[:250])}\n\n"
                f"<b>Lending Use Case:</b>\n  {_escape_html(analysis.lending_use_case[:250])}\n\n"
                f"{fit_icon} \U0001f3af <b>Fit:</b> {analysis.target_fit}  |  "
                f"<b>Score:</b> {analysis.opportunity_score}/10\n\n"
                f"<b>Why:</b>\n  {_escape_html(analysis.why[:250])}\n\n"
                f"\u26a0\ufe0f <b>Risks:</b>\n{_escape_html(risks)}\n\n"
                f"\U0001f680 <b>Next Steps:</b>\n{_escape_html(steps)}\n\n"
                f"\U0001f916 <i>Auto-generated by Founder Intelligence Copilot</i>"
            )
            _telegram_reply(token, chat_id, report)
            console.print(f"  [green]\u2705 Auto-scan: sent {signal.company}[/green]")
            sent += 1

        except Exception as e:
            console.print(f"  [red]Auto-scan: error on {signal.company}: {e}[/red]")

    save_memory(memory)
    console.print(f"  [magenta]Auto-scan complete: {sent} reports sent.[/magenta]")


def run_telegram_bot() -> None:
    """Run the Telegram bot in long-polling mode, listening for /scan commands."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token:
        console.print("[red]TELEGRAM_BOT_TOKEN not set. Cannot start bot.[/red]")
        return

    console.print(Panel(
        "[bold white]Founder Intelligence Copilot \u2014 Telegram Bot Mode[/bold white]\n"
        f"[dim]Listening for commands... (Ctrl+C to stop)[/dim]\n\n"
        f"[bold]Commands:[/bold]\n"
        f"  /scan <company> <domain>  \u2014  Scan a company\n"
        f"  /scan <company>           \u2014  Scan with default domain (lending)\n"
        f"  /autoscan                 \u2014  Fetch trending lending signals\n"
        f"  /domains                  \u2014  List available domains\n"
        f"  /help                     \u2014  Show help",
        border_style="cyan",
        padding=(1, 2),
    ))

    offset = 0

    while True:
        try:
            updates = _telegram_get_updates(token, offset)
        except KeyboardInterrupt:
            console.print("\n[dim]Bot stopped.[/dim]")
            return

        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            msg_chat_id = msg.get("chat", {}).get("id")
            if not text or not msg_chat_id:
                continue

            console.print(f"[dim]Received:[/dim] {text} [dim]from {msg_chat_id}[/dim]")

            if text.startswith("/scan"):
                parts = text.split(maxsplit=2)
                if len(parts) < 2:
                    _telegram_reply(token, msg_chat_id,
                        "\u26a0\ufe0f Usage: /scan <company> [domain]\n\n"
                        f"Domains: {', '.join(DOMAIN_CONFIG.keys())}\n"
                        f"Default: {DEFAULT_DOMAIN}")
                    continue

                company = parts[1]
                domain_name = parts[2] if len(parts) > 2 else None
                domain = get_domain(domain_name)

                _telegram_reply(token, msg_chat_id,
                    f"\U0001f50e Scanning <b>{_escape_html(company)}</b> "
                    f"in {_escape_html(domain['label'])} domain...\n"
                    f"This may take 30\u201360 seconds.")

                console.print(f"  [blue]Scanning {company} ({domain['label']})...[/blue]")
                try:
                    report = scan_company(company, domain)
                    _telegram_reply(token, msg_chat_id, report)
                    console.print(f"  [green]\u2705 Sent report for {company}[/green]")
                except Exception as e:
                    _telegram_reply(token, msg_chat_id,
                        f"\u274c Scan failed: {_escape_html(str(e))}")
                    console.print(f"  [red]\u274c Error scanning {company}: {e}[/red]")

            elif text.startswith("/autoscan"):
                _telegram_reply(token, msg_chat_id,
                    "\U0001f50e Running auto-scan for lending signals...")
                try:
                    auto_scan(token, msg_chat_id)
                except Exception as e:
                    _telegram_reply(token, msg_chat_id,
                        f"\u274c Auto-scan failed: {_escape_html(str(e))}")

            elif text.startswith("/domains"):
                lines = [f"\U0001f4cb <b>Available Domains:</b>\n"]
                for key, cfg in DOMAIN_CONFIG.items():
                    lines.append(f"  \u2022 <b>{key}</b> \u2014 {_escape_html(cfg['label'])}")
                    lines.append(f"    {_escape_html(cfg['focus'][:80])}")
                lines.append(f"\nDefault: {DEFAULT_DOMAIN}")
                _telegram_reply(token, msg_chat_id, "\n".join(lines))

            elif text.startswith("/help"):
                _telegram_reply(token, msg_chat_id,
                    "\U0001f916 <b>Founder Intelligence Copilot</b>\n\n"
                    "<b>Commands:</b>\n"
                    "  /scan razorpay payments \u2014 Scan a company in a domain\n"
                    "  /scan plum insurance \u2014 Scan with insurance lens\n"
                    "  /scan kreditbee \u2014 Scan with default (lending)\n"
                    "  /autoscan \u2014 Trigger auto-scan now\n"
                    "  /domains \u2014 List available domains\n"
                    "  /help \u2014 Show this message")

        # No automatic scanning — bot only responds to user commands


def print_memory_summary(memory: dict) -> None:
    companies = memory.get("companies", {})
    if not companies:
        return
    table = Table(title="\U0001f9e0 Memory", title_style="bold magenta", border_style="magenta", show_lines=False)
    table.add_column("Date", style="dim")
    table.add_column("Company", style="bold")
    table.add_column("Fit", justify="center")
    table.add_column("Score", justify="center")
    for name, entry in companies.items():
        a = entry["analysis"]
        ts = entry["analysed_at"][:10]
        fit_val = a.get("target_fit", a.get("apollo_fit", "N/A"))
        fit_color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(fit_val, "white")
        table.add_row(ts, name, f"[{fit_color}]{fit_val}[/{fit_color}]", f"{a['opportunity_score']}/10")
    console.print(table)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def print_banner(search_api: str, claude_live: bool, domain: dict) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    is_live = search_api and claude_live

    title = "\U0001f4e1 Live Market Scan" if is_live else "\U0001f4e1 Market Scan"
    d_icon = domain.get("icon", "")
    search_line = (
        f"[green]\u2705 Search signals  \u2014 {search_api} API[/green]"
        if search_api
        else "[yellow]\u26a0\ufe0f  Search signals  \u2014 cached/mock data[/yellow]"
    )
    claude_line = (
        f"[green]\u2705 Analysis engine \u2014 Claude ({CLAUDE_MODEL})[/green]"
        if claude_live
        else "[yellow]\u26a0\ufe0f  Analysis engine \u2014 cached/mock data[/yellow]"
    )
    target_ctx = domain.get("target_context", DEFAULT_TARGET)
    domain_line = f"\U0001f9ed Domain: [bold]{domain['label']}[/bold]  [dim]\u2502  {domain['flow_label']}[/dim]"
    target_line = f"\U0001f3af Target Context: [bold]{target_ctx}[/bold]"
    body = f"[dim]\U0001f552 {ts}[/dim]\n\n{target_line}\n{domain_line}\n\n{search_line}\n{claude_line}"
    console.print(Panel(body, title=f"[bold]{title}[/bold]", subtitle="Founder Intelligence Copilot", border_style="bright_blue", padding=(1, 2)))


def run(domain_name: str | None = None, target: str | None = None) -> None:
    domain = get_domain(domain_name)
    if target:
        domain["target_context"] = target
    claude_live = bool(os.environ.get("ANTHROPIC_API_KEY"))
    dash = Dashboard()

    # Shared state between threads
    memory: dict = {}
    memory_lock = threading.Lock()
    signals: list[Signal] = []
    search_api = ""
    results: list[tuple[Signal, Analysis, ExecutionPlan]] = []
    results_lock = threading.Lock()
    telegram_ok = False
    email_ok = False

    # Coordination events
    memory_loaded = threading.Event()
    signals_ready = threading.Event()
    analysis_done = threading.Event()
    delivery_done = threading.Event()

    # --- Agent threads ---

    def memory_agent() -> None:
        nonlocal memory
        dash.log("MEMORY", "Loading past analyses...", 0.5)
        mem = load_memory()
        with memory_lock:
            memory.update(mem)
        stored = len(memory.get("companies", {}))
        dash.log("MEMORY", f"Loaded [bold]{stored}[/bold] companies.", 0.3)
        memory_loaded.set()

        # Wait for signals, then assist during analysis
        signals_ready.wait()
        for signal in signals:
            mem_count = len(memory.get("companies", {}))
            dash.log("MEMORY", f"Checking patterns ({mem_count} stored)...", 0.4)
            time.sleep(0.3)

        # Wait for analysis to finish, then persist
        analysis_done.wait()
        for _, analysis, _ in results:
            with memory_lock:
                save_to_memory(analysis.company, analysis, memory)
            dash.log("MEMORY", f"Saved [bold]{analysis.company}[/bold].", 0.3)

        num_reuses = sum(len(p.reusable_from_memory) for _, _, p in results)
        if num_reuses:
            dash.log("MEMORY", f"[bold]{num_reuses}[/bold] patterns reused.", 0.4)

        with memory_lock:
            save_memory(memory)
        dash.log("MEMORY", f"[bold]{len(memory.get('companies', {}))}[/bold] companies tracked.", 0.3)

    def signal_agent() -> None:
        nonlocal signals, search_api
        memory_loaded.wait()
        dash.log("SIGNAL", f"Scanning [bold]{domain['label']}[/bold] signals...", 0.7)
        sigs, api = fetch_signals(domain)
        signals.extend(sigs)
        search_api = api
        with dash._lock:
            dash.signals_found = len(signals)
        dash.log("SIGNAL", f"Found [bold]{len(signals)}[/bold] companies.", 0.5)
        for s in signals:
            dash.log("SIGNAL", f"[dim]\u2192[/dim] {s.company}", 0.2)
        dash.log("SIGNAL", "[bold]Signal scan complete.[/bold]", 0.3)
        signals_ready.set()

    def analyst_agent() -> None:
        signals_ready.wait()
        for i, signal in enumerate(signals, 1):
            dash.log("ANALYST", f"Evaluating [bold]{signal.company}[/bold] ({i}/{len(signals)})...", 0.7)
            analysis = analyze_company(signal, domain)
            with dash._lock:
                dash.analyzed = i
                if analysis.target_fit == "High":
                    dash.high_priority += 1
            fit_tag = {"High": "[green]High[/green]", "Medium": "[yellow]Medium[/yellow]", "Low": "[red]Low[/red]"}.get(analysis.target_fit, analysis.target_fit)
            dash.log("ANALYST", f"{signal.company} \u2192 {analysis.opportunity_score}/10 {fit_tag}", 0.3)

            # Execution runs in parallel per company
            dash.log("EXECUTION", f"Building plan: [bold]{signal.company}[/bold]...", 0.7)
            plan = generate_execution_plan(analysis, memory, domain)
            dash.log("EXECUTION", f"{len(plan.apis)} APIs \u2022 {len(plan.gtm_steps)} GTM steps", 0.3)
            if plan.reusable_from_memory:
                dash.log("EXECUTION", f"[magenta]{len(plan.reusable_from_memory)} reusable[/magenta]", 0.2)

            with results_lock:
                results.append((signal, analysis, plan))

        num_high = dash.high_priority
        dash.log("ANALYST", f"[bold green]{num_high}[/bold green] high-fit shortlisted.", 0.4)
        analysis_done.set()

    def delivery_agent() -> None:
        nonlocal telegram_ok, email_ok
        analysis_done.wait()
        dash.log("DELIVERY", "Preparing reports...", 0.5)

        summary_text = format_telegram_message(results, memory, domain)
        full_report = format_email_report(results, memory, domain)

        if os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"):
            dash.log("DELIVERY", "Sending Telegram...", 0.5)
            telegram_ok = send_to_telegram(summary_text)
            dash.log("DELIVERY", "[green]\u2705 Telegram sent[/green]" if telegram_ok else "[red]\u274c Telegram failed[/red]", 0.3)
        else:
            dash.log("DELIVERY", "[dim]Telegram \u2014 no credentials[/dim]", 0.3)

        if os.environ.get("EMAIL_USER") and os.environ.get("EMAIL_PASS") and os.environ.get("EMAIL_TO"):
            dash.log("DELIVERY", "Sending email...", 0.5)
            email_ok = send_email(full_report)
            dash.log("DELIVERY", "[green]\u2705 Email sent[/green]" if email_ok else "[red]\u274c Email failed[/red]", 0.3)
        else:
            dash.log("DELIVERY", "[dim]Email \u2014 no credentials[/dim]", 0.3)

        dash.log("DELIVERY", "[bold]All tasks complete.[/bold]", 0.3)
        delivery_done.set()

    # --- Header ---
    console.print()
    console.print(
        Panel(
            f"[bold white]Founder Intelligence Copilot \u2014 Live Agent System[/bold white]\n"
            f"\U0001f3af Target: [bold]{domain.get('target_context', DEFAULT_TARGET)}[/bold]  [dim]\u2502[/dim]  "
            f"\U0001f9ed Domain: [bold]{domain['label']}[/bold]",
            border_style="bright_blue",
            padding=(0, 2),
        )
    )
    console.print()

    # --- Launch dashboard + threads ---
    dash.start()

    threads = [
        threading.Thread(target=memory_agent, name="MemoryAgent", daemon=True),
        threading.Thread(target=signal_agent, name="SignalAgent", daemon=True),
        threading.Thread(target=analyst_agent, name="AnalystAgent", daemon=True),
        threading.Thread(target=delivery_agent, name="DeliveryAgent", daemon=True),
    ]
    for t in threads:
        t.start()

    # Wait for full pipeline to complete
    delivery_done.wait()
    time.sleep(0.5)
    dash.stop()

    # --- Static output: banner + results ---
    print_banner(search_api, claude_live, domain)

    for i, (signal, analysis, plan) in enumerate(results, 1):
        console.print()
        console.print(Rule(f"[bold]Signal {i}/{len(results)}[/bold]", style="bright_blue"))
        console.print()
        print_company_dashboard(signal, analysis, plan, domain)

    console.print()
    print_memory_summary(memory)

    # --- Agent Summary table ---
    num_high = dash.high_priority
    num_reuses = sum(len(p.reusable_from_memory) for _, _, p in results)
    delivery_items: list[str] = []
    if telegram_ok:
        delivery_items.append("Telegram")
    if email_ok:
        delivery_items.append("Email")
    delivery_status = ", ".join(delivery_items) if delivery_items else "None"

    summary_table = Table(title="\U0001f916 Agent Summary", title_style="bold", border_style="bright_blue", show_lines=False, padding=(0, 2))
    summary_table.add_column("Agent", style="bold")
    summary_table.add_column("Result")
    summary_table.add_row("[blue]\U0001f50e Signal Agent[/blue]", f"{len(signals)} signals fetched")
    summary_table.add_row("[yellow]\U0001f9e0 Analyst Agent[/yellow]", f"{len(results)} companies analyzed")
    summary_table.add_row("[green]\u2699\ufe0f  Execution Agent[/green]", f"{num_high} high-fit opportunities")
    summary_table.add_row("[magenta]\U0001f4be Memory Agent[/magenta]", f"{num_reuses} patterns reused")
    summary_table.add_row("[cyan]\U0001f4e4 Delivery Agent[/cyan]", f"{delivery_status} sent")

    console.print()
    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    domain_arg = None
    target_arg = None

    # Parse --target "Some Context" from args
    filtered: list[str] = []
    i = 0
    while i < len(args):
        if args[i] == "--target" and i + 1 < len(args):
            target_arg = args[i + 1]
            i += 2
        else:
            filtered.append(args[i])
            i += 1

    first = filtered[0] if filtered else None

    second = filtered[1] if len(filtered) > 1 else None
    known = set(DOMAIN_CONFIG.keys()) | {"bot", "--help", "-h"}

    if first in ("--help", "-h"):
        print("Usage: python copilot.py [domain] [--target \"Company (Context)\"]")
        print("       python copilot.py <company> <domain> [--target \"...\"]")
        print()
        print("Modes:")
        print("  bot                           Start Telegram bot")
        print(f"  <domain>                      Full scan (domains: {', '.join(DOMAIN_CONFIG.keys())})")
        print(f"  (no argument)                 Full scan with default domain ({DEFAULT_DOMAIN})")
        print(f"  <company> <domain>            Scan a single company in a domain")
        print()
        print("Options:")
        print("  --target \"Name (Context)\"    Set custom target context for fit evaluation")
        print()
        print("Examples:")
        print("  python copilot.py lending --target \"Apollo Finvest (NBFC Lending)\"")
        print("  python copilot.py payments --target \"Razorpay (Payment Infra)\"")
        print("  python copilot.py volopay payments --target \"PhonePe (UPI Payments)\"")
        print("  python copilot.py kreditbee lending")
        print("  python copilot.py                  # defaults to lending domain")
        sys.exit(0)

    if first == "bot":
        run_telegram_bot()
    elif first and first not in known:
        # First arg is a company name, second is optional domain
        domain = get_domain(second)
        if target_arg:
            domain["target_context"] = target_arg
        target_ctx = domain.get("target_context", DEFAULT_TARGET)

        # --- Header ---
        console.print()
        console.print(Panel(
            f"[bold white]Founder Intelligence Copilot \u2014 Single Company Scan[/bold white]\n"
            f"\U0001f3af Target: [bold]{target_ctx}[/bold]  [dim]\u2502[/dim]  "
            f"\U0001f9ed Domain: [bold]{domain['label']}[/bold]",
            border_style="bright_blue",
            padding=(0, 2),
        ))
        console.print()

        # --- Live dashboard for single company ---
        dash = Dashboard()
        dash.start()

        signal = Signal(
            company=first,
            sector=domain["label"],
            trigger=f"Manual scan requested for {first}",
            source="cli/scan",
        )

        dash.log("MEMORY", "Loading past analyses...", 0.5)
        memory = load_memory()
        stored = len(memory.get("companies", {}))
        dash.log("MEMORY", f"Loaded [bold]{stored}[/bold] companies.", 0.3)

        dash.log("SIGNAL", f"Target: [bold]{first}[/bold]", 0.5)
        dash.signals_found = 1

        dash.log("ANALYST", f"Evaluating [bold]{first}[/bold]...", 0.7)
        analysis = analyze_company(signal, domain)
        dash.analyzed = 1
        if analysis.target_fit == "High":
            dash.high_priority = 1
        fit_tag = {"High": "[green]High[/green]", "Medium": "[yellow]Medium[/yellow]", "Low": "[red]Low[/red]"}.get(analysis.target_fit, analysis.target_fit)
        dash.log("ANALYST", f"{first} \u2192 {analysis.opportunity_score}/10 {fit_tag}", 0.3)

        mem_count = len(memory.get("companies", {}))
        dash.log("MEMORY", f"Checking patterns ({mem_count} stored)...", 0.4)

        dash.log("EXECUTION", f"Building plan for [bold]{first}[/bold]...", 0.7)
        plan = generate_execution_plan(analysis, memory, domain)
        dash.log("EXECUTION", f"{len(plan.apis)} APIs \u2022 {len(plan.gtm_steps)} GTM steps", 0.3)
        if plan.reusable_from_memory:
            dash.log("EXECUTION", f"[magenta]{len(plan.reusable_from_memory)} reusable patterns[/magenta]", 0.2)

        dash.log("MEMORY", f"Saved [bold]{first}[/bold].", 0.3)
        save_to_memory(first, analysis, memory)
        memory["companies"][first]["sector"] = signal.sector
        save_memory(memory)

        # Delivery
        telegram_report = scan_company(first, domain)
        telegram_ok = False
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        chat_id_env = os.environ.get("TELEGRAM_CHAT_ID", "")
        if token and chat_id_env:
            dash.log("DELIVERY", "Sending Telegram...", 0.5)
            telegram_ok = send_to_telegram(telegram_report)
            dash.log("DELIVERY", "[green]\u2705 Telegram sent[/green]" if telegram_ok else "[red]\u274c Telegram failed[/red]", 0.3)
        else:
            dash.log("DELIVERY", "[dim]Telegram \u2014 no credentials[/dim]", 0.3)

        email_ok = False
        if os.environ.get("EMAIL_USER") and os.environ.get("EMAIL_PASS") and os.environ.get("EMAIL_TO"):
            dash.log("DELIVERY", "Sending email...", 0.5)
            email_report = format_email_report([(signal, analysis, plan)], memory, domain)
            email_ok = send_email(email_report)
            dash.log("DELIVERY", "[green]\u2705 Email sent[/green]" if email_ok else "[red]\u274c Email failed[/red]", 0.3)
        else:
            dash.log("DELIVERY", "[dim]Email \u2014 no credentials[/dim]", 0.3)

        dash.log("DELIVERY", "[bold]All tasks complete.[/bold]", 0.5)
        dash.stop()

        # --- Static output ---
        console.print()
        print_company_dashboard(signal, analysis, plan, domain)

        # --- Agent Summary ---
        num_reuses = len(plan.reusable_from_memory)
        delivery_items: list[str] = []
        if telegram_ok:
            delivery_items.append("Telegram")
        if email_ok:
            delivery_items.append("Email")
        delivery_status = ", ".join(delivery_items) if delivery_items else "None"

        summary_table = Table(title="\U0001f916 Agent Summary", title_style="bold", border_style="bright_blue", show_lines=False, padding=(0, 2))
        summary_table.add_column("Agent", style="bold")
        summary_table.add_column("Result")
        summary_table.add_row("[blue]\U0001f50e Signal Agent[/blue]", f"1 company targeted")
        summary_table.add_row("[yellow]\U0001f9e0 Analyst Agent[/yellow]", f"{first} analyzed")
        summary_table.add_row("[green]\u2699\ufe0f  Execution Agent[/green]", f"{len(plan.apis)} APIs, {len(plan.gtm_steps)} GTM steps")
        summary_table.add_row("[magenta]\U0001f4be Memory Agent[/magenta]", f"{num_reuses} patterns reused")
        summary_table.add_row("[cyan]\U0001f4e4 Delivery Agent[/cyan]", f"{delivery_status} sent")

        console.print()
        console.print(summary_table)
        console.print()
    else:
        run(first, target_arg)
