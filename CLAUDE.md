# CLAUDE.md

Read AGENTS.md first; it is the single source for setup, tests, gates, rules and the files not to
edit. For Claude Code specifically: .mcp.json connects this repository's own MCP server over stdio,
so you can ask the three warehouses a question while you work, and .claude/skills holds the three
procedures (warehouse-question, golden-question, release-gate). Use the warehouse-question skill
before stating any number from the warehouses in a commit message or a document.
