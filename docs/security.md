# Security

What readback defends, and how each defense is tested.

- **The SQL guard.** One statement, parsed by sqlglot in the DuckDB dialect; only a SELECT, a WITH
  over a SELECT, or a set operation of SELECTs; no write, ATTACH, COPY, INSTALL, LOAD, PRAGMA, SET,
  DESCRIBE or SHOW anywhere in the tree; no function that reads a file or the environment; tables
  only from the named warehouse schema; a row ceiling and a ten second timeout.
  tests/warehouse/test_guard.py has one case per refusal.
- **The read only connection,** the second line: the views live in a database file opened read
  only, external access is off except for the exact files the lock names, extensions cannot load,
  and the configuration is locked. A test sends a write past the guard and the connection refuses it.
- **Redaction.** Emails, phone numbers, card numbers and account style identifiers are removed from a
  question before a model sees it or the log stores it. The agent records only how many it removed.
- **The identifier scan** reads everything published, the answer log and the traces for a card
  number, an email, a phone number or a planted token.
- **Injection.** Text in a tool result, a table cell or a catalog entry is data. The floor quotes a
  definition only when the catalog cites it to a build's definitions document by line; the system
  prompt says the same to a model; and the gate refuses any number that did not come from a tool. The
  red team (evals/redteam) plants instructions in a catalog entry and in a table cell, fakes system
  notes in the question, asks for writes and for the system prompt. Its first run caught a real hole;
  DECISIONS.md has it.
- **The free tier.** No token, a read only server, 60 requests an hour and 600 a day per client (a
  hash of the address), and the ceilings on rows, time and k.

## What the platform engineer would push back on

There is no authentication, by design, because the data is public and the server cannot write; a
caller who rotates addresses can spend more than one client's budget. The redaction patterns are
patterns, so a question can carry something they do not recognize; the identifier scan is the check
behind them, not a guarantee.
