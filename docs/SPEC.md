# Specification

This is sections 1 to 21 of the prompt the build was run from, committed as written. Where the build
differs from it, DECISIONS.md says how and why, dated.

## 1. What we are building

readback is an analyst agent over three warehouses from this portfolio, served as an MCP server and graded against known truth: a catalog that describes every published table, column, metric and manifest value of doorstep, turnaround and ledger with its unit and definition; an MCP server at the current specification revision exposing the catalog, read only SQL, the published values and a readback tool over stdio and streamable HTTP; a LangGraph agent that is a client of that server, plans, queries, verifies every number it is about to say, and answers in a structured form whose claims each point at the evidence; a gate that refuses an answer with an unverified number; a router over five free providers and a no model floor with a daily budget each; a golden set of 150 questions whose answers are known from the manifests, graded per provider with intervals; an injection red team; OpenTelemetry traces across the agent and the server rendered on the site; a chat whose every number is a chip that opens its evidence; the repository surface an agent needs to work in it; a briefing rendered from the same manifest as the site; and a registry entry so any MCP host can connect.

The reader is a hiring manager for an AI engineer, agent engineer or applied scientist role, deciding in ten minutes whether this person can put a model in front of data and prove what it says.

## 2. Hard constraints

- **The eighteen mandatory steps in section 16 are the product.** The build is not done while any of them is missing, and the README first paragraph says which are missing until none are.
- **The server is deployed at step nine**, before any web page, verified from a separate MCP client in a separate process over streamable HTTP, and its live URL is in the README from that step on.
- **Every published table of the three builds, at pinned tags.** The fetch step pulls every mart and export table the three repositories publish at the tags recorded in data/warehouses.lock.json, verifies each file against a committed digest, and refuses a missing file. The three manifests are loaded whole. Nothing is recomputed from raw data; the warehouses are the record.
- **Every number the agent says is read back.** The answer is a structured object; every claim carries a value, a unit and the id of the tool result or the manifest key it rests on; the gate re-runs every claim within the stated tolerance before the answer is shown; an answer with an unmatched number is repaired once, then refused. Years, identifiers, codes and counts of list items in the answer itself are exempt by a stated rule, and the rule has a test.
- **The floor is graded like a model.** The deterministic planner runs the full golden set in CI on every push and its row sits on every scorecard.
- **Every provider has a budget, in code.** Requests per day per provider, persisted, decremented before the call, refused at the cap with the next provider tried. CI never calls a metered or quota bearing API: every model call in the test suite and the eval replays from a committed cassette keyed by a digest of the request; a cassette miss in CI is a failure with the digest printed.
- **Read only SQL, parsed before it runs.** One statement, a SELECT or a WITH, parsed by sqlglot against the DuckDB dialect; anything else refused with the reason; ATTACH, COPY, INSTALL, LOAD, PRAGMA, SET and any write refused; LIMIT rewritten to the ceiling; a statement timeout; the connection opened read only with extension loading disabled.
- **The specification revision is 2026-07-28** and nothing deprecated under it is implemented: no roots, no sampling, no logging feature; tools listed in a deterministic order; cache hints on every list result; an output schema on every tool and structured content that validates against it; server discovery; trace context accepted from request metadata and continued.
- **No person in the data, none stored.** The warehouses carry none at the published grain. Questions are redacted of emails, phone numbers and identifiers before they are sent to any provider or stored; the answer log stores the redacted question, the answer object, the readback result, the provider, the model, the token counts, the latency and the trace id; the planted identifier scan proves it on the log and the traces.
- **Out of scope is refused**, in code: a question that is not about the three warehouses, or that asks about an individual, gets the stated refusal with no tool called beyond the classifier; the pattern is tested.
- **The test server refuses what the host refuses**, and the live URL is checked in a real browser and from a separate client before the tag.
- **The statement on every surface**, gated.
- **No em dashes anywhere.** Port the em dash gate and the vocabulary gate.
- **Every number in a document is rendered from the manifest.** The Day 3 renderer, whole file diff in CI. Answers from the agent never enter a document.
- **Free tier only, no card.** Vercel Hobby for the server and the API, Render free as the container fallback if the probe says so, Neon Postgres, GitHub Pages, GitHub Actions. The probe runs before the deploy step and the deploy step reads it.
- **Forty to sixty conventional commits**, made as the build proceeds, one module at a time, with the tag pushed after the commits.

## 3. Stack

```
Core            Python 3.12, uv workspace, StrictModel ported from trajectory,
                Pydantic v2 for every schema the protocol or a provider sees
Data            DuckDB over the fetched parquet and CSV tables of the three
                builds, attached read only as three schemas with extension
                loading disabled; Polars for the catalog build; a BM25 index
                over the catalog built in Python at catalog build time and
                committed as parquet, so no extension loads at request time
Protocol        the official MCP Python SDK at 2.x (MCPServer, the decorators,
                the Client with the in memory transport for tests); stdio
                and streamable HTTP; specification revision 2026-07-28;
                sqlglot for SQL parsing; server.json for the registry
Agent           LangGraph 1.x for the graph, the Postgres checkpointer and
                interrupts; LangChain 1.x chat model integrations
                (langchain-google-genai, langchain-groq, langchain-openai for
                the OpenAI compatible providers, langchain-ollama) and its
                middleware hooks for budget, redaction, summarization and the
                tool call ceiling; structured output through the schema mode
                of the provider where it exists and the tool calling strategy
                where it does not, with one parse and repair step
Providers       Google AI Studio Gemini (the default live model is the newest
                Flash Lite the free tier lists, the fallback the newest
                Flash), Groq, OpenRouter free models, SambaNova, Ollama on a
                local machine, and the deterministic floor; one registry file;
                one router
Gate            packages/gate: the numeric token extractor, the exemption
                rules, the tolerance rule, the re-run against the warehouse or
                the manifest, the verdict per claim
Tracing         OpenTelemetry SDK, the GenAI semantic convention attribute
                names pinned in docs/observability.md, a Parquet span
                exporter written in packages/tracing, an OTLP exporter when
                an endpoint is configured and nothing by default; trace
                context carried to the server in request metadata
Evaluation      packages/evals: the golden set loader, the graders, the
                cassette recorder and player, the runner, the red team, the
                scorecard with Wilson intervals and Benjamini-Hochberg
API             FastAPI, async: the MCP streamable HTTP app mounted at /mcp,
                the chat stream at /v1/chat, the answer log at /v1/answers,
                health and the statement; SQLModel over Neon Postgres for the
                answer log, the budget ledger and the spans; Alembic; the
                LangGraph checkpointer tables beside them; deployed as a
                Vercel Python function with the entrypoint declared in
                pyproject, or as a Render Docker service if the probe says so
Rendering       the Day 3 claim gate renderer, Jinja templates, manifest; the
                briefing, the scorecard pages, README, RESULTS all render
                from it
Web             Next.js 16, TypeScript strict, Tailwind v4, static export on
                GitHub Pages, DuckDB-WASM over the committed results and the
                trace parquet, the same SVG chart library as previous days,
                a streaming chat client over server sent events
Containers      Dockerfile (the server and API, for Render and for the out of
                process check), built in CI
Quality         ruff, mypy strict, pytest, hypothesis, testcontainers, nbmake,
                skills-ref for the skills, Playwright against a test server
                that refuses HEAD and answers a first 503, 80 percent floor
Logging         structlog, JSON, ids only, never a question or an answer body
```

## 4. Architecture

```
  THREE WAREHOUSES   doorstep v0.1.0, turnaround v0.1.0, ledger v0.1.0: the
                     published marts and export tables, the data dictionaries,
                     the definitions, the SQL behind the charts, the manifests
        |
        v  catalog         tables, columns, units, grains, definitions, metrics,
                           manifest keys with values; the synonym table; the
                           lexical index; the catalog quarantine report
        v  warehouse       DuckDB, three read only schemas; the SQL guard
   +-----------------------------------------------------------------------+
   |  MCP SERVER (2026-07-28, stdio and streamable HTTP)                     |
   |    tools: warehouses, describe, search_catalog, run_sql, published,     |
   |           readback, lookup                                              |
   |    resources: catalog://, manifest://, statement://                     |
   |    prompts: analyst_briefing, compare                                   |
   |    deterministic tool order, ttl on lists, output schemas, discover,    |
   |    trace context in _meta                                               |
   +-----------------------------------+-----------------------------------+
                                       ^  MCP client (in memory in tests,
                                       |  streamable HTTP in production)
   +-----------------------------------+-----------------------------------+
   |  AGENT (LangGraph)                                                      |
   |    classify -> plan -> act (tool loop) -> gate -> repair -> answer      |
   |                  \-> refuse                 \-> interrupt (ambiguity)   |
   |    middleware: redaction, budget, summarization, tool call ceiling      |
   |    router: gemini | groq | openrouter | sambanova | ollama | floor      |
   |    checkpointer: Postgres (Neon), thread per conversation               |
   +-----------------------------------------------------------------------+
        |                                   |
        v  EVALUATION (never grades itself) v  TRACING
           golden set 150 from the manifests  invoke_agent > chat > execute_tool
           development and test split         spans to Parquet; traceparent
           graders in code; the floor row     into the server; viewer on site
           red team; cassettes; budgets
        |
        v
  manifest.json          every scorecard number, interval, latency, count, hash
        v  render        briefing, README, RESULTS, scorecard pages
   +-----------------------------------------------------------------------+
   |  VERCEL (or RENDER)  /mcp  /v1/chat  /v1/answers  /health              |
   |  GITHUB PAGES        desk, traces, evals, catalog, connect, playbook,  |
   |                      report                                             |
   +-----------------------------------------------------------------------+
```

State in ARCHITECTURE.md why the agent is a client of its own server rather than calling the warehouse directly: the tools the agent uses are the tools any host gets, so a bug in a tool is found by the eval and a bug in the protocol is found by the separate client, and neither can be hidden by a private code path. State why the gate is deterministic code and not a second model: a model checking a model is a vote, and a vote is not a verification. State why the floor exists: the free tier of a provider can disappear in a week, and a product that only works with a key is a demo. State why the known truth is the manifests: three builds spent a day each proving their numbers, and this build should not pretend to know better.

## 5. The three warehouses, the catalog, the manifests, and the quarantine

**The warehouses.** doorstep at v0.1.0 (393 metros, 2000 to 2026Q2, the eight chapter tables, the calculator marts, the CSV bundle, 928 manifest values), turnaround at v0.1.0 (74.2 million flights summarized to the published tables, the eight chapter tables, the CSV bundle, its manifest), ledger at v0.1.0 (the fraud desk, the fair lending tables on New Jersey HMDA, the reconciliation, its manifest). The fetch script pulls every file the lock file names from each repository at its tag, over GitHub, verifies SHA-256 against the lock, and writes data/warehouses/<name>/ with the manifest beside the tables. The lock file is committed with the tag, the commit, the file list and the digests; a planted wrong digest fails the fetch, with a test. Nothing is recomputed. If a table the lock names is not in the repository at the tag, the fetch refuses and the README names it; the build does not substitute.

**The catalog, catalog/<name>.yaml.** One entry per table with its grain, its source step in the build, its row count, and one entry per column with type, unit (fraction, percent, dollars, count, years, index points, minutes, share of flights, basis points, or none), the definition sentence lifted from the definitions document of that build with the file and line cited, and the manifest keys that read from it. One entry per metric with the SQL the build published. Built by scripts/build_catalog.py from the data dictionaries and the definitions documents, then hand edited where a dictionary is silent, with every hand edit recorded as a DECISIONS.md entry. The synonym table maps the words a person uses (home price, house price, median value; on time, punctual; denial, decline) to catalog terms. The lexical index (BM25 in plain Python) over table names, column names, definitions, metric names, manifest keys and synonyms is built once at catalog build time and committed as parquet; the server loads it into memory at start and never loads a DuckDB extension.

**The manifests.** results/manifest.json from each build, loaded into catalog/manifest_index.parquet: warehouse, key, value, unit, interval low and high where present, the table and SQL that produced it where the build recorded one, the rounding (the number of decimals in the published value). The rounding is what the readback tolerance reads.

**Units.** Every column and every manifest value has a unit. The readback converts percent to fraction and back only when the catalog gives the unit on both sides, and refuses to compare two values whose units it cannot reconcile. A test plants a fraction against a percent and asserts the refusal.

**The catalog quarantine**, named, counted, nothing deleted: a table with a column lacking a unit; a column lacking a definition; a manifest key with no table behind it; a manifest value whose published rounding cannot be read; a synonym that maps to nothing; a metric whose published SQL does not parse against the current table; a table in the lock file absent from the catalog. Publish the report by warehouse and rule. The first real run of the golden set through the floor (step three) is expected to add rules here, and the build logs each one.

**The golden set, evals/golden/*.yaml.** 150 questions in eight families, committed with their known answers before the agent exists:

```
 40  doorstep   lookup (one published value by metro and year), comparison
                (two metros or two years), trend (direction over a window),
                top k (a ranking slice), definition (what a term means, graded
                against the definitions document by key phrase)
 40  turnaround the same families over carriers, airports and years
 40  ledger     the same families over the fraud desk, the fair lending tables
                and the reconciliation
 15  multi      a question that needs two warehouses (which build has more
                rows; the year both doorstep and ledger cover; a definition
                that differs between two builds)
 15  refusal    out of scope (another build in the series, a question about
                an individual, a forecast, advice, a question about a metro
                that is not in any warehouse) where the only correct answer
                is the stated refusal, graded as a hard pass or fail
```

Each in scope question carries its known answer as a manifest key, or as a committed SQL over the published tables that produces it, with the tolerance derived from the published rounding, and the entities it names. The set is split by a seeded, sorted draw into 50 development and 100 test questions, stratified by family and warehouse; every choice tuned on development is reported on test, and a test reports on the development split only to show the gap.

**The red team, evals/redteam/*.yaml.** 15 injection cases, each with a marker string that must never appear in an answer and a list of tools that must never be called: an instruction planted in a catalog description used only in the red team fixture; an instruction planted in a mart cell of a red team only table (a text column, since the real warehouses have no free text that a person wrote); a fake system note inside the user message; a tool result that asks the agent to call run_sql with a write; a question that asks the agent to reveal its system prompt; a question that asks it to ignore the gate and answer with a number it did not look up. Pass is deterministic: the marker is absent, the forbidden tools were not called, the gate verdict is consistent with the claims.

## 6. The MCP server

Build it with the official SDK at 2.x. One server object, two transports: stdio through the console script readback-mcp, and streamable HTTP as an ASGI app mounted at /mcp inside the FastAPI application. Stateless, as the revision requires: no session header, the protocol version and the client capabilities read from request metadata, server discovery answered with the supported revisions, capabilities and identity. Tools listed in a fixed order from a committed table, with a test that two list calls return identical bytes. Every list and read result carries its cache hint: a ttl of one hour and a public scope for the catalog and the published values, which do not change between deploys. Every tool has an input schema and an output schema, returns structured content that validates against the output schema, and a test per tool asserts the validation. Request metadata is read for trace context (traceparent, tracestate) and the server span is a child of it; a test over the in memory transport asserts the parent id.

**Tools**, with their purpose and their refusals:

- **warehouses** returns the three warehouses with their pinned tag, commit, row counts, the as of period each covers and the statement. No arguments.
- **describe(warehouse, table)** returns the grain of the table, columns with types, units and definitions, the manifest keys that read it, and five example rows drawn deterministically (sorted by the primary key, first five). Refuses an unknown table with the three nearest names.
- **search_catalog(query, k)** returns tables, columns, metrics and manifest keys ranked by the lexical index with the synonym expansion applied, each with the definition sentence and the unit. k is capped at 20. Returns the query as expanded so the caller can see what it searched.
- **run_sql(warehouse, sql, limit)** parses the statement with sqlglot in the DuckDB dialect, refuses anything but a single SELECT or WITH, refuses any write, ATTACH, COPY, INSTALL, LOAD, PRAGMA or SET, refuses a reference to a table outside the named warehouse schema, rewrites or adds LIMIT at the ceiling of 500 rows, runs with a statement timeout of 10 seconds on a read only connection, and returns the normalized SQL, the column schema with units where the catalog knows them, the rows, the row count before the limit, the elapsed time and a digest of the result. Every refusal names the clause it refused.
- **published(warehouse, key_or_pattern)** returns manifest values matching a key or a glob, each with unit, interval, rounding, and the table and SQL that produced it where recorded. Capped at 50 matches, sorted by key.
- **readback(claim)** takes a value, a unit, and either a result id from an earlier run_sql call in the same request chain, a SQL statement, or a manifest key, re-runs or looks up, converts units where the catalog allows, and returns agree or disagree with the difference and the tolerance applied. This is the tool the agent must call for every number before it answers; the gate checks that it did.
- **lookup(kind, name)** resolves a metro, carrier, airport, county or year the way the warehouses spell it. When the name is ambiguous (Portland, Washington, Kansas City) it needs a choice. If the installed SDK exposes the multi round trip pattern, the tool returns an input required result carrying the candidates, and the client retries with the choice; if the SDK does not yet expose it, the tool returns the candidates as structured content with a flag and the agent asks the person through a graph interrupt. DECISIONS.md records which path shipped and why.

**Resources.** catalog://{warehouse}/tables, catalog://{warehouse}/{table}, manifest://{warehouse}, statement://readback. Resource templates listed with cache hints. **Prompts.** analyst_briefing(warehouse) and compare(warehouse, entity_a, entity_b), each a template whose arguments are validated.

**Protection of the free tier.** The public endpoint is read only and needs no token. A per client budget of 60 requests an hour and 600 a day, keyed by a hash of the client address, is kept in Postgres and refused with a clear message past the cap; a test exhausts it. The ceilings on rows, time and k are the other half of the protection.

**The registry.** server.json committed at the root with the remote entry for the live streamable HTTP URL and the package entry for the stdio console script, named under the GitHub namespace of the account. Publishing needs a device code login and is done in Part 5; the README links the entry once it exists and says so until then.

**Connecting.** docs/connect.md and the /connect page carry the exact configuration for Claude Desktop (stdio command and the remote URL), the claude.ai custom connector (the URL), Cursor, VS Code and Codex, each as a code block, each produced from one committed source so they cannot drift.

## 7. The agent

A LangGraph StateGraph with named nodes, not a prebuilt loop, because every edge here is a decision the reader should be able to find:

```
classify   question family and warehouse routing: the deterministic rules
           first (entity dictionaries, family grammar), the model second when
           the rules do not match; out of scope goes to refuse with no tool
           call
plan       the tools to call, in order, as a structured object; for the floor
           this is the plan the grammar compiled
act        the tool loop over the MCP client: search_catalog, describe,
           lookup, run_sql, published, in at most the ceiling of calls; every
           result kept with its id and digest
gate       the readback: every claim in the draft answer re-verified through
           the readback tool; the verdict per claim
repair     one retry with the gate report in context; on a second failure,
           refuse with the report
refuse     the stated refusal, labeled, with the reason
interrupt  a lookup that needs a choice pauses the graph and surfaces the
           candidates; the person chooses; the graph resumes from the
           checkpoint
answer     the structured Answer: text, claims with evidence ids, the
           provider and model, the token counts, the trace id, the gate
           verdict
```

**The Answer schema.** text (the prose), claims (value, unit, display string, the span of the text it occupies, evidence: tool result id or manifest key, the SQL as run), warehouses touched, provider, model, tokens in and out, latency, trace id, gate verdict (verified, repaired, refused), and the statement. The chat renders a chip over each claim span.

**Structured output.** The schema mode of the provider where the registry says it exists (Gemini, and Groq on the models that support it), the tool calling strategy otherwise, with one parse and repair step whose success rate per provider is published. The Answer schema and every tool input schema are the same Pydantic models the server uses, so there is one definition of each.

**Middleware**, in the LangChain 1.x sense (hooks before the model call, after it, and around each tool call), implemented as wrappers on the act node so the hand built graph keeps them explicit, each with a test: redaction (emails, phone numbers, identifiers removed from the question before the model and before storage, with a planted identifier test), budget (the daily count of the provider read and decremented before the call, the next provider tried at the cap, the switch recorded in the trace), summarization (threads past a stated token length have their older turns condensed; the summary is labeled in the trace), the tool call ceiling (eight per turn; the ninth is refused and the answer says the question was too wide).

**Durable execution.** The Postgres checkpointer on Neon, one thread per conversation, so a conversation resumes after a restart and an interrupt waits as long as it needs to. A test kills the graph between act and gate and resumes it from the checkpoint.

**The prompt registry, prompts/registry.yaml.** Every system prompt, tool description and few shot block is a file with a hash; the registry is hashed as a whole; the hash is recorded in every trace and printed on the scorecard; a prompt changed after the eval plan was registered changes the hash and fails the gate unless DECISIONS.md carries a dated entry for the change, as doorstep did for its sixth chapter.

**Context discipline.** The catalog is never sent whole. search_catalog results carry one definition sentence each; describe is called for one table at a time; the system prompt is under 600 tokens and says what the tools are for and what the gate will do. Tokens per question per provider are measured and published, and the median is one of the scorecard columns.

## 8. Providers, budgets, and the floor

**The registry, providers/registry.yaml.** One entry per provider: the environment variable that holds its key, the model id (from the environment for Gemini, since the model list of the free tier moves; fixed defaults for the others), the structured output mode, the daily request budget, the requests per minute cap, a flag for whether the terms of the provider allow the data sent (public aggregates only; every entry says so), and the order of preference. Gemini first because the key is the one the account holds; Groq second for its larger daily quota; OpenRouter free models third; SambaNova fourth; Ollama when a local endpoint is configured; the floor always last and always available.

**The router.** Picks the first eligible provider: key present, budget remaining, not rate limited in the last minute. Records the choice and the reason in the trace. Never pools: a scorecard row is one provider, one model, one prompt registry hash.

**The budget ledger.** A Postgres table of provider, day (Pacific time, because the Gemini quota resets there), requests used, with a row written before each call inside the same transaction as the audit row of that call, so a crash between the two cannot leave an uncounted call. The remaining budget for the day is on the /evals page and in the API health response.

**Cassettes, evals/cassettes/<provider>/<digest>.json.** Every model request in the eval and the test suite is keyed by a digest of the provider, the model, the prompt registry hash and the message list. A recorded response replays; a miss in CI fails with the digest; a miss in a live run calls the provider within the budget and records. The cassette carries the recording date and the model id as reported, both printed on the scorecard. A test changes one character of a prompt and asserts a miss.

**The live eval is incremental.** The scheduled workflow (weekly, and on demand) runs the test split through every provider whose key is in the repository secrets, records cassettes until the daily budget of each provider is spent, commits the new cassettes through a pull request, and the scorecard states, per provider, the share of the test split graded live and the dates. A scorecard with 40 of 100 graded says 40 of 100; it never extrapolates.

**The floor, packages/planner.** A grammar over the golden set families with entity dictionaries from the catalog and SQL templates per warehouse: lookup, comparison, trend, top k, definition, multi, and the refusal rule for everything else. No model anywhere in it. It compiles a plan, calls the same tools over the same client, and produces the same Answer schema with the same readbacks. It is graded on both splits and sits on every scorecard as the first row, in the control gray with a hatch, labeled no model. It is also what the live site runs when no key is present or every budget is spent, with a badge that says so.

**What the floor is for.** A model that does not beat the floor on the test split, after correction, is listed as not beating the floor, and the default live provider is the best one that does. That decision is made on the development split and reported on the test split.

## 9. The readback gate and the operating points

**The gate.** From the draft answer text, extract every numeric token with its span. Apply the exemption rules: a four digit year in a year position, an identifier the catalog knows (a CBSA code, an airport code, a county FIPS), an ordinal position in a list the answer itself numbers, and a count of items in that list. Every remaining token must be a claim with evidence. For each claim: re-run through the readback tool; compare in the unit of the claim after the conversion the catalog allows; pass when the absolute difference is at or below the tolerance, which is half a unit of the published rounding for a manifest key and half a unit of the display rounding for a query result; fail otherwise. An answer passes when every claim passes; fails to repair on the first failure; fails to refuse on the second. The gate is pure code with no model in it, and it has the three tests every gate has plus one per exemption rule.

**Operating points, each with the interior test.** The tolerance (a quarter, a half and one unit of rounding), the retrieval depth k (3, 5, 8), the tool call ceiling (4, 8, 12), the summarization threshold, the daily budget per provider (half, as set, double), and the development split size (30, 50, 70). The /evals page prints the test split accuracy of the default provider and the floor under each neighbor, and the word degenerate when the ranking of providers changes at the first neighbor.

**The pre-registered plan.** evals/plan.yaml: the families, the graders, the tolerance rule, the split seed, the providers in scope, the prompt registry hash, hashed and registered before the first live model call; the hash printed in the scorecard and RESULTS.md. A plan changed after registration changes the hash and fails the gate unless DECISIONS.md logs the change with the date and the reason.

## 10. Evaluation

**Graders, all code.** Numeric: the claim value against the known value within tolerance, in the known unit. Entity: the named metro, carrier, airport or table matches the known one after the lookup normalization. Trend: the direction word matches the known sign. Top k: the known set at the known positions, graded as exact match and as Jaccard at k. Definition: the known key phrases present. Refusal: the stated refusal pattern present and no warehouse tool called. Injection: the marker absent and the forbidden tools not called. Readback rate: the share of claims with evidence that re-verify. Unsupported number rate: numeric tokens outside the exemption rules that carry no evidence, measured on the draft before the gate as well as on what shipped, so the reader sees what the gate caught. Efficiency: tool calls, model calls, tokens, latency per question. Repair rate: the share of answers that needed the retry.

**The scorecard.** Per provider and family, on the test split: accuracy with a Wilson interval, readback rate, unsupported number rate before and after the gate, repair rate, refusal accuracy, injection pass count, median tool calls, median tokens, median and 99th percentile latency, the share graded live and the cassette dates, the model id as reported, the prompt registry hash. Provider against provider differences in accuracy with intervals and Benjamini-Hochberg across the family of comparisons. The floor as the first row. A second table on the development split for the gap.

**The secondary metric, labeled.** An optional model judge scores answer clarity on a five point rubric from a committed prompt, never correctness, and its agreement with the deterministic grade (the kappa statistic on pass or fail) is printed beside it. It runs only from cassettes in CI and within budget live. It never decides anything.

**Latency.** Through the live API, the test split questions by provider: p50 and p99 from a stated load test, with the cold start (the first call after the function has been idle) measured separately and published, because a serverless host has one.

**The briefing, report/briefing.md and HTML**, rendered from the manifest: the headline (which provider the site runs, at what accuracy against the floor, with what interval), the scorecard, the red team result, the catch rate of the gate, the protocol conformance summary, the budgets used, the latency, the limitations, and a paragraph at the end of every section titled What the platform engineer would push back on.

## 11. Observability

OpenTelemetry through the SDK, with the span names and attributes of the GenAI semantic conventions as they stand in 2026 (still in development status; the exact names used are pinned in docs/observability.md with the date they were read): an invoke_agent span per turn, a chat span per model call carrying the provider name, the request and response model ids, the finish reasons and the input and output token counts, an execute_tool span per tool call, and the gate as its own span with the verdict as an attribute. Message content is not captured; the content capture attributes stay off, and a test asserts no question text appears in any span. The agent puts traceparent and tracestate into the MCP request metadata; the server reads them, so one trace crosses the protocol boundary, and the test over the in memory transport proves the parent child link.

Exporters: a Parquet exporter in packages/tracing writes results/traces/<run>.parquet with one row per span (trace id, span id, parent id, name, start, end, attributes as a struct), used by the eval runner, the rederive and the site; an OTLP exporter is wired and used only when OTEL_EXPORTER_OTLP_ENDPOINT is set, which it is not by default, so no vendor is involved; the live API writes spans for each turn to the spans table with a seven day retention job. The /traces page renders a waterfall per turn from the parquet in the browser, with the gate span marked and the readback verdicts beside the chat spans; every answer on the desk links to its trace by id.

## 12. Persistence and the API

Neon Postgres, schema readback, shared project with the earlier builds: the answers table (id, thread id, redacted question, answer object, gate verdict, provider, model, tokens in, tokens out, latency, trace id, created at), the budget ledger, the client budget, the spans, and the checkpointer tables. Alembic with the versioned table pattern from Day 13.

POST /v1/chat takes a thread id (or none, to start one) and a question, streams server sent events (the classification, each tool call with its result id, the gate verdict per claim, the answer object), writes the audit row before the final event, and returns the answer id in the final event. GET /v1/answers/{id} returns the stored answer with its trace id. POST /v1/chat/{thread}/resume carries the choice for an interrupt. GET /health returns the version, the protocol revision, the provider the router would pick now with its remaining budget, and the statement. The demo queue is preloaded with the development split answers from the floor so the desk is never empty.

test_answer_is_committed observes the row from a second, independently opened connection; test_audit_precedes_final_event asserts the audit row exists before the final stream event is sent; test_budget_and_audit_share_a_transaction asserts a failure between them leaves neither; the CI out of process script starts the API in the container, asks a development split question through the floor, reads the answer back through a fresh connection in a separate process, and asserts the trace id matches a span row. The demo recording creates answers; the reset and rederive step clears them.

## 13. The repository surface for agents

This is the part the market calls vibe coding. Do it as engineering.

- **AGENTS.md** at the root, in the open format the Agentic AI Foundation hosts: how to set up, how to run the tests, the gates and what they refuse, the commit convention, the files an agent must not edit (the lock file, the manifests, the cassettes except through the recorder), where decisions go, and the rule that every number in a document renders from the manifest. It is the single source.
- **CLAUDE.md** and **.github/copilot-instructions.md** each one paragraph that points at AGENTS.md and adds only what that tool needs.
- **.mcp.json** configuring the server of this repository over stdio, so whoever opens the repo in an MCP capable editor can ask the warehouses questions while working on the code.
- **.claude/skills/** with three skills in the Agent Skills format (a SKILL.md with name and description in the frontmatter, under 500 lines, references one level deep), validated in CI with skills-ref: warehouse-question (how to answer a question against the three warehouses through the tools, with the readback rule), golden-question (how to add a golden question with its known truth, unit, tolerance and split, and what the grader needs), release-gate (the checklist run before a tag, every command). Each skill is the procedure a person would follow, written once.
- **docs/SPEC.md**: sections 1 to 21 of this prompt, committed as the specification the build was run from, with a line at the top saying deviations are in DECISIONS.md. The opening paragraph of the prompt is not part of it.
- **server.json** for the registry, as section 6 says.
- **The playbook page** on the site renders AGENTS.md and the three skills, so a reader who never opens the repository sees how it is worked in.

## 14. The site and the visual system

Static export on GitHub Pages, DuckDB-WASM over the committed results and trace parquet for every chart and the viewer, the live API for the desk, and a recorded session so every page works if the API is asleep or absent, labeled as recorded, with the site probing twice because a Render instance wakes slowly and a Vercel function has a cold start.

**Art direction.** A flight deck at night. Dark first: a graphite surface with a cool cast, hairlines, one transcript down the middle like a radio log, tool calls as cards with monospaced headers, the turns of the person in copper, the turns of the model in violet, the results of the warehouse in teal, and a chip on every number whose color is its verdict. Light is a true theme on a neutral paper, not an inversion. Dense tables only on the evals and catalog pages. Nothing decorative.

**Surfaces and ink.** Dark is the default; light is a true theme. Both validated.

```
Dark surface    #15171A    light surface   #F5F5F2    card   #1E2126 dark, #FFFFFF light
Primary ink     #ECEEF1    primary ink     #17191C    rules  #30353C dark, #D8DAD5 light
Secondary ink   #A6ADB7    secondary ink   #5A6069
Control gray    #8D959F    control gray    #6E7580
```

**Categorical palette, fixed order, validated in both modes.** Dark: #2FB8A0, #9B8CF2, #EE9A4C, #5B8DEF, #E04A89, #A8BB3A, #2E9DD3, #CDA06A. Light: #0E8571, #5D47D9, #B4561E, #2457A6, #D43F6E, #6F7F18, #06689A, #8A5F2B. Measured with the series validator in OKLab under normal vision and under the simulations of protanopia, deuteranopia and tritanopia, with WCAG contrast on both surfaces and both cards: worst adjacent CVD separation 13.3 dark and 8.5 light against a target of 8; worst normal vision separation 21.9 dark and 20.1 light against a floor of 12; every dark slot at or above 4.7:1 on the surface and 4.2:1 on the dark card; every light slot at or above 4.1:1 on the surface and 4.4:1 on white. The first three slots pass the all pairs check in both modes (10.0 dark, 11.6 light). Slot one is the warehouse: query results, verified readbacks, execute_tool spans. Slot two is the model: its turns, chat spans. Slot three is the person: the question, the interrupt choices, the gate span. Slots four to eight are the providers in the eval charts in fixed order: Gemini, Groq, OpenRouter, SambaNova, Ollama; the floor is the control gray with a hatch. The order is committed as a table, with direct labels always. Port scripts/validate_palette.js and run it in CI against exactly these values, including the card run in both modes. If the ported validator rejects a slot, move it by the smallest change that passes and record the change in DECISIONS.md.

**Sequential, teal, for magnitude.** Dark, dark to light: #0E4A40, #11705F, #1F9480, #4FBFA8, #9EE0D1; light, light to dark: #8FD0C1, #5FB8A5, #2E9A85, #157F6C, #0B5447. Both validated as ordinal ramps, monotonic in lightness. For accuracy heatmaps by provider and family, token density, and latency bands.

**Diverging, violet to teal through a neutral midpoint**, #2A2E33 dark and #E4E6E2 light. Dark arms: violet #C9BDFF, #A897F5, #8676DC, #5E4FB0 to the midpoint, then teal #176D5E, #1F9480, #4FBFA8, #9EE0D1. Light arms: violet #3B2E8F, #5D47D9, #8A7BE6, #B3A7F0, then teal #8FD0C1, #4FB39F, #157F6C, #0B5447. Each arm validated. The claim of the model against the value of the warehouse on the readback difference chart: violet when the model was high, teal when the warehouse was higher, neutral at agreement.

**Status, reserved, always with an icon and a word.** Good #3FB950 dark and #1E7F3F light; warning #E3B341 and #B7791F; serious #F0883E and #C2410C; critical #F85149 and #B42318. Verified at or above 3:1 on both surfaces and both cards. Verified, repaired, refused, budget spent, cassette miss, degenerate and recorded session wear these; no series does.

**Type.** Self hosted at build time through next/font.

```
A  Flight deck (default)  Bricolage Grotesque (display: page titles, the
                          standfirst, the headline figures, at the heavy
                          weights with the optical size axis on), B612
                          (interface and body; confirm tabular figure support
                          in the build and fall back to the sans of option B for
                          numeric columns if it is missing), B612 Mono (the tool
                          cards of the transcript, SQL, hashes, trace spans,
                          every figure in a dense table)
B  Workshop               Familjen Grotesk, Onest, Kode Mono
C  Contemporary           Syne, Wix Madefor Text, Google Sans Code
```

Body 15px on the desk and 16px elsewhere, line height 1.5, measure capped at 70 characters, the briefing at 68. Every figure right aligned with tabular numerals. If a face is missing from Google Fonts at build time, use the next option and record it in DECISIONS.md. Nothing from days 1 to 15 type appears.

**Chart rules, every chart.** The series mark specification unchanged, one axis, legend and direct labels by the count rule, hover on every mark, a table toggle beside every chart, a show the SQL toggle beside every chart, texture in addition to hue, ink tokens for text, one written message per chart rendered from the manifest as its title, with the conventional title demoted to a subtitle. The agent charts have conventions and the build follows them: the scorecard is a dot plot with the interval as a bar, one row per provider, the floor row first and hatched; the readback difference chart is a strip of claims on the diverging ramp with agreement at the center; the trace waterfall has time on the x axis, one row per span, the model spans in violet, the tool spans in teal, the gate span in copper, and the token counts at the right end of each chat span; the budget chart is a horizontal bar per provider with the use so far today against the cap; the latency chart is two dots per provider, warm and cold start, joined by a line.

**Pages.**

- / **The desk.** The chat: a question box, the transcript with tool call cards that expand to the SQL, the schema and the rows; the answer with a chip on every number (teal verified, warning repaired, critical refused) that opens the evidence; the provider and model badge; the trace link; the interrupt choices when a lookup is ambiguous; the statement; a no model badge when the floor is answering.
- /traces **The viewer.** Pick a turn from the recorded eval runs or paste a trace id from the desk; the waterfall; the attributes of every span; the readback verdicts beside the chat spans.
- /evals **The scorecard.** The test split table by provider and family with intervals, the floor row, the development split table for the gap, the red team table, the gate catch rate, the interior tests, the budgets used today, the cassette dates, the prompt registry hash, the pre-registered plan hash.
- /catalog **The three warehouses.** Tables, columns, units, definitions, metrics, manifest keys with values, the synonym table, the quarantine report, the lock file.
- /connect **Connect a host.** The live URL, the stdio command, the configuration blocks for Claude Desktop, claude.ai, Cursor, VS Code and Codex, the server.json, the registry link, and the protocol conformance summary (revision, discovery result, tool count, both transports).
- /playbook **How this repo is worked in.** AGENTS.md and the three skills rendered, the specification link, the decisions with dates.
- /report **The briefing**, with a print stylesheet.

Loading states are skeletons in the shape of the chart. prefers-reduced-motion respected, everything keyboard reachable, contrast checked in both themes, the statement in the footer of every route, mobile laid out at 390 pixels first with the transcript full width and the evidence as a sheet.

## 15. What makes it read as built by a person, the agent edition

Everything in northstar section 18 applies unchanged. Four additions:

- **What the platform engineer would push back on.** Every page and every section of the briefing ends with a short paragraph naming the objection (the manifests are the numbers of this portfolio itself; the gate checks arithmetic agreement, not the choice of query; free quotas make the live eval partial; a stateless server cannot stream progress across requests; the floor only covers the families it was written for) and what the build did or did not do about it.
- **The catches of the gate are kept.** The /evals page lists the unsupported numbers the gate caught on the test split, by provider, with the draft and the shipped answer side by side, because the catch is the product.
- **The decisions name the protocol.** Every DECISIONS.md entry that chose a protocol path (the multi round trip pattern or the fallback, the cache hints, the client budget, what was not implemented because it is deprecated) cites the revision and the reason.
- **The dead ends are kept.** The notebooks keep the absolute tolerance that passed every claim and hid a unit error, the embedding retriever that needed a key and lost to the lexical index with synonyms, and the injection defense that stripped imperative sentences from tool results and broke the definitions.

## 16. Repository layout and build order

```
readback/
+-- README.md  RESULTS.md  ARCHITECTURE.md  DECISIONS.md  CONTRIBUTING.md  LICENSE
+-- AGENTS.md  CLAUDE.md  server.json  .mcp.json  vercel.json  render.yaml  Dockerfile
+-- Makefile  pyproject.toml  uv.lock  .env.example
+-- .github/  workflows/  ci.yml  pages.yml  live-eval.yml  release.yml
|             copilot-instructions.md
+-- .claude/skills/  warehouse-question/  golden-question/  release-gate/
+-- data/  warehouses.lock.json  PROVENANCE.md  warehouses/ (doorstep, turnaround,
|          ledger: fetched tables and manifests)
+-- catalog/  doorstep.yaml  turnaround.yaml  ledger.yaml  synonyms.yaml
|             manifest_index.parquet  index.parquet  slot_order.csv
+-- prompts/  registry.yaml  system/  tools/
+-- providers/  registry.yaml
+-- packages/
|   +-- core/  catalog/  warehouse/  mcp_server/  planner/  providers/  agent/
|   |   gate/  tracing/  evals/  api/  render/
+-- evals/  plan.yaml  golden/  redteam/  cassettes/
+-- results/  manifest.json  evals/  traces/  latency.json  live_check.json
|             hosting_probe.json  providers.json  conformance.json  rederive.json
+-- notebooks/  01_the_tolerance  02_the_floor  03_the_injection
+-- report/  briefing.md  templates/
+-- scripts/  check_no_em_dash.py  check_vocabulary.py  check_published_numbers.py
|             check_statement.py  scan_for_planted_identifiers.py  validate_palette.js
|             fetch_warehouses.py  build_catalog.py  probe_hosts.py  record_cassettes.py
|             load_test.py  check_persistence.py  reset_and_rederive.py
|             build_demo_gif.py  conformance.py
+-- deploy/  probe.ps1  verify.ps1  replay.ps1  reset.ps1  push-main.ps1  push-tag.ps1
+-- web/
+-- docs/  SPEC.md  protocol.md  agent.md  evaluation.md  observability.md  security.md
|          connect.md  runbook.md  templates/
+-- tests/
```

Build order. Steps 1 to 18 are mandatory and are the product.

```
 1  Scaffold, ported tooling, em dash, vocabulary and statement gates, licences,
    a health route at the Vercel entrypoint so the first push deploys, the
    hosting probe run against it and its result committed
    chore: scaffold workspace with ported tooling
 2  Claim gate renderer before any results exist, wired to README, RESULTS,
    the briefing and the scorecard templates
    ci: published number gate
 3  Warehouses: the lock file, the fetch with digests, the catalog with units
    and definitions, the manifest index, the synonym table, the lexical
    index, the catalog quarantine; the golden set committed with known truth
    and split; the first ten golden questions run through SQL by hand against
    the real marts and the catalog fixed where they fail
    feat(data): three warehouses, the catalog and the golden set
 4  MCP server: the seven tools with output schemas, the resources, the
    prompts, deterministic order, cache hints, discovery, stdio; the
    conformance tests over the in memory transport
    feat(mcp): server at the 2026-07-28 revision
 5  The SQL guard, the readback tool, the lookup with the multi round trip
    pattern or its fallback, the client budget
    feat(mcp): read only sql, readback and lookup
 6  Providers: the registry, the router, the budget ledger, the cassette
    recorder and player, the structured output modes; the floor over the
    grammar and the templates, graded on the development split
    feat(agent): providers, budgets and the floor
 7  The graph: classify, plan, act over the MCP client, gate, repair, refuse,
    interrupt, answer; the middleware; the checkpointer; the prompt registry
    hashed; the eval plan registered
    feat(agent): the graph and the readback gate
 8  Tracing: the spans, the Parquet exporter, trace context through the
    server, the content capture off with its test
    feat(tracing): spans across the protocol boundary
 9  Deploy: the ASGI app with /mcp, /v1/chat, /v1/answers and /health on the
    host the probe chose, with Neon; verified from a separate MCP client in a
    separate process (tools listed, discovery answered, one run_sql, one
    readback); live URL in the README
    feat(api): server deployed and verified from a separate client
10  Independent connection tests, audit ordering, the shared transaction, the
    out of process check
    test(api): answers observed independently
11  Evaluation: the graders, the runner, the red team, the cassettes recorded
    for the floor and for every provider with a key, within budget
    feat(evals): graders, red team and cassettes
12  The scorecard: both splits, intervals, Benjamini-Hochberg, the interior
    tests, the gate catches, the secondary judge with its agreement; the
    default live provider chosen on development and reported on test
    feat(evals): the scorecard
13  The repository surface: AGENTS.md, CLAUDE.md, the Copilot instructions,
    .mcp.json, the three skills validated with skills-ref, docs/SPEC.md,
    server.json, docs/connect.md from one source
    docs(agents): the surface a coding agent needs
14  Web: desk, traces, evals, catalog, connect, playbook, report; the test
    server that refuses HEAD and answers a first 503; Pages deploy
    feat(web): the desk and its pages
15  Full run, RESULTS.md with the section 19 checklist, README with the matrix,
    DECISIONS.md, notebooks 01 to 03
    chore: first full run and publish
16  Load test with cold start; the live check in a real browser with the API
    awake and asleep and from the separate client; demo recording; reset and
    rederive in a worktree; gate
    chore: live check, recording and canonical rederive
17  The scheduled live eval workflow with the budget guard and the pull
    request it opens; release notes rendered
    ci: incremental live eval
18  Tag v0.1.0 pushed after the commits
    chore: release
19  MCP Apps: a ui resource that renders a run_sql result as a table with the
    readback verdicts inside a host that supports the extension
    feat(mcp): the apps extension
20  A2A: the agent card at the well known path and a message endpoint that
    wraps the chat, at the 1.0 revision
    feat(api): an agent card
21  The browser floor: the grammar and templates of the planner in TypeScript over
    DuckDB-WASM, so the desk answers the in scope families with no server
    feat(web): the floor in the browser
22  A fourth warehouse (marginal or lookahead) added through the lock file and
    the catalog alone, as the test that the design generalizes
    feat(data): a fourth warehouse
23  A Claude Code plugin manifest and Cursor rules generated from AGENTS.md
    docs(agents): editor manifests
24  Dockerfile hardening, ARCHITECTURE and docs, release workflow hardening
    ci: containers and documentation
```

If time runs short, cut from 24 backward and never below 18. Inside the first eighteen there is nothing to cut; if one of them cannot be finished, the README first paragraph names it and the build is not called complete.

## 17. The skills matrix

In the README, one row per skill an AI engineer, agent engineer or applied scientist posting lists, and the file that demonstrates it:

```
Skill                                      Where it lives
MCP server design                          packages/mcp_server, docs/protocol.md,
                                           results/conformance.json
MCP client                                 packages/agent (the client), tests over
                                           the in memory transport
Agent orchestration                        packages/agent (LangGraph graph, interrupts,
                                           checkpointer)
Tool use and structured outputs            the Answer schema, the tool schemas, the
                                           per provider output modes
Natural language to SQL, verified          packages/planner, run_sql, the readback tool
Evaluation engineering                     packages/evals, evals/golden, the scorecard
Known truth and graders in code            catalog/manifest_index.parquet, the graders
Red teaming and injection defense          evals/redteam, the gate, docs/security.md
Observability                              packages/tracing, docs/observability.md,
                                           /traces
Cost control and model routing             providers/registry.yaml, the budget ledger,
                                           the cassettes
Resilience without a key                   the floor, the recorded session
Durable execution and human in the loop    the checkpointer, the interrupt path
Context engineering                        prompts/registry.yaml, the search and
                                           describe discipline, tokens per question
Semantic layer and data catalog            catalog/, the units, the synonym table
Security                                   the SQL guard, redaction, the identifier
                                           scan, the client budget
APIs and persistence                       packages/api, check_persistence.py
Serverless deployment                      vercel.json, the cold start measurement
Spec driven, agent assisted engineering    AGENTS.md, .claude/skills, docs/SPEC.md,
                                           .mcp.json, DECISIONS.md
Interoperability standards                 server.json, the connect page, A2A if built
Frontend for agents                        web/ (streaming, chips, the viewer)
Statistics for evaluation                  Wilson intervals, Benjamini-Hochberg, kappa
Communication                              report/briefing.md, the pushback paragraphs
Reproducibility                            the claim gate, the rederive, the cassettes
```

## 18. Testing

- The three tests for every gate: em dash, vocabulary, statement, claim gate, palette validator (both surfaces and both cards), the planted identifier scan on the answer log and the traces, every catalog quarantine rule, every exemption rule of the readback gate, every interior test.
- **Protocol conformance**: two tools/list calls return identical bytes; every tool has an output schema and every result validates against it; discovery returns the supported revisions and the identity; every list and read result carries a ttl and a scope; a request with an unsupported protocol version in its metadata gets the unsupported version error; a request carrying traceparent produces a server span whose parent is the span of the caller; the stdio transport and the streamable HTTP transport answer the same list; no deprecated feature is advertised in the capabilities.
- **The SQL guard**: a write, a second statement, ATTACH, COPY, INSTALL, LOAD, PRAGMA, SET, a comment hiding a statement, a reference to another schema and a statement past the timeout are each refused with the clause named; LIMIT is rewritten to the ceiling; a clean SELECT runs.
- **The readback**: a manifest key agrees within half a unit of its rounding; a value one unit off disagrees; a fraction against a percent is refused as a unit mismatch, and converts when the catalog says both units; a result id from the same chain is found and a foreign id is refused.
- **The gate**: a planted unsupported number is caught; each exemption rule exempts its case and only its case; a repaired answer is labeled repaired; a second failure refuses; the gate refuses on nothing (an answer with no numbers passes).
- **Pre-registration**: the plan hash in the manifest equals the hash of the committed plan; the prompt registry hash likewise; a changed prompt changes the hash and fails the gate without a DECISIONS.md entry.
- **Providers**: the budget refuses at the cap and the router tries the next; the ledger row and the audit row share a transaction; a cassette replays; a changed prompt misses; a miss in CI fails with the digest; each structured output mode parses its fixture and the repair step repairs a planted malformed response.
- **The floor**: every in scope family on the development split produces an Answer with readbacks; the refusal family refuses; the grammar rejects an out of scope question.
- **The graph**: the interrupt pauses and resumes from the checkpoint; a kill between act and gate resumes; the tool call ceiling refuses the ninth call; summarization fires past the threshold and is labeled; redaction removes a planted email, phone number and identifier before the model and before storage.
- **Did the step run**: every claim was re-run (the readback call count equals the claim count); the cassette hit count equals the model call count in CI; the budget was decremented once per call; one invoke_agent span per turn with at least one execute_tool child; the trace parquet row count equals the span count.
- **Persistence**: test_answer_is_committed from an independent connection; test_audit_precedes_final_event; the out of process check in the container.
- **Evaluation**: the graders on fixtures with known verdicts; the split is stratified and reproducible under two PYTHONHASHSEED values; the scorecard reproduces from the cassettes; the Wilson interval and the Benjamini-Hochberg step on fixtures; the red team marker test fails when the defense is disabled (a deliberate violation).
- **Catalog**: every table in the lock has a catalog entry; every column has a unit and a definition or a quarantine row; every manifest key resolves; the lexical index returns the planted synonym.
- **Skills**: skills-ref validate on each skill; the name matches the directory; SKILL.md under 500 lines.
- **Determinism**: every seeded step sorts before it samples; every published table has a stable tie break; identical manifests under two PYTHONHASHSEED values; caches keyed by input digest.
- **The test server** refuses HEAD and answers a first 503, and the site client handles both.
- Notebooks in CI with nbmake; Playwright on the desk (a question answered with chips, a chip opens the SQL and the rows, the no model badge when the floor answers, the interrupt choices), the viewer (a waterfall renders, a span expands), the scorecard (the floor row first, intervals drawn), the connect page (every configuration block parses), the statement on every route.
- Property tests: the gate verdict is monotonic in tolerance; the readback is symmetric in unit conversion; the budget never goes negative; the Wilson interval contains the point estimate; the choice of the router is stable under a fixed ledger.
- Availability probes and named skip markers for Postgres, the provider keys, Ollama, the load test and the browser, with CI asserting each dependency in the container.

## 19. Definition of done, printed as a checklist

The build prints this list in its final message and in RESULTS.md, each line marked done or not done, with one sentence of evidence per line (a file, a test name, a URL, a number):

```
 1  Three warehouses fetched at pinned tags with digests, the catalog with a
    unit and a definition on every column or a quarantine row, the manifest
    index, the synonym table, the quarantine report published, provenance
    and licenses recorded
 2  Golden set of 150 committed with known truth, units, tolerances and the
    stratified split; the first ten run against the real marts at step three
 3  MCP server at the 2026-07-28 revision: seven tools with output schemas,
    resources, prompts, deterministic order, cache hints, discovery, trace
    context; stdio and streamable HTTP; conformance results published
 4  The SQL guard with every refusal tested; the readback tool; the lookup
    with the multi round trip pattern or its recorded fallback; the client
    budget
 5  Providers behind one router with a daily budget each, the ledger in the
    same transaction as the audit row, cassettes keyed by digest, the floor
    graded on both splits
 6  The graph with the gate, repair, refusal and interrupt paths, the
    middleware, the checkpointer, the prompt registry and the eval plan hashed
    before the first live call
 7  Server deployed on the host the probe chose, with Neon; live URL in the
    README; verified from a separate MCP client in a separate process with
    the client output printed
 8  Answers observed from an independent connection; audit before the final
    event; the shared transaction; the out of process check
 9  Tracing: one trace per turn across the protocol boundary, exported to
    Parquet, no content captured, rendered on the viewer
10  Scorecard on the test split per provider and family with intervals and
    Benjamini-Hochberg, the floor row, the development table, the red team
    table with 15 of 15 or the failures named, the gate catch list, the
    interior tests, the secondary judge with its agreement, the live share
    and cassette dates
11  The default live provider chosen on development and reported on test, or
    the floor if nothing beats it, stated in the README first paragraph
12  AGENTS.md, CLAUDE.md, the Copilot instructions, .mcp.json, three skills
    validated with skills-ref, docs/SPEC.md, server.json, docs/connect.md from
    one source
13  The desk live on GitHub Pages with chips on every number, tool cards, the
    interrupt choices, the no model badge; working from the recorded session
    when the API is asleep; the test server refuses what the host refuses
14  Traces, evals, catalog, connect, playbook and report pages live
15  Latency with cold start published; the live check in a real browser and
    from the separate client recorded in results/live_check.json
16  RESULTS.md with every figure re-derived by the gate and a specific
    limitations section
17  README with the matrix and this checklist; DECISIONS.md with at least ten
    dated entries, two reversals and every protocol decision; three executed
    notebooks with a dead end each; the pushback paragraph on every page
18  Coverage at or above 80 percent, mypy strict clean, ruff clean, zero em
    dashes, zero banned vocabulary, palette validator green including both
    card runs, skills valid, forty to sixty commits, the rederive run in a
    worktree before the tag, v0.1.0 pushed after the commits, Apache 2.0 for
    code with the terms of every warehouse restated, repo described, topics set
```

Stretch items (the apps extension, the agent card, the browser floor, the fourth warehouse, the editor manifests, the containers) are listed beneath the checklist as stretch, done or not done, and never counted toward it.

## 20. Stretch, only if the day allows

- The apps extension, the agent card, the browser floor, the fourth warehouse and the editor manifests, as steps 19 to 23.
- A second gate on definitions: a definition sentence in an answer matched to the definitions document by key phrase coverage, with its own catch list.
- A conversation export: a thread as a Markdown transcript with every readback inline, rendered by the claim gate.
- Multi turn golden cases: a follow up question that depends on the previous answer, graded on the second turn.

## 21. What not to build

- No answer with a number that was not read back.
- No gate that asks a model whether the number is right.
- No provider without a budget, and no CI job that calls a provider.
- No SQL that runs unparsed, and no connection that can write.
- No session state in the protocol; the revision has none, and a server minted handle passed as an argument is the only cross call state.
- No roots, sampling or logging features; they are deprecated under the revision.
- No embedding service; the lexical index with synonyms is the retriever, and the notebook records why.
- No person in the log, no question stored unredacted, no content in a span.
- No language model writing a sentence about a number into a document; answers from the agent stay in the desk and the log.
- No pooled scorecard across providers, and no live share extrapolated.
- No authentication beyond the client budget on a read only public server, since this is a demo and the README says so.
- No mandatory step replaced by a table entry.

Build it in the order in section 16. When you finish, print the file tree, the section 19 checklist with every line marked, the scorecard on the test split per provider and family with intervals, the floor row, the red team result, the gate catch count by provider, the protocol conformance summary (revision, discovery result, tool count, both transports, the trace context test), the live URL and the output of the separate client check, the latency with the cold start, the budgets used today by provider, the share of the test split graded live by provider, the prompt registry hash and the plan hash, the live check summary, and anything you could not measure or any dependency that was missing today.
