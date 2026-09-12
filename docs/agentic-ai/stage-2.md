# Stage 2: Planning Agent + Write Tools

Read stage-1.md first. This document builds on those concepts.

---

## 1. Read Tools vs Write Tools

Stage 1 tools were read-only:
  get_user_progress  -> SELECT from problems table
  get_weak_topics    -> SELECT from problems + topics

Stage 2 introduces write tools:
  create_study_plan  -> INSERT into study_plans + study_tasks tables

### Why write tools are more dangerous

A read tool that fails: user gets an error message. Nothing changes.
A write tool that fails half-way: you could have partial data in the database.
A write tool with bad input from the LLM: you could write garbage to production.

This is why write tools require two extra steps that read tools do not:

  LLM output
    |
    v
  Pydantic validation   <- shape check (required fields, types)
    |
    v
  Business validation   <- logic check (hours sensible? topics exist?)
    |
    v
  write to database     <- only if both validations pass

Read tools skip the first two steps because they cannot corrupt data.

---

## 2. Structured Output

When the LLM generates a study plan, we do NOT want:

  "Here is your plan: Day 1 focus on Graphs for 3 hours,
   then Day 2 tackle DP for 2 hours..."

We cannot parse that reliably into database records.

We want:

  {
    "title": "7-Day Interview Plan",
    "duration_days": 7,
    "daily_hours": 3,
    "days": [
      {
        "day_number": 1,
        "focus": "Graphs",
        "tasks": [
          {"title": "BFS traversal", "estimated_minutes": 60, "priority": "HIGH"},
          {"title": "DFS problems", "estimated_minutes": 90, "priority": "HIGH"}
        ]
      }
    ]
  }

This JSON is:
  - Predictable: every plan has the same shape
  - Parseable: we can validate it with Pydantic
  - Storable: we can map it directly to database records
  - Verifiable: we can check hours, durations, field presence

### How we get structured output from the LLM

We do NOT use a "response schema" parameter (not all models support it).
Instead, we instruct the LLM in the system prompt and tool description:

  "When creating a plan, call create_study_plan() with a JSON object
   matching this exact schema..."

The LLM then provides the structured data as arguments to create_study_plan().
Tool arguments are already structured (they follow the tool schema).
This is actually cleaner than asking for structured text output.

---

## 3. LLM Reasoning vs Deterministic Logic

This is the most important concept in Stage 2.

The LLM is good at:
  - Understanding what the user wants ("I have 7 days, focus on graphs")
  - Deciding which topics to prioritize ("Graphs is weakest, put it first")
  - Writing human-readable explanations
  - Adapting tone and detail level

The LLM is NOT reliable for:
  - Enforcing that hours_per_day * num_tasks <= daily_hours
  - Ensuring topic_id values actually exist in the database
  - Guaranteeing all required fields are present
  - Preventing duplicate plans
  - Enforcing user ownership

The pattern we use:

  LLM decides WHAT  (which topics, what order, what tasks)
  Backend enforces HOW MUCH and WHETHER (constraints, ownership, existence)

Never trust the LLM to enforce application invariants.
Always validate before writing to the database.

Example of LLM reasoning that looks reasonable but could be wrong:

  LLM: "I'll schedule 4 hours of Graphs and 3 hours of DP on Day 1"
  User said: "I can study 5 hours per day"
  Total: 7 hours > 5 hours daily limit <- backend catches this

The LLM was trying to be helpful. The constraint enforcement is our job.

---

## 4. Tool Calling vs Structured Output - The Difference

These solve different problems and are often confused.

Tool calling:
  "LLM decides to request an action"
  LLM says: "Call get_weak_topics(user_id=1)"
  Your code executes the function and sends back the result.
  Used for: fetching data, triggering side effects, writing to DB.

Structured output:
  "LLM returns data in a predictable shape"
  LLM says: { "title": "Plan", "days": [...] }
  Your code parses and validates the JSON.
  Used for: getting structured data out of an LLM response.

In Stage 2, we use BOTH:
  Tool calling:      Gemini calls get_weak_topics() to fetch data
  Structured output: Gemini calls create_study_plan(plan={...}) where
                     plan is a structured JSON object

The trick: we get structured output THROUGH tool calling.
The plan JSON is the argument to the create_study_plan tool.
Tool arguments are inherently structured (they follow the tool schema).
This avoids parsing free-form text entirely.

---

## 5. The Planning Workflow

A planning request triggers a multi-step agent loop:

  Turn 1: User asks for a plan
  Turn 2: Gemini calls get_user_progress() to understand baseline
  Turn 3: Tool result returned to Gemini
  Turn 4: Gemini calls get_weak_topics() to find priorities  
  Turn 5: Tool result returned to Gemini
  Turn 6: Gemini calls get_goals() to understand deadlines
  Turn 7: Tool result returned to Gemini
  Turn 8: Gemini calls get_pending_revisions() to find revision debt
  Turn 9: Tool result returned to Gemini
  Turn 10: Gemini has enough data. Calls create_study_plan(plan={...})
  Turn 11: Backend validates the plan (Pydantic + business rules)
  Turn 12: If valid: write to DB. Return success to Gemini.
  Turn 13: Gemini produces a human-readable confirmation

This is the agent loop in action: multiple tool calls, each building
on the previous result, until the agent has enough information to act.

---

## Summary of Stage 2 Concepts

| Concept | Stage 1 | Stage 2 |
|---------|---------|---------|
| Tool type | Read-only | Read + Write |
| Validation | None needed | Pydantic + business rules |
| LLM output | Natural text | Natural text + structured plan |
| DB changes | None | study_plans + study_tasks |
| Risk | Low (no side effects) | Higher (writes to DB) |
