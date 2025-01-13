from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict


class AgentInterface(ABC):
    @abstractmethod
    def send_message(self, message: str, thread_id: str) -> List[Dict[str, Any]]:
        """Send a message and get response"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent"""
        pass

    @abstractmethod
    def create_thread(self, thread_id: str) -> None:
        """Initialize a new thread"""
        pass


class AnthropicAgent(AgentInterface):
    def __init__(self, name: str, system_prompt: str, tools: Optional[List] = None):
        from standardbackend.helpers.thread import Thread
        from standardbackend.helpers.agent import Agent

        self.name = name
        self.agent = Agent(name, system_prompt)
        self.tools = tools
        self.threads: Dict[str, "Thread"] = {}

    def create_thread(self, thread_id: str) -> None:
        from standardbackend.helpers.thread import Thread

        if thread_id in self.threads:
            raise ValueError(f"Thread {thread_id} already exists")

        self.threads[thread_id] = Thread(tools=self.tools, agent=self.agent)

    def send_message(self, message: str, thread_id: str) -> List[Dict[str, Any]]:
        if thread_id not in self.threads:
            raise ValueError(f"Thread {thread_id} not found")

        return self.threads[thread_id].send_message(message)

    def get_system_prompt(self) -> str:
        return self.agent.prompt
