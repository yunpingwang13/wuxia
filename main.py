from game.engine import GameEngine
import sys
import os
from dotenv import load_dotenv

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

def main():
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
    print_welcome()
    
    # Main game loop
    while True:        
        # Show current location description
        print(engine.get_current_location_description())
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
            input("\nPress Enter to continue...")
            continue
        elif command == 'load':
            try:
                save_id = int(input("Enter the save ID to load: ").strip())
                if engine.load_game(save_id):
                    print("\nGame loaded successfully!")
                else:
                    print("\nError: Invalid save ID or save file corrupted.")
                input("\nPress Enter to continue...")
                continue
            except ValueError:
                print("\nError: Please enter a valid save ID (number).")
                input("\nPress Enter to continue...")
                continue
        
        # Process the command
        response = engine.process_command(command)
        
        # Show the response
        print(f"\n{response}")

if __name__ == "__main__":
    main() 