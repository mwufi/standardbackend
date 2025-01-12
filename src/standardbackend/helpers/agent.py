class Agent:
    """A thin wrapper around system prompt, meant to be used in a thread!"""

    def __init__(self, name: str, prompt: str):
        self.name = name
        self.prompt = prompt

    def get_current_context(self):
        return self.prompt
