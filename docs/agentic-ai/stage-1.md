# Stage 1: Agentic AI — Learning the Fundamentals

This document explains every concept you need to understand before reading the code.
Read this first. Then read `stage-1-flow.md` for a concrete worked example.

---

## 1. What is an LLM API?

An LLM (Large Language Model) API is an HTTP service that accepts text as input
and returns generated text as output.

**The request has three main parts:**

| Part | What it is |
|---|---|
| `model` | Which AI model to use. E.g. `gemini-2.5-flash` |
| `messages` | The conversation history as a list |
| `tools` | (Optional) Functions the model is allowed to call |

**Messages come in three roles:**

- `system` — Instructions to the model about how to behave.
  "You are a helpful preparation assistant."
  The model reads this but the user never sees it directly.
- `user` — What the human said. "How am I doing in DSA?"
- `assistant/model` — What the model replied.

The conversation is **stateless**. The LLM has no memory between requests.
Every call sends the ENTIRE conversation history from scratch.
That is why the agent loop keeps building up a messages list.

---

## 2. What is Structured Output?

When you ask an LLM a question, it returns free-form text by default.
The problem: you cannot reliably parse this in code.

Structured output means you instruct the model to return a specific JSON shape:

```json
{
  "total_problems": 30,
  "solved": 12,
  "weak_topics": ["Graphs", "DP"],
  "recommendation": "Focus on Graphs next"
}
```

Now your application can read `response["weak_topics"]` predictably.

For Stage 1, our tools return structured Python dicts.
The model final answer is plain text - fine for a chat response.

---

## 3. What is Tool / Function Calling?

This is the most important concept. Read carefully.

**Without tools:**
User: "How many problems have I solved?"
LLM:  "I do not have access to your data, so I cannot answer that."

**With tools:**
User: "How many problems have I solved?"
LLM:  -> function_call: get_user_progress(user_id=1)
App:  executes the Python function, returns {"solved": 12, ...}
LLM:  "You have solved 12 problems so far."

### The Critical Distinction

The LLM does NOT execute code. It cannot call Python functions directly.

What actually happens:

1. LLM returns a "function_call" object:
   { "name": "get_user_progress", "args": { "user_id": 1 } }

2. YOUR Python code reads this object.
   YOUR Python code calls the actual function.
   YOUR Python code sends the result back to the LLM.

3. The LLM uses the result to write a final response.

The LLM is just saying: "I want this function called with these arguments."
It is your application job to actually do it.

---

## 4. What is a Tool Schema?

For the LLM to know which tools exist, you give it a schema - a structured
description of each tool.

A tool schema tells the model:
- name: must exactly match your Python function
- description: what the model reads to decide when to call it (very important!)
- parameters: what arguments to provide, and their types

Good descriptions are critical. The model decides whether to use a tool
based almost entirely on the description.

---

## 5. The Tool Call Lifecycle

```
Step 1: User sends "What topics am I weak at?"

Step 2: Python builds a messages list and sends it to Gemini
        along with the tool schema definitions.

Step 3: Gemini decides: "I need data. I will call get_weak_topics."

Step 4: Gemini returns:
        function_call { name: "get_weak_topics", args: { user_id: 1 } }
        (No text yet - the model is waiting for data.)

Step 5: Python detects the function_call.
        Python looks up "get_weak_topics" in a dispatch table (dict).
        Python calls the actual function with the arguments.

Step 6: Function queries the database via repository layer.
        Returns a Python dict.

Step 7: Python sends the dict back to Gemini as a "function_response" message.

Step 8: Gemini generates a final text response using the data.
        "You appear weakest in Graphs and DP..."

Step 9: Python returns this to the FastAPI endpoint -> user.
```

---

## 6. What is an Agent Loop?

An agent is just a loop. There is no magic.

```python
messages = [initial_user_message]

for iteration in range(MAX_ITERATIONS):
    response = call_gemini(messages, tools)

    if response has a function_call:
        result = execute_tool(response.function_call)
        messages.append(model_turn_with_function_call)
        messages.append(tool_result_turn)
        # Loop again - give result back to the model

    else:
        return response.text   # Model gave plain text: done!
```

Why a MAX_ITERATIONS limit? Without it, a misbehaving model could loop
forever. We set a limit (5) to prevent infinite loops.

---

## Summary

| Concept | One sentence |
|---|---|
| LLM API | Send messages, get text back |
| Messages | Ordered conversation: system/user/assistant/tool |
| Tool schema | Tell the model what functions exist and when to use them |
| Function call | Model requests a function; your code executes it |
| Tool result | You send the function output back to the model |
| Agent loop | Repeat until the model gives a plain text answer |
