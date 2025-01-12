def pretty_print_messages(messages):
    """Pretty print conversation messages with color coding"""
    from termcolor import colored

    for msg in messages:
        # Handle both dict and Message objects
        if isinstance(msg, dict):
            role = msg["role"]
            content = msg["content"]
        else:
            role = msg.role
            content = msg.content

        # Print role header
        if role == "user":
            print(colored(f"\n[User]", "green", attrs=["bold"]))
        elif role == "assistant":
            print(colored(f"\n[Assistant]", "blue", attrs=["bold"]))

        # Handle different content types
        if isinstance(content, str):
            # Simple text content
            print(content)
        elif isinstance(content, list):
            # Complex content with blocks
            for block in content:
                if isinstance(block, dict):
                    # Tool result block
                    if block["type"] == "tool_result":
                        print(colored("\n[Tool Result]", "yellow", attrs=["bold"]))
                        print(block["content"])
                    # Message block from assistant
                    elif block["type"] == "text":
                        print(block["text"])
                    elif block["type"] == "tool_use":
                        print(colored("\n[Tool Use]", "magenta", attrs=["bold"]))
                        print(f"Tool: {block['name']}")
                        print(f"Input: {block['input']}")
                else:
                    # Handle typed blocks
                    if block.type == "tool_result":
                        print(colored("\n[Tool Result]", "yellow", attrs=["bold"]))
                        print(block.content)
                    elif block.type == "text":
                        print(block.text)
                    elif block.type == "tool_use":
                        print(colored("\n[Tool Use]", "magenta", attrs=["bold"]))
                        print(f"Tool: {block.name}")
                        print(f"Input: {block.input}")
