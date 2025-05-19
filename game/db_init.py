from typing import Dict, Any, Set, Tuple
import json
from datetime import datetime
from .database import Database, WorldEntity
import os
import logging
from .llm import GameLLM

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    def __init__(self, db: Database):
        logger.debug("Initializing DatabaseInitializer")
        self.db = db
        self.config = self._load_config()
        self.llm = GameLLM()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load world configuration from JSON file."""
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'world_config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def create_location(self, name: str, description: str, properties: Dict[str, Any]) -> WorldEntity:
        """Create a new location in the game world."""
        logger.debug("Creating new location: %s", name)
        
        try:
            location_data = {
                "name": name,
                "description": description,
                "entity_type": "location",
                "properties": json.dumps(properties)
            }
            
            location = self.db.add_entity(**location_data)
            logger.debug("Created location with ID: %d", location.id)
            
            return location
            
        except Exception as e:
            logger.error("Error creating location: %s", str(e))
            raise
    
    def create_item(self, name: str, description: str, properties: Dict[str, Any]) -> WorldEntity:
        """Create a new item in the game world."""
        logger.debug("Creating new item: %s", name)
        
        try:
            item_data = {
                "name": name,
                "description": description,
                "entity_type": "item",
                "properties": json.dumps(properties)
            }
            
            item = self.db.add_entity(**item_data)
            logger.debug("Created item with ID: %d", item.id)
            
            return item
            
        except Exception as e:
            logger.error("Error creating item: %s", str(e))
            raise
    
    def create_character(self, name: str, description: str, properties: Dict[str, Any]) -> WorldEntity:
        """Create a new character in the game world."""
        logger.debug("Creating new character: %s", name)
        
        try:
            character_data = {
                "name": name,
                "description": description,
                "entity_type": "character",
                "properties": json.dumps(properties)
            }
            
            character = self.db.add_entity(**character_data)
            logger.debug("Created character with ID: %d", character.id)
            
            return character
            
        except Exception as e:
            logger.error("Error creating character: %s", str(e))
            raise
    
    def _get_existing_locations(self) -> Dict[str, Any]:
        """Get existing locations from the database."""
        session = self.db.get_session()
        locations = session.query(WorldEntity).filter_by(entity_type="location").all()
        
        if not locations:
            return {}
        
        # Convert to dictionary format using the name field directly
        location_dict = {}
        for location in locations:
            location_dict[location.name] = location
        
        return location_dict
    
    def _create_locations(self) -> Dict[str, Any]:
        """Create all game locations."""
        locations = {}
        for key, config in self.config["locations"].items():
            # Create a mapping of exit directions to location IDs
            exit_mapping = {}
            for direction, target_id in config["exits"].items():
                exit_mapping[direction] = target_id
            
            locations[key] = self.db.add_entity(
                id=config["id"],
                name=config["name"],
                description=config["description"],
                entity_type="location",
                properties=json.dumps({
                    "exits": exit_mapping,
                    "items": config["items"],
                    "description": config["description"]
                })
            )
        return locations
    
    def _create_items(self, locations: Dict[str, Any]) -> Dict[str, Any]:
        """Create all game items."""
        items = {}
        for key, config in self.config["items"].items():
            items[key] = self.db.add_entity(
                id=config["id"],
                name=key,
                description=config["description"],
                entity_type="item",
                properties=json.dumps({
                    "location": config["location_id"],
                    "properties": config["properties"],
                    "state": config["state"]
                })
            )
        return items
    
    def _create_characters(self, locations: Dict[str, Any]) -> Dict[str, Any]:
        """Create all game characters."""
        characters = {}
        for key, config in self.config["characters"].items():
            characters[key] = self.db.add_entity(
                id=config["id"],
                name=key,
                description=config["description"],
                entity_type="character",
                properties=json.dumps({
                    "location": config["location_id"],
                    "properties": config["properties"],
                    "state": config["state"]
                })
            )
        return characters
    
    def _set_initial_states(self, locations: Dict[str, Any]):
        """Set initial states for all locations."""
        for location in locations.values():
            self.db.update_world_state(
                location.id,
                json.dumps({
                    "visited": False,
                    "state": "正常",
                    "timestamp": str(datetime.utcnow())
                })
            )
    
    def _add_world_knowledge(self):
        """Add all world knowledge to the database."""
        for knowledge in self.config["world_knowledge"]:
            metadata = {"type": knowledge["type"]}
            if "character_id" in knowledge:
                metadata["character_id"] = knowledge["character_id"]
            if "item_id" in knowledge:
                metadata["item_id"] = knowledge["item_id"]
            if "location_id" in knowledge:
                metadata["location_id"] = knowledge["location_id"]
                
            self.db.add_entity(
                id=knowledge["id"],
                name=f"Knowledge_{knowledge['type']}",
                description=knowledge["text"],
                entity_type="knowledge",
                properties=json.dumps(metadata)
            )
    
    def add_new_location(self, name: str, description: str, exits: Dict[str, int]) -> WorldEntity:
        """Add a new location to the world, ensuring bidirectional relationships are maintained."""
        # Get the next available ID
        session = self.db.get_session()
        max_id = session.query(WorldEntity).order_by(WorldEntity.id.desc()).first()
        new_id = (max_id.id + 1) if max_id else 1
        
        # Create the new location
        new_location = self.db.add_entity(
            id=new_id,
            name=name,
            description=description,
            entity_type="location",
            properties=json.dumps({
                "exits": exits,
                "items": [],
                "description": description
            })
        )
        
        # Update the connected locations to maintain bidirectional relationships
        for direction, target_id in exits.items():
            opposite_dir = self._get_opposite_direction(direction)
            
            # Get the target location
            target_loc = session.query(WorldEntity).get(target_id)
            if target_loc:
                # Update target location's exits
                target_props = json.loads(target_loc.properties)
                target_props["exits"][opposite_dir] = new_id
                target_loc.properties = json.dumps(target_props)
                session.add(target_loc)
        
        session.commit()
        return new_location
    
    def initialize_world(self):
        """Initialize the game world using the configuration file."""
        logger.info("Initializing game world from configuration")
        
        try:
            # Create locations
            locations = {}
            for key, config in self.config["locations"].items():
                locations[key] = self.db.add_entity(
                    id=config["id"],
                    name=config["name"],
                    description=config["description"],
                    entity_type="location",
                    properties=json.dumps(config["properties"])
                )
                logger.debug("Created location: %s (ID: %d)", config["name"], config["id"])
            
            # Create items
            items = {}
            for key, config in self.config["items"].items():
                items[key] = self.db.add_entity(
                    id=config["id"],
                    name=key,
                    description=config["description"],
                    entity_type="item",
                    properties=json.dumps({
                        "location": config["location_id"],
                        "properties": config["properties"],
                        "state": config["state"]
                    })
                )
                logger.debug("Created item: %s (ID: %d)", key, config["id"])
            
            # Create characters
            characters = {}
            for key, config in self.config["characters"].items():
                characters[key] = self.db.add_entity(
                    id=config["id"],
                    name=key,
                    description=config["description"],
                    entity_type="character",
                    properties=json.dumps({
                        "location": config["location_id"],
                        "properties": config["properties"],
                        "state": config["state"]
                    })
                )
                logger.debug("Created character: %s (ID: %d)", key, config["id"])
            
            # Add world knowledge
            for knowledge in self.config["world_knowledge"]:
                metadata = {"type": knowledge["type"]}
                if "character_id" in knowledge:
                    metadata["character_id"] = knowledge["character_id"]
                if "item_id" in knowledge:
                    metadata["item_id"] = knowledge["item_id"]
                if "location_id" in knowledge:
                    metadata["location_id"] = knowledge["location_id"]
                
                self.db.add_entity(
                    id=knowledge["id"],
                    name=f"Knowledge_{knowledge['type']}",
                    description=knowledge["text"],
                    entity_type="knowledge",
                    properties=json.dumps(metadata)
                )
                logger.debug("Added world knowledge: %s (ID: %d)", knowledge["type"], knowledge["id"])
            
            # Initialize world states for locations
            for location in locations.values():
                self.db.add_world_state(
                    entity_id=location.id,
                    state_data=json.dumps({
                        "visited": False,
                        "visit_count": 0,
                        "last_visited": None,
                        "discovered_items": [],
                        "environmental_changes": {},
                        "interactions": {}
                    })
                )
                logger.debug("Initialized world state for location: %s (ID: %d)", location.name, location.id)
            
            logger.info("World initialization completed successfully")
            return {
                "locations": locations,
                "items": items,
                "characters": characters
            }
            
        except Exception as e:
            logger.error("Error initializing world: %s", str(e))
            raise

def initialize_world():
    """Initialize the game world using the configuration file."""
    db = Database()
    initializer = DatabaseInitializer(db)
    return initializer.initialize_world() 