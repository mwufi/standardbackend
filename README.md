# OpenAI GPT-4 Completion Service

A FastAPI service that provides an endpoint for OpenAI GPT-4 completions.

## Setup

1. Create a `.env` file in the root directory and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the service:
```bash
python main.py
```

The service will be available at `http://localhost:8000`

## API Endpoints

### POST /completion

Send a completion request with messages.

Example request:
```json
{
    "messages": [
        {
            "role": "user",
            "content": "Hello, how are you?"
        }
    ]
}
```

Example response:
```json
{
    "content": "I'm doing well, thank you for asking! How can I help you today?",
    "role": "assistant",
    "finish_reason": "stop"
}
```
