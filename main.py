from game.engine import GameEngine
import sys
import os
import json
from dotenv import load_dotenv
import argparse

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_welcome():
    clear_screen()
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
    
    print("\n=== DEBUG: Game State ===")
    print(f"Action: {action}")
    print(f"Result: {result}")
    print(f"Current Location: {engine.current_location}")
    print("Player State:")
    print(json.dumps(engine.player_state, indent=2, ensure_ascii=False))
    
    if engine.current_location:
        location = engine.db.get_entity(engine.current_location)
        if location:
            print("\nLocation State:")
            current_state = engine.db.get_current_world_state(engine.current_location)
            if current_state:
                print(json.dumps(json.loads(current_state.state_data), indent=2, ensure_ascii=False))
    
    print("\nPress Enter to continue...")
    input()

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Interactive Text Adventure Game')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key.")
        sys.exit(1)
    
    # Initialize game engine
    engine = GameEngine()
    
    # Print welcome message
    # print_welcome()
    
    # Main game loop
    while True:
        # clear_screen()
        
        # Show current location description
        print(engine.get_current_location_description(args.debug))
        print("\nWhat would you like to do?")
        
        # Get player input
        command = input("> ").strip().lower()
        
        # Handle special commands
        if command == 'quit':
            print("\nThanks for playing!")
            break
        elif command == 'save':
            save_name = input("Enter a name for this save: ").strip()
            save_id = engine.save_game(save_name)
            print(f"\nGame saved successfully! (Save ID: {save_id})")
            continue
        elif command == 'load':
            try:
                save_id = int(input("Enter the save ID to load: ").strip())
                if engine.load_game(save_id):
                    print("\nGame loaded successfully!")
                else:
                    print("\nError: Invalid save ID or save file corrupted.")
                continue
            except ValueError:
                print("\nError: Please enter a valid save ID (number).")
                continue
        
        # Process the command
        response = engine.process_command(command, args.debug)
        
        # Log state in debug mode
        log_state(engine, command, response, args.debug)
        
        # Show the response
        print(f"\n{response}")

if __name__ == "__main__":
    main() 