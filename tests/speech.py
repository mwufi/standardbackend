import os
import tempfile
from mainframe_orchestra import RecordingTools, WhisperTools, TextToSpeechTools

from dotenv import load_dotenv

load_dotenv()

def respond_task(user_message, conversation_history):
    from mainframe_orchestra import OpenaiModels
    
    response = OpenaiModels.gpt_4o(
        messages=[
            {"role": "system", "content": "You are a helpful assistant engaging in conversation."},
            {"role": "user", "content": f"Conversation history:\n{conversation_history}\n\nUser's latest message: {user_message}\n\nRespond naturally to the user's latest message, taking into account the conversation history."}
        ]
    )
    
    return response

def main():
    conversation_history = []
    temp_dir = tempfile.mkdtemp()
    audio_file = os.path.join(temp_dir, "recorded_audio.wav")

    print("Enter 'q' to quit.")

    while True:
        user_input = input("Press Enter to start recording (or 'q' to quit): ").lower()
        if user_input == 'q':
            print("Exiting...")
            break

        # Record user input via microphone upon 'enter'
        RecordingTools.record_audio(audio_file)
        
        # Transcribe the audio
        transcription = WhisperTools.whisper_transcribe_audio(audio_file)

        # Collect the text from the transcription
        user_message = transcription['text'] if isinstance(transcription, dict) else transcription

        # Add the user's message to the conversation history
        conversation_history.append(f"User: {user_message}")

        # Agent acts and responds to the user
        response = respond_task(user_message, conversation_history)
        conversation_history.append(f"Assistant: {response}")
        print("Assistant's response:")
        print(response)

        # Read the agent response out loud
        TextToSpeechTools.elevenlabs_text_to_speech(text=response)

    # Clean up the temporary directory
    os.rmdir(temp_dir)

if __name__ == "__main__":
    main()
