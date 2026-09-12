# Stage 1 Flow: A Complete Request Walkthrough

This file shows one real request end-to-end with the actual data structures
that flow between the user, the FastAPI app, Gemini, and the database.

---

## The Request

User types in the chat UI:

```
"What topics am I weak at?"
```

This hits: POST /api/v1/agent/chat
Request body: { "message": "What topics am I weak at?" }

---

## Step 1: FastAPI Receives the Request

The endpoint in `api/v1/agent.py` receives the message.
It calls `agent.run(user_message="What topics am I weak at?", db=session)`.

---

## Step 2: Agent Builds the Initial Messages List

The agent constructs a messages list to send to Gemini:

```python
messages = [
    {
        "role": "user",
        "parts": ["What topics am I weak at?"]
    }
]
```

It also prepares a system instruction:
```
"You are PrepPilot, an AI preparation assistant.
 You help students track their DSA, Core CS, and GATE preparation.
 Use the available tools to fetch data before answering.
 Always fetch data before giving specific numbers or recommendations."
```

---

## Step 3: Agent Calls Gemini (First Turn)

Python sends to Gemini:
- The system instruction
- The messages list (1 message so far)
- The tool definitions for: get_user_progress, get_weak_topics

Gemini reads the user question.
Gemini reads the tool descriptions.
Gemini decides: "I need to call get_weak_topics to answer this."

---

## Step 4: Gemini Returns a Function Call

Gemini does NOT return text. It returns:

```json
{
  "candidates": [{
    "content": {
      "role": "model",
      "parts": [{
        "function_call": {
          "name": "get_weak_topics",
          "args": {
            "user_id": 1
          }
        }
      }]
    }
  }]
}
```

This is NOT code execution. Gemini is saying:
"Please call this function and give me the result."

---

## Step 5: Python Detects and Executes the Tool

The agent loop detects `function_call` in the response.

```python
tool_name = "get_weak_topics"
tool_args = {"user_id": 1}

# Dispatch table lookup
func = TOOL_DISPATCH[tool_name]   # points to get_weak_topics function
result = await func(db=session, **tool_args)
```

`get_weak_topics` queries the database via `ProblemRepository`:
- Gets all problems for user_id=1
- Groups by topic
- Finds topics with low solve rate or low confidence

Returns:
```python
{
    "topics": [
        {
            "topic": "Graphs",
            "subject": "DSA",
            "problem_count": 8,
            "solved_count": 2,
            "mastered_count": 0,
            "solve_rate": 0.25,
            "reason": "Only 2 of 8 problems solved, 0 mastered"
        },
        {
            "topic": "Dynamic Programming",
            "subject": "DSA",
            "problem_count": 10,
            "solved_count": 3,
            "mastered_count": 1,
            "solve_rate": 0.3,
            "reason": "Only 3 of 10 problems solved"
        }
    ]
}
```

---

## Step 6: Python Adds the Tool Result to Messages

The agent adds two things to the messages list:
1. The model turn (what Gemini returned — the function_call)
2. A function_response turn (what the tool returned)

The messages list now looks like:

```python
[
    # Turn 1: User
    {"role": "user", "parts": ["What topics am I weak at?"]},

    # Turn 2: Model (Gemini said: call get_weak_topics)
    {"role": "model", "parts": [function_call_part]},

    # Turn 3: Tool result (we are returning the data)
    {"role": "user", "parts": [
        genai.protos.Part(
            function_response=genai.protos.FunctionResponse(
                name="get_weak_topics",
                response={"result": <the dict above>}
            )
        )
    ]}
]
```

Note: In the Gemini SDK, function_response parts are sent as "user" role.
This is correct and expected.

---

## Step 7: Agent Calls Gemini (Second Turn)

The agent loops again, sending the full updated messages list to Gemini.

This time Gemini has the tool result.
It does NOT request another tool.
It generates a final text response.

---

## Step 8: Gemini Returns Final Text

```json
{
  "candidates": [{
    "content": {
      "role": "model",
      "parts": [{
        "text": "Based on your progress data, you appear weakest in two areas:\n\n**Graphs** — You've attempted 8 problems but only solved 2 (25% solve rate). No problems are mastered yet. This is a significant gap.\n\n**Dynamic Programming** — 3 out of 10 problems solved (30% solve rate) with only 1 mastered.\n\nI'd recommend focusing on Graphs first since it has the lowest solve rate. Start with basic BFS/DFS before moving to advanced graph algorithms."
      }]
    }
  }]
}
```

---

## Step 9: FastAPI Returns the Response

The endpoint returns:

```json
{
  "response": "Based on your progress data, you appear weakest in two areas:\n\n**Graphs** — You've attempted 8 problems but only solved 2 (25% solve rate)...",
  "tool_calls": [
    {
      "tool": "get_weak_topics",
      "args": {"user_id": 1},
      "result_summary": "Found 2 weak topics"
    }
  ]
}
```

---

## Full Conversation History at End of Request

```
Turn 1 [user]:    "What topics am I weak at?"
Turn 2 [model]:   function_call: get_weak_topics({user_id: 1})
Turn 3 [user]:    function_response: {topics: [...]}
Turn 4 [model]:   "Based on your progress data, you appear weakest in..."
```

The next request starts fresh — this history is NOT stored between requests.
That is what "stateless" means.

---

## What Makes This "Agentic"

A simple LLM call:  User -> Gemini -> Response  (1 round trip)

An agent:           User -> Gemini -> tool_call -> Python executes
                         -> tool_result -> Gemini -> Response  (2+ round trips)

The model is "in the loop" — it receives data, decides what to do next,
and can chain multiple tool calls before giving a final answer.

In Stage 2, we will give the agent write tools like `create_study_plan()`.
That is when it becomes genuinely useful as a planning system.
