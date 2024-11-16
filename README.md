# Claude Thinking Chain

A Python application that implements Claude's thinking chain mechanism with a graphical user interface. This tool helps break down complex tasks into structured thinking steps, providing real-time visualization of the thought process and ensuring high-quality outputs through continuous assessment and improvement.

## Inspiration & Acknowledgments

This project is inspired by [Thinking Claude](https://github.com/richards199999/Thinking-Claude/) by [richards199999](https://github.com/richards199999/).

The entire development process was completed with the assistance of Claude Sonnet (include this Readme).

The project uses OpenRouter API, which provides the flexibility to switch between different AI models as needed.

## Features

- **Interactive GUI**: Split-screen interface with chat and thinking process displays
- **Structured Thinking Process**: Breaks down tasks into analytical phases
- **Real-time Visualization**: Shows thinking progress and intermediate results
- **Quality Assessment**: Automatic quality scoring and improvement suggestions
- **Context Awareness**: Option to include conversation history
- **Bilingual Support**: Handles both English and Chinese content
- **Token Usage Tracking**: Monitors API usage and estimates costs

## Installation

1. Clone the repository:
```bash
git clone https://github.com/z060142/claude-thinking-chain.git
cd claude-thinking-chain
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a .env file in the project root with your API credentials:
```bash
OPENROUTER_API_KEY=your_api_key_here
SITE_URL=your_site_url
APP_NAME=ThinkingChain
```

**Required Packages
- tkinter (usually comes with Python)
- requests
- python-dotenv
- json5
- logging

## Usage

1.Run the application:
```bash
python ui.py
```
2. Enter your query in the input box
3. Optional: Check "與記錄對話" to include conversation history
4. Click "Send" or press Enter to process your query
