# Kayfa AI Sales Agent Project Documentation

> Last updated: June 2026 — This documentation covers the current state of the code after the latest modifications to `app.py` and `core/agent.py` (LLM Router + lower-pressure sales strategy + price files injection), and `pages/monitor.py` (Cost Monitor + Behaviour Trace with `turn_id` system).

---

## 1) Project Overview

An intelligent sales agent for the "Kayfa" educational platform, interacting with visitors in Arabic and English, recommending courses/tracks/diplomas from a real knowledge base (JSON + Markdown), and registering serious clients as CRM tickets in MongoDB — with a full monitoring layer for the cost of each model call and step-by-step tracking of the agent's behavior.

### Main Components

| File | Role |
|---|---|
| `app.py` | Main page: login/new account, chat interface, agent invocation, LLM Router, usage logging |
| `core/agent.py` | Agent definition (pydantic-ai), search tools and CRM ticket creation, phone number verification |
| `core/rag.py` | Semantic search (RAG) via ChromaDB + Gemini Embeddings |
| `core/loader.py` | Loading and classifying knowledge base files (JSON/Markdown) |
| `database/mongodb.py` | All MongoDB interactions: users, tickets, messages, usage logs |
| `pages/crm.py` | Sales team dashboard for reviewing tickets |
| `pages/monitor.py` | Admin dashboard: Cost Monitor + Behaviour Trace |
| `utils/styles.py` | Shared CSS, sidebar, logo |

---

## 2) How the System Works — A Single Message Journey

When the user sends a message, the following sequence occurs (illustrated by the two diagrams in the previous response):

1. **Chat Interface (`app.py`)** receives the text and displays it immediately in the user's bubble.
2. **Small-Talk Check** (`_small_talk`): Simple regular expressions (regex) detect short greetings/thanks and reply to them immediately **without any API call** — direct cost savings on the most frequently repeated message type.
3. **LLM Router** (simple keyword-based rule): If the message contains words related to courses/prices/booking, `gemini-2.5-flash` is selected. Otherwise, `groq:openai/gpt-oss-120b` is used (cheaper/faster for general questions).
4. **`agent.run_sync()`**: pydantic-ai executes the call with the chosen model, passing the full conversation history (`message_history`) and an internal usage limit (`UsageLimits`) that prevents any message from consuming more than a specific number of LLM requests.
5. **`search_kayfa` Tool**: Searches the structured courses database (JSON) by matching single words, **and** in the RAG (ChromaDB) for policies, prices, and text content, in just one call. If the question contains the word price/free, the full contents of the price files are injected as additional "ground truth".
6. **The embedding call** (inside `rag.search`) is logged in `deps.embedding_calls` to calculate its cost later.
7. **Final Model Decision**: Responds with direct text, or calls `create_sales_ticket` if enough contact data is collected. This tool verifies that the phone number matches the mentioned country (`model_validator`), and programmatically injects the full conversation text (without any token cost) before saving it in MongoDB.
8. **`app.py` logs a `usage_log`** containing the model, tokens, and calculated cost, then displays the response to the user and saves it in `messages`.

---

## 3) Problems We Encountered and How They Were Solved

This section documents every actual problem we faced in chronological order, its true root cause (confirmed by actual inspection, not guessing), and the final solution.

### 3.1 "model not found" Error in Embeddings

**Problem:** `GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")` was rejecting with a "model not found" error.

**Root Cause:** The extra `"models/"` prefix. The `langchain-google-genai` library performs normalization (removing this prefix) **only** when using Vertex AI (`use_vertexai=True`). We are using the Gemini Developer API (`use_vertexai=False`), so the prefix is sent as-is to the API, which rejects it because the correct name is completely without it.

**Solution:** `model="gemini-embedding-001"` without any prefix. This was confirmed by directly inspecting the library code and simulating a real call.

### 3.2 The Agent Says "No information found" to Almost Every Question

**Problem:** After solving (3.1), every answer was "I did not find specific information", even for courses clearly existing in the knowledge base.

**Root Cause (two overlapping reasons):**

1. The `vector_db` was **completely empty** — it was deleted after changing the embeddings model (due to a conflict in vector dimensions) and was not rebuilt with `build_vector_db.py` before testing. The code does not throw any error in this case; it silently returns an empty context.
2. The structured search in `kayfa_courses.json` was matching the **full string** as a single substring. A query like `"AI diplomas"` returns zero results, even though `"AI"` alone returns 14 results — because the two words together in this order do not exist literally in any record.

**Solution:**

- `build_vector_db.py` was built as an independent script, and an explicit warning was added (in the terminal and the Streamlit interface) if the database is empty.
- The structured search matching was rewritten to split the query into single words and match if any word appears, while excluding common stop words (not by word length, because acronyms like "AI" are short and critical).

### 3.3 Complete Google Rejection of the Project (403 PERMISSION_DENIED)

**Problem:** `403 PERMISSION_DENIED — denied access, contact support` at the entire project level (Google Cloud Project), even with a new, previously unused API key.

**Most Likely Cause:** Repeatedly exceeding the RPM/RPD limits **without** a proper exponential backoff automatically triggers a Trust & Safety flag at the project level (documented in the official Google AI forum for identical cases). This is fundamentally different from `429 RESOURCE_EXHAUSTED` (a normal quota exceedance resolved by waiting).

**Decision:** Instead of trying to restore access to a banned project, a temporary shift was made to Groq + local HuggingFace (see 3.4), and then later returning to Gemini after Auth stabilized, while building an **LLM Router** that integrates Groq (for general questions) and Gemini (for courses/prices) — turning the problem into an opportunity to reduce cost.

### 3.4 Attempt at Complete Independence from Google (Groq + Local HuggingFace)

As a temporary solution for (3.3), the following were tried:

- **Chat:** `groq:openai/gpt-oss-120b` instead of Gemini.
- **Embeddings:** `HuggingFaceEmbeddings` with `paraphrase-multilingual-mpnet-base-v2` locally (supports Arabic and English with academically documented quality, without any API key or rate limit).

**Subsequent Decision:** This shift was rolled back (the team found Groq to be less accurate in extracting Arabic RAG information), and returned to Gemini as a stable base model, with a later plan for an LLM Router (already implemented in the current `app.py`) that integrates both instead of making a final choice between them.

### 3.5 `pydantic_ai.exceptions.UserError` and `ValueError: Unknown provider: google` Error

**Problem:** On a different Windows machine, the agent failed to run with the exact same code that works in another environment.

**Root Cause:** The `pydantic-ai` version installed on this machine was `1.5.0` (outdated), where the short provider name `"google"` did not exist at all (the correct name in this version was `"google-gla"`). The modern short name was added in later releases.

**Solution:** `pip install --upgrade pydantic-ai` to access a version that supports `"google"` directly, without any code modifications.

### 3.6 `ModuleNotFoundError` in `opentelemetry` (Windows Installation Issues)

**Problem:** `chromadb` fails upon import due to a version conflict between different `opentelemetry-exporter-otlp-proto-*` libraries installed from previous installations.

**Solution:** Pinning specific, unified version numbers for all related `opentelemetry` libraries in `requirements.txt`, instead of leaving them without a version number (which allows pip to leave older, conflicting installations as they are).

### 3.7 The Agent Confuses a "Course" with a "Diploma"

**Problem:** The raw data (`kayfa_courses.json` / `kayfa_roadmaps.json`) did not contain an explicit field differentiating a short course from a Track from a diploma (Bootcamp). The only available difference was the item name itself (the presence of the word "Diploma").

**Solution:** `core/loader.py` adds an explicit `item_type` field (`course` / `track` / `diploma`) at load time, based on the source file and the item name. The system prompt obligates the agent to read this field before describing any item, preventing confusion between terms.

### 3.8 The Agent is Sales "Pressuring" — Demanding Contact Info Immediately

**Problem:** The agent was asking for name/phone/city from the very first reply, regardless of how ready the user actually was.

**Initial Solution (Implemented then Replaced):** A "patient selling" threshold based on `turn_id` (a dynamic `@agent.system_prompt` function: a trust-building phase for the first few turns, then a closing phase). **Current Solution in Code (More Simplified):** An explicit rule in the static system prompt — no contact data is requested unless the user explicitly says "I want to book" or something indicating a clear purchase intent, without any reliance on counting turns.

### 3.9 `AttributeError: ERROR` when Integrating Langfuse

**Problem:** Using `level=SpanLevel.ERROR` in a manual integration with Langfuse.

**Cause:** `SpanLevel` does not exist in the current `langfuse` version (confirmed by actually installing and inspecting the library) — `level` is passed as plain text (`"ERROR"`).

**Solution:** The official, documented integration of pydantic-ai + Langfuse does not require any manual level configuration at all: `Agent.instrument_all()` after `get_client()` is sufficient (tracing via native OpenTelemetry). Full activation is optional and wrapped in a `try/except` block — the absence of Langfuse keys does not break the application.

### 3.10 Exceeding the Very Low RPM Limit on the Free Tier

**Problem:** Even a single simple message was hitting the RPM limit (around 10 requests/minute on the Gemini Free Tier).

**The Multi-layered Solution:**
- Merging the two search tools (Courses + RAG) into a single tool (`search_kayfa`) to reduce the number of model inference rounds per message.
- `UsageLimits(request_limit=...)` as an explicit internal safety limit regardless of the model provider.
- Improving the retry logic: Distinguishing the real 429 error (waiting 20/40 seconds, because the quota window is a full minute) from other errors (shorter waits).
- Mandatory login across the **entire** application (not just the CRM dashboard) to prevent any random visitor from consuming the quota indefinitely.

### 3.11 Miscellaneous Execution Issues on Windows

| Error | Cause | Solution |
|---|---|---|
| `WinError 32` during `pip install` | The `streamlit` process is already running and locking the file | Stop the process first (`Stop-Process`) before installing |
| `UserError: Set GOOGLE_API_KEY` in manual CLI test | The manual command does not call `load_dotenv()` | Use `streamlit run app.py` directly, or call `load_dotenv()` explicitly in any separate test |
| Same error from `build_vector_db.py`, `seed_db.py`, `test_agent.py`, and `pages/crm.py` | These files were not explicitly calling `load_dotenv()` themselves | Add an explicit `load_dotenv()` at the beginning of each independently runnable file |
| `SSL: TLSV1_ALERT_INTERNAL_ERROR` when connecting to MongoDB Atlas | Common on Windows; usually an active VPN, local network restrictions, or unspecified `tlsCAFile` | Explicitly pass `tlsCAFile=certifi.where()` in the `MongoClient` setup |

### 3.12 Core Bug in Linking Behaviour Trace (Unreliable Timing)

**Problem:** When building the `monitor.py` page, linking each agent response to its associated `usage_logs` records initially relied on timing comparison (`timestamp`).

**Root Cause Confirmed by Actual Inspection:** `save_chat_turn` stores the time with only second precision (`strftime("%Y-%m-%d %H:%M:%S")`), whereas `usage_logs` are stored with full microsecond precision (`datetime.now()`). Under fast execution, the user and agent messages might be recorded in the **same rounded second**, making the comparison order between messages and usage logs completely unreliable — records were observed linking to the wrong response, or not linking to any response, in real tests.

**Definitive Solution:** Replacing the time comparison with an explicit, accurate `turn_id` (a sequential number calculated in `app.py`, stored on the user message, the agent message, **and every** `usage_log` record associated with this turn). The linking in `monitor.py` becomes a direct dictionary lookup (`logs_by_turn_id.get(turn_id)`) without any guessing or time tolerance window — 100% deterministic regardless of execution speed.

---

## 4) Known Technical Risks (Intentionally Left Unresolved, As They Are Outside the Scope of Current Requests)

These are points observed during the review and were not modified because they were not part of the request, but they are worth following up on:

- **Using `result.usage()` as a method and `request_tokens`/`response_tokens` instead of `input_tokens`/`output_tokens`** in the current `app.py`: It works now due to an explicit backward compatibility in `pydantic-ai`, accompanied by a `DeprecationWarning`, and backward support may be removed in a future release.
- **The current `usage_logs` record a single aggregated log for each user message** (via the total `result.usage()`), unlike the more precise design used in earlier development (a separate log for each actual `ModelResponse` via `result.new_messages()`). This means the Behaviour Trace page will show one combined invocation instead of the details of each individual inference step, even if the response included a tool + a final phrasing.
- **Groq pricing in the current code is approximate** (`$0.15`/`$0.60` per million tokens) — it needs confirmation from the current official Groq documentation before relying on it for accurate financial reports.

---

## 5) Static Security Decisions (Auth)

- Passwords are **always** encrypted with **bcrypt** — no plaintext is saved.
- The role for a new registration is **always** `"user"` — there is no input in the interface to select `"admin"`. Upgrading is done only by matching `APP_ADMIN_EMAIL` in environment variables upon login, or manually straight from the database.
- A **unified** error message for both "Email not found" and "Incorrect password" — prevents an enumeration attack to discover registered emails.
- A **unique** index on the `email` field in MongoDB itself (not just a Python check) — prevents two simultaneous registrations with the same email (race condition).
- `@agent.tool(retries=0)` on `create_sales_ticket`: If the phone-to-country match verification fails, pydantic-ai is not allowed to make an automatic correction attempt that costs an additional LLM call — the failure is immediate, and a friendly Arabic message is displayed directly to the user.

---

## 6) Transparency Note Regarding This Documentation

While preparing this file, it became apparent that some parts (especially the `turn_id` system in `database/mongodb.py`, `app.py`, and `pages/monitor.py`) had already been implemented in a previous stage of work on the project, without it being clearly recorded in the context of this session at the time it occurred. Everything described above was verified by an actual inspection of the current code (uploaded in `app.py`, `core/agent.py`, `monitor.py`), not from memory, to ensure that this documentation reflects the true state of the project.
