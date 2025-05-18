from game.engine import GameEngine
import sys
import os
import json
import logging
from dotenv import load_dotenv
import argparse

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_welcome():
    """Print the welcome message and game instructions."""
    clear_screen()
    logger.debug("Displaying welcome message")
    print("""
    Welcome to the Interactive Text Adventure!
    
    You can interact with the world using natural language commands.
    For example:
    - "look around"
    - "go north"
    - "take the torch"
    - "examine the wall"
    
    Type 'quit' to exit the game.
    Type 'save' to save your progress.
    Type 'load' to load a saved game.
    
    Press Enter to begin...
    """)
    input()

def log_state(engine: GameEngine, action: str, result: str, debug: bool):
    """Log the current game state if in debug mode."""
    if not debug:
        return
    
    logger.debug("=== Game State ===")
    logger.debug("Action: %s", action)
    logger.debug("Result: %s", result)
    logger.debug("Current Location: %s", engine.current_location)
    logger.debug("Player State: %s", json.dumps(engine.player_state, indent=2, ensure_ascii=False))
    
    if engine.current_location:
        location = engine.db.get_entity(engine.current_location)
        if location:
            logger.debug("Location State:")
            current_state = engine.db.get_current_world_state(engine.current_location)
            if current_state:
                logger.debug(json.dumps(json.loads(current_state.state_data), indent=2, ensure_ascii=False))
    
    input("\nPress Enter to continue...")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Interactive Text Adventure Game')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    logger.debug("Starting game with debug=%s", args.debug)
    
    # Load environment variables
    load_dotenv()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found in environment variables")
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key.")
        sys.exit(1)
    
    # Initialize game engine
    logger.debug("Initializing game engine")
    engine = GameEngine(debug=args.debug)
    
    # Print welcome message
    # print_welcome()
    
    # Main game loop
    logger.debug("Starting main game loop")
    while True:
        # clear_screen()
        
        # Show current location description
        logger.debug("Getting current location description")
        print(engine.get_current_location_description())
        print("\nWhat would you like to do?")
        
        # Get player input
        command = input("> ").strip().lower()
        logger.debug("Player command: %s", command)
        
        # Handle special commands
        if command == 'quit':
            logger.debug("Player quit the game")
            print("\nThanks for playing!")
            break
        elif command == 'save':
            logger.debug("Player requested save")
            save_name = input("Enter a name for this save: ").strip()
            save_id = engine.save_game(save_name)
            logger.debug("Game saved with ID: %d", save_id)
            print(f"\nGame saved successfully! (Save ID: {save_id})")
            continue
        elif command == 'load':
            logger.debug("Player requested load")
            try:
                save_id = int(input("Enter the save ID to load: ").strip())
                if engine.load_game(save_id):
                    logger.debug("Game loaded successfully from save ID: %d", save_id)
                    print("\nGame loaded successfully!")
                else:
                    logger.error("Failed to load game from save ID: %d", save_id)
                    print("\nError: Invalid save ID or save file corrupted.")
                continue
            except ValueError:
                logger.error("Invalid save ID format")
                print("\nError: Please enter a valid save ID (number).")
                continue
        
        # Process the command
        logger.debug("Processing player command")
        response = engine.process_command(command)
        
        # Log state in debug mode
        log_state(engine, command, response, args.debug)
        
        # Show the response
        print(f"\n{response}")

if __name__ == "__main__":
    main() 