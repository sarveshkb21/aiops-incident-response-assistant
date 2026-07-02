# Demo Video Script (~3 minutes)

Record the Streamlit app (local or the live deploy) with screen capture +
voiceover. Times are targets, not rules — under 4 minutes total is a good
ceiling. Suggested tool: OBS Studio (free), or Windows Game Bar (Win+Alt+R).

---

## Scene 1 — The hook (0:00–0:25)
**Show:** A terminal or slide with a fake `SEV-1` alert, e.g.
`ALERT: pod payments-api OOMKilled — restart loop (prod)`.

**Say:**
> "It's 3 a.m. and production is down. The fix is documented — somewhere in a
> wiki the on-call engineer can't search fast enough. I built an agent team
> that turns our runbooks into instant, step-by-step incident guidance."

## Scene 2 — What it is (0:25–0:50)
**Show:** The architecture diagram from the README (or the writeup).

**Say:**
> "This is a multi-agent system: a Router agent classifies each incident into
> a domain — Kubernetes, database, infrastructure, network, security, or
> CI/CD — and hands it to a specialist agent that retrieves only from that
> domain's runbooks in ChromaDB. One Gemini call to route, one to answer. If the
> specialist finds nothing, a General agent automatically searches everything,
> so a misroute never hides the right runbook."

## Scene 3 — Live demo, routed query (0:50–1:50)
**Show:** The Streamlit app. Type (or click the sample):
`How do I resolve OOMKilled pods in Kubernetes?`

**Point at, while it answers:**
- the spinner: "Router classifying the incident…"
- the badge: `🧭 Router → ☸️ Kubernetes Agent`
- the numbered remediation steps
- the *Sources* line citing the runbook file

**Say:**
> "Watch the routing trace — the Router picked the Kubernetes specialist, and
> the answer is grounded in our own runbook, cited at the bottom. Numbered
> steps, escalation guidance, no hallucinated wiki pages."

**Then run a second domain**, e.g.
`Database connection pool exhausted - what to do?` — show the badge flip to
`🗄️ Database Agent`.

## Scene 4 — Honest answers off the runbook path (1:50–2:20)
**Show:** Ask something off-domain, e.g.
`Our office printer says PC LOAD LETTER, what now?`

**Point at:** the badge showing `🧭 Router → 🧭 General Agent`, and the answer
opening with *"I don't have a specific runbook for this, but here is general
guidance:"*.

**Say:**
> "Queries that fit no specialist route to the General agent, which searches
> all runbooks. And when nothing matches, the assistant says so — it opens
> with 'I don't have a specific runbook for this' and gives best-practice
> guidance instead of inventing a source. There's also a safety net: if a
> specialist ever comes back empty-handed, the app automatically retries
> with the General agent."

## Scene 5 — How it was built + wrap (2:20–3:00)
**Show:** The GitHub repo (README + CLAUDE.md visible in the file list).

**Say:**
> "The whole system was vibe-coded with Claude Code — LangChain, ChromaDB,
> Gemini, and Streamlit. A CLAUDE.md file acts as the coding agent's project
> memory, so every session knows the architecture and the hard-won rules.
> Adding a new domain is just a new runbook folder and a re-ingest.
> The code, a live demo, and this video are linked in the writeup — thanks
> for watching."

---

## Recording checklist
- [ ] Run `streamlit run app.py` fresh (chains rebuild, no stale cache)
- [ ] Test all three demo queries beforehand (free-tier 429s are real —
      don't burn quota right before recording)
- [ ] Hide bookmarks bar / close other tabs
- [ ] Upload to YouTube as **Public or Unlisted** (not Private)
- [ ] Paste the link into KAGGLE_WRITEUP.md before submitting
