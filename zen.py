from standardbackend.helpers.thread import Thread
from standardbackend.utils import pretty_print_messages


# Chain of tool interactions
analysis_thread = Thread()
messages = analysis_thread.send_message("What's my current CPU usage? Use the tool!")
# Then ask for analysis of that data
messages = analysis_thread.send_message(
    "Based on the CPU usage you just checked, would you recommend running a heavy computation task right now? Why?"
)
pretty_print_messages(messages)
