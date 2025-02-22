class Agent:
    def __init__(self):
        self.current_convo = []
        self.system_prompt = ""

    def add_message(self, message, role="user"):
        self.current_convo.append({"role": role, "content": message})

    def get_messages(self):
        return self.current_convo

    def clear_messages(self):
        self.current_convo = []

    def set_system_prompt(self, prompt):
        self.system_prompt = prompt

    def build_messages(self):
        return [
            {"role": m["role"], "content": m["content"]} for m in self.current_convo
        ]
