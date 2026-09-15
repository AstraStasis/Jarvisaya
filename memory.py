import os
import json

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "memory.json")

def _load_memories() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {}
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_memories(data: dict):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_all_memories() -> list:
    mem = _load_memories()
    return [fact for fact in mem.values()]

def remember_fact(fact: str) -> str:
    """Saves a fact, preference, or detail about the user into long-term memory."""
    mem = _load_memories()
    if fact not in mem.values():
        key = f"fact_{len(mem)}"
        mem[key] = fact
        _save_memories(mem)
        return f"I will remember that: {fact}"
    return "I already know that."

def forget_fact(fact_substring: str) -> str:
    """Removes a fact from long-term memory if it matches the substring."""
    mem = _load_memories()
    removed = False
    new_mem = {}
    idx = 0
    for k, v in mem.items():
        if fact_substring.lower() in v.lower():
            removed = True
        else:
            new_mem[f"fact_{idx}"] = v
            idx += 1
            
    if removed:
        _save_memories(new_mem)
        return f"I have forgotten the fact related to: '{fact_substring}'"
    return f"I could not find any memory matching '{fact_substring}'."
