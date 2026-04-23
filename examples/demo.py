from core.reflective_loop import ReflectiveLoop

loop = ReflectiveLoop(
    safety_guardrails=[
        {"type": "hard", "keywords": ["harm", "illegal"]}
    ]
)

print(loop.route_decision("test task"))
