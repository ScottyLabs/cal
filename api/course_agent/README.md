# Course-Agent: Autonomous Discovery of CMU Course Calendars

This repository contains an **agentic AI system** that autonomously discovers
official Carnegie Mellon University course websites and extracts embedded
Google Calendar (iCal) information when available. It is a multi-agent architecture where one agent proposes candidate course websites and a separate critic agent independently evaluates the decision, vetoing weak or ambiguous verifications before any data is committed.

The system operates under uncertainty:

- No predefined list of course website domains
- Some courses have no public websites
- Some websites do not publish calendars

To handle this, we model discovery as a **probabilistic, auditable agent workflow**
rather than a deterministic scraper.

______________________________________________________________________

## Goals

For each CMU course:

1. Discover candidate course websites using web search
1. Verify which (if any) site is the official course website
1. Detect embedded Google Calendars via HTML iframe inspection
1. Persist all results, including failures, to Supabase for auditing and review

______________________________________________________________________

## Why Agentic AI?

This task requires:

- Search under uncertainty
- Semantic relevance judgment
- Conditional branching
- Tool orchestration
- Graceful failure handling

A single script is brittle, while an agent can **observe -> decide -> act -> record**.

______________________________________________________________________

## Architecture Overview

To visualize LangGraph, run `python -m course_agent.scripts.visualize_graph` in root directory, then paste the content into [https://mermaid.live](https://mermaid.live).

<img width="447" height="572" alt="course_agent_graph" src="https://github.com/user-attachments/assets/6d893a8c-6a8a-4e7d-8eb0-2581f44e63de" />

______________________________________________________________________

## Data Model (Supabase)

- `courses`: canonical course data (input)
- `course_websites`: discovered candidate websites + confidence
- `calendar_sources`: extracted calendar artifacts
- `agent_runs`: metadata for reproducibility and auditing

______________________________________________________________________

## Setup

### 1. Install dependencies

From `api/`:

```bash
uv sync
```

### 2. Environment Variables

Make sure `.env.development` contains the follow values:

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_HTTP_REFERER=http://localhost:5001
OPENROUTER_X_TITLE=cmucal-course-agent
SERPER_API_KEY=...
```

### 3. Run it from `api/`

`uv run python -m course_agent.scripts.run_all_courses`

## Trouble shooting

- If encounter `postgrest.exceptions.APIError: {'message': 'permission denied for table agent_runs', 'code': '42501', 'hint': None, 'details': None}`, run the following query in Supabase's SQL Editor
  - `GRANT ALL PRIVILEGES ON TABLE agent_runs TO service_role;`

## Next Steps

- Tested using 4 CMU courses and achieved 100% accuracy on identifying the course website and extracting ical link from home page. However, should use `fetch_all_courses` when actually running the script.
- features to add
  - visit all linked pages of the official website until a google calendar is found, in case calendars are linked in pages other than the homepage. for example: https://www.cs.cmu.edu/~mgormley/courses/10601/officehours.html
  - when a calendar is found, examine the events to see if OH is included. If so, create the category named `OH for xx-xxx`.
