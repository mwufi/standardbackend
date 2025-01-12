def hello() -> str:
    return "Hello from standardbackend!"


from standardbackend.helpers.agent import Agent
from standardbackend.helpers.thread import Thread

__all__ = ["Agent", "Thread"]
