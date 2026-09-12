# Stage 2 Flow: Planning Agent Complete Walkthrough

## The Request

User: "I have an interview in 7 days. I can study 3 hours/day.
       Create a preparation plan for me."

POST /api/v1/agent/chat
Body: { "message": "I have an interview in 7 days. I can study 3 hours/day. Create a preparation plan for me." }

---

## Messages at Each Turn

### Turn 1: User message sent to Gemini

Messages list:
  [
    { "role": "user", "parts": ["I have an interview in 7 days..."] }
  ]

Gemini available tools:
  - get_user_progress
  - get_weak_topics
  - get_goals
  - get_pending_revisions
  - create_study_plan

---

### Turn 2: Gemini decides to fetch progress first

Gemini returns:
  function_call { name: "get_user_progress", args: { user_id: 1 } }

[LLM DECISION - not code logic]
Gemini decided to call this because the system prompt says:
"Fetch data before creating a plan."

Python executes: get_user_progress(db, user_id=1)

Database query: SELECT * FROM problems WHERE user_id=1

Result:
  {
    "total_problems": 30,
    "solved": 12,
    "mastered": 2,
    "solve_rate": 0.4,
    "pending_revisions": 3,
    "active_goals": 1
  }

Messages list now:
  [
    { user: "I have an interview..." },
    { model: function_call(get_user_progress) },
    { user: function_response({ result: { total_problems: 30, ... } }) }
  ]

---

### Turn 3: Gemini asks for weak topics

Gemini returns:
  function_call { name: "get_weak_topics", args: { user_id: 1 } }

Python executes: get_weak_topics(db, user_id=1)

Result:
  {
    "weak_topics": [
      { "topic": "Graphs", "solve_rate": 0.2, "reason": "only 2/8 solved" },
      { "topic": "DP", "solve_rate": 0.3, "reason": "only 3/10 solved" }
    ]
  }

---

### Turn 4: Gemini asks for goals

Gemini returns:
  function_call { name: "get_goals", args: { user_id: 1 } }

Python executes: get_goals(db, user_id=1)

Result:
  {
    "goals": [
      {
        "id": 1,
        "title": "EPAM SDE Interview",
        "goal_type": "PLACEMENT",
        "priority": "HIGH",
        "target_date": "2026-09-19",
        "days_remaining": 7
      }
    ]
  }

---

### Turn 5: Gemini asks for pending revisions

Gemini returns:
  function_call { name: "get_pending_revisions", args: { user_id: 1 } }

Python executes: get_pending_revisions(db, user_id=1)

Result:
  {
    "pending_revisions": [
      { "topic": "Binary Search", "planned_date": "2026-09-10", "days_overdue": 2 }
    ],
    "count": 1
  }

---

### Turn 6: Gemini has enough data. Calls create_study_plan.

Gemini returns:
  function_call {
    name: "create_study_plan",
    args: {
      user_id: 1,
      title: "7-Day Interview Preparation Plan",
      duration_days: 7,
      daily_hours: 3,
      goal_id: 1,
      days: [
        {
          day_number: 1,
          focus: "Graphs - BFS & DFS",
          tasks: [
            { title: "BFS traversal pattern", estimated_minutes: 60, priority: "HIGH", topic_id: null },
            { title: "DFS recursive + iterative", estimated_minutes: 60, priority: "HIGH", topic_id: null },
            { title: "Graph problem set (easy)", estimated_minutes: 60, priority: "MEDIUM", topic_id: null }
          ]
        },
        {
          day_number: 2,
          focus: "Graphs - Advanced",
          tasks: [
            { title: "Shortest path (Dijkstra)", estimated_minutes: 90, priority: "HIGH", topic_id: null },
            { title: "Topological sort", estimated_minutes: 90, priority: "MEDIUM", topic_id: null }
          ]
        },
        ...
      ]
    }
  }

[LLM DECISION]
Gemini allocated more time to Graphs (days 1-2) because get_weak_topics
showed it has the lowest solve rate (0.2).

---

### Turn 7: Backend validates the plan

Python calls: validate_plan(plan_data)

Checks performed:
  [PASS] duration_days == 7 (positive, matches request)
  [PASS] daily_hours == 3 (positive, user specified this)
  [PASS] Day 1: 60+60+60 = 180 minutes = 3 hours <= 3 hours limit
  [PASS] Day 2: 90+90 = 180 minutes = 3 hours <= 3 hours limit
  [PASS] All tasks have positive estimated_minutes
  [PASS] user_id matches DEV_USER_ID (ownership check)
  [PASS] Plan has at least 1 task

Validation passed. Proceed to persistence.

---

### Turn 8: Backend persists the plan

study_plans INSERT:
  { user_id: 1, title: "7-Day Interview Preparation Plan",
    duration_days: 7, daily_hours: 3, status: "ACTIVE", goal_id: 1 }

study_tasks INSERT (one per task, 7 days x ~3 tasks = ~21 tasks):
  { plan_id: 1, day_number: 1, title: "BFS traversal pattern",
    estimated_minutes: 60, priority: "HIGH" }
  { plan_id: 1, day_number: 1, title: "DFS recursive + iterative",
    estimated_minutes: 60, priority: "HIGH" }
  ...

Tool returns to Gemini:
  {
    "success": true,
    "plan_id": 1,
    "tasks_created": 21,
    "message": "Plan created successfully"
  }

---

### Turn 9: Gemini produces final response

Gemini uses the tool result to write:

  "Your 7-day preparation plan has been created!

   Here is the breakdown:

   Days 1-2: Graphs (your weakest area at 25% solve rate)
     - BFS/DFS fundamentals
     - Dijkstra and topological sort

   Days 3-4: Dynamic Programming (30% solve rate)
     - Fibonacci variants, coin change, knapsack
     ...

   I have also scheduled Binary Search revision on Day 1 since
   you have an overdue revision from 2 days ago.

   Each day is 3 hours as you requested. Good luck with the interview!"

---

## What Changed vs Stage 1

Stage 1 agent loop:
  User -> Gemini -> [0-2 tool calls] -> text response
  No side effects. Nothing written to DB.

Stage 2 agent loop:
  User -> Gemini -> [3-5 read tool calls] -> Gemini reasons
       -> create_study_plan (write tool) -> validation -> DB write
       -> Gemini confirmation -> text response with plan

---

## LLM Decisions vs Backend Guarantees

LLM decided:
  - Which topics to prioritize (Graphs first because lowest solve_rate)
  - How many tasks per day
  - What the task titles should be
  - The order of topics across 7 days
  - The wording of the final response

Backend guaranteed:
  - Total minutes per day <= daily_hours * 60
  - All required fields are present
  - user_id is the authenticated user (no cross-user writes)
  - Plan has at least 1 task
  - Duration is positive
  - Data was actually written to the database

This is the correct separation of concerns:
  LLM = intelligent decision maker
  Backend = strict enforcer
