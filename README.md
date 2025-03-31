# Interactive Text Adventure Game

An interactive text-based adventure game that uses natural language processing and LLM technology to create a dynamic, responsive world.

## Features

- Natural language command processing
- Local LLM integration for dynamic responses
- RAG (Retrieval Augmented Generation) for context-aware interactions
- Persistent world knowledge database
- Dynamic story progression based on player actions

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your configuration:
```
OPENAI_API_KEY=your_api_key_here
```

4. Run the game:
```bash
python main.py
```

## Project Structure

- `main.py`: Main game entry point
- `game/`: Core game logic
  - `engine.py`: Game engine and state management
  - `llm.py`: LLM integration
  - `rag.py`: RAG system for context retrieval
  - `database.py`: Database management
  - `parser.py`: Command parsing and processing
- `data/`: World knowledge and game data
- `tests/`: Test files

## How to Play

1. Start the game
2. Enter natural language commands to interact with the world
3. The game will process your commands using the LLM and RAG system
4. Your actions will be recorded and affect the world state
5. Continue exploring and interacting with the world

## Contributing

Feel free to submit issues and enhancement requests! 