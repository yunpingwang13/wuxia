import argparse
from game.database import Database, WorldEntity, WorldState
from game.db_init import DatabaseInitializer

def main():
    parser = argparse.ArgumentParser(description='Initialize the game database')
    parser.add_argument('--force', action='store_true', help='Force reinitialize even if locations exist')
    parser.add_argument('--clear', action='store_true', help='Clear all data from the database before initialization')
    args = parser.parse_args()

    db = Database()
    initializer = DatabaseInitializer(db)

    if args.clear:
        print("Clearing database...")
        session = db.get_session()
        try:
            # Delete all entities
            session.query(WorldEntity).delete()
            # Delete all world states
            session.query(WorldState).delete()
            session.commit()
            print("Database cleared successfully.")
        except Exception as e:
            session.rollback()
            print(f"Error clearing database: {e}")
            return

    if args.force:
        print("Forcing reinitialization...")
        initializer.initialize_world()
        print("Database reinitialized successfully.")
    else:
        print("Initializing database...")
        initializer.initialize_world()
        print("Database initialized successfully.")

if __name__ == "__main__":
    main() 