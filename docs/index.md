# Angel Claw Documentation

Welcome to Angel Claw, your personal AI assistant. This guide will help you get started with the system and understand its core features.

## Overview
Angel Claw is an intelligent personal assistant that combines long-term memory with an extensible skills system. It can remember facts about you, your preferences, and autonomously expand its own capabilities.

## Getting Started

### 1. Installation
Ensure you have the dependencies installed:
```bash
pip install -e .
```

### 2. Configuration
Set up your `.env` file with your model and API key:
```bash
MODEL=openai/gpt-4o
MODEL_KEY=your-api-key
```

### 3. Usage (CLI)
Start a chat session using the CLI:
```bash
python main.py chat
```

## Core Features

### Persistent Memory
Angel Claw automatically remembers important details from your conversation. You can also explicitly tell it to remember things:
- "Remember that I live in London."
- "I prefer dark mode in my IDE."
- "What do you know about my work?"

### Autonomous Skills
Angel Claw can learn new tasks by creating Python tools on the fly. You can ask it to create skills or import them from external definitions.

Check out the [Skills Documentation](skills.md) to learn more.
