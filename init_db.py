import argparse
from game.database import Database
from game.db_init import DatabaseInitializer

def main():
    parser = argparse.ArgumentParser(description='Initialize the game database')
    parser.add_argument('--force', action='store_true', help='Force reinitialization of the database')
    args = parser.parse_args()

    db = Database()
    initializer = DatabaseInitializer(db)
    
    if args.force:
        print("Forcing database reinitialization...")
        # Here you would add code to clear existing data if needed
        # For now, we'll just proceed with initialization
    
    print("Initializing game world...")
    starting_location_id = initializer.initialize_world()
    print(f"Database initialized successfully. Starting location ID: {starting_location_id}")

if __name__ == "__main__":
    main() 