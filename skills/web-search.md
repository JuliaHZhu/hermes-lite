---
name: web-search
description: Search the web and summarize findings.
trigger: search, look up, research, find, google
tools:
  - net_web_search
  - net_web_extract
---

## Usage

When the user asks to search for something, use `net_web_search` first.
If a specific page needs to be read, use `net_web_extract`.
