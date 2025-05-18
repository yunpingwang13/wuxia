from typing import Dict, Any, Optional
import json
import logging
from datetime import datetime
from .database import Database, WorldEntity
from .rag import RAGSystem
from .llm import GameLLM
from .db_init import DatabaseInitializer
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GameEngine:
    def __init__(self, debug: bool = False):
        self.db = Database()
        self.rag = RAGSystem(self.db)
        self.llm = GameLLM(debug=debug)
        self.current_location = None
        self.player_state = {}
        self.debug = debug
        
        # Initialize the game world
        self._initialize_world()
    
    def _initialize_world(self):
        """Initialize the game world using the database initializer."""
        initializer = DatabaseInitializer(self.db)
        self.current_location = initializer.initialize_world()
        
        # Initialize player state
        self.player_state = {
            "inventory": [],
            "discovered_locations": [],
            "quests": [],
            "relationships": {}
        }

    def _get_current_context(self, player_input: str) -> Dict[str, Any]:
        # Get relevant context from RAG system
        return self.rag.get_relevant_context(
            player_input,
            self.current_location
        )

    def _get_world_state(self) -> Dict[str, Any]:
        # Get current world state
        return {
            "current_location": self.current_location,
            "player_state": self.player_state,
            "location_state": self.db.get_current_world_state(self.current_location).state_data if self.current_location else None
        } 
    
    def _create_new_location(self, direction: str, current_location: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new location in the given direction from the current location."""
        logger.debug("Creating new location in direction: %s", direction)
        
        # Generate a description for the new location
        location_context = {
            "current_location": current_location,
            "direction": direction
        }
        
        # Get a unique ID for the new location
        session = self.db.get_session()
        max_id = session.query(WorldEntity).order_by(WorldEntity.id.desc()).first()
        new_id = (max_id.id + 1) if max_id else 1
        logger.debug("Generated new location ID: %d", new_id)
        
        # Generate location details using LLM
        location_prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate a new location description for a wuxia-themed game.
            The location should be connected to the current location in the specified direction.
            Include details about the environment, atmosphere, and any notable features.
            
            Respond with a JSON object containing:
            {
                "name": "location name",
                "description": "detailed description",
                "exits": {
                    "direction": "target_location_id"
                },
                "items": ["list of items present"],
                "properties": {
                    "exits": {
                        "direction": target_id
                    },
                    "items": ["list of items"],
                    "description": "detailed description"
                }
            }
            
            It is imperative that you output the response in Chinese."""),
            ("human", "{context}")
        ])
        
        location_chain = location_prompt | self.llm.llm | JsonOutputParser()
        location_data = location_chain.invoke({"context": json.dumps(location_context, indent=2)})
        logger.debug("Generated location data: %s", json.dumps(location_data, indent=2, ensure_ascii=False))
        
        # Create the new location
        new_location = self.db.add_entity(
            id=new_id,
            name=location_data["name"],
            description=location_data["description"],
            entity_type="location",
            properties=json.dumps(location_data["properties"])
        )
        logger.debug("Created new location: %s", new_location.name)
        
        # Update current location's exits
        current_props = json.loads(current_location["properties"])
        current_props["exits"][direction] = new_id
        current_location["properties"] = json.dumps(current_props)
        
        # Update the location in the database
        session.query(WorldEntity).filter_by(id=current_location["id"]).update(
            {"properties": current_location["properties"]}
        )
        session.commit()
        logger.debug("Updated current location exits to include new location")
        
        return new_location
    
    def _get_current_location(self) -> WorldEntity:
        return self.db.get_entity(self.current_location)

    def process_command(self, command: str) -> Dict[str, Any]:
        """Process a player command and return the game's response."""
        logger.debug("Processing command: %s", command)
        
        # Get current context
        context = self._get_current_context(command)
        world_state = self._get_world_state()
        logger.debug("Current context: %s", json.dumps(context, indent=2, ensure_ascii=False))
        logger.debug("World state: %s", json.dumps(world_state, indent=2, ensure_ascii=False))
        
        # Process the command using LLM
        result = self.llm.process_command(command, context, world_state)
        logger.debug("LLM result: %s", json.dumps(result, indent=2, ensure_ascii=False))
        
        # Handle movement to new locations
        if result["action"] == "move":
            current_location = self._get_current_location()
            current_props = json.loads(current_location.properties)
            exits = current_props.get("exits", {})
            
            logger.debug("Current location: %s", current_location.name)
            logger.debug("Available exits: %s", json.dumps(exits, indent=2, ensure_ascii=False))
            
            # If the direction is not in the exits, create a new location
            if result["target"] not in exits:
                logger.debug("Creating new location in direction: %s", result["target"])
                new_location = self._create_new_location(result["target"], current_location)
                result["new_state"]["location"] = new_location.id
                result["description"] = f"你发现了一条新的道路，通向{new_location.name}。\n{new_location.description}"
        
        # Update world state based on the result
        if result["new_state"]:
            logger.debug("Updating world state with: %s", json.dumps(result["new_state"], indent=2, ensure_ascii=False))
            
            # Update current location if changed
            if "location" in result["new_state"]:
                self.current_location = result["new_state"]["location"]
                logger.debug("Updated current location to: %d", self.current_location)
            
            # Update player state
            if "inventory" in result["new_state"]:
                self.player_state["inventory"] = result["new_state"]["inventory"]
                logger.debug("Updated inventory: %s", json.dumps(self.player_state["inventory"], indent=2, ensure_ascii=False))
            
            # Update discovered locations and items
            if "discovered" in result["new_state"]:
                self.player_state["discovered_locations"].update(
                    result["new_state"]["discovered"].get("locations", [])
                )
                self.player_state["discovered_items"].update(
                    result["new_state"]["discovered"].get("items", [])
                )
                logger.debug("Updated discovered locations: %s", json.dumps(self.player_state["discovered_locations"], indent=2, ensure_ascii=False))
                logger.debug("Updated discovered items: %s", json.dumps(self.player_state["discovered_items"], indent=2, ensure_ascii=False))
        
        return result
    
    def get_current_location_description(self) -> str:
        """Get a description of the current location."""
        if not self.current_location:
            return "You are nowhere."
        
        location = self.db.get_entity(self.current_location)
        if not location:
            return "You are in an unknown location."
        
        current_state = self.db.get_current_world_state(self.current_location)
        state_data = json.loads(current_state.state_data) if current_state else {}
        
        # Generate a fresh description using the LLM
        location_data = {
            "name": location.name,
            "description": location.description,
            "properties": json.loads(location.properties),
            "current_state": state_data
        }
        
        return self.llm.generate_description(location_data)
    
    def save_game(self, save_name: str):
        """Save the current game state."""
        save_data = {
            "current_location": self.current_location,
            "player_state": self.player_state,
            "timestamp": str(datetime.utcnow())
        }
        
        # Save to database
        save_entity = self.db.add_entity(
            name=f"Save_{save_name}",
            description="Game save state",
            entity_type="save",
            properties=json.dumps(save_data)
        )
        
        return save_entity.id
    
    def load_game(self, save_id: int) -> bool:
        """Load a saved game state."""
        save_entity = self.db.get_entity(save_id)
        if not save_entity or save_entity.entity_type != "save":
            return False
        
        save_data = json.loads(save_entity.properties)
        self.current_location = save_data["current_location"]
        self.player_state = save_data["player_state"]
        
        return True 