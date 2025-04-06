from typing import Dict, Any, Optional
import json
from datetime import datetime
from .database import Database
from .rag import RAGSystem
from .llm import GameLLM
from .db_init import DatabaseInitializer

class GameEngine:
    def __init__(self):
        self.db = Database()
        self.rag = RAGSystem(self.db)
        self.llm = GameLLM()
        self.current_location = None
        self.player_state = {}
        
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
    
    def process_command(self, player_input: str, debug: bool = False) -> str:
        """Process a player command and return the game's response."""
        # Get relevant context from RAG system
        context = self.rag.get_relevant_context(
            player_input,
            self.current_location
        )
        
        # Get current world state
        world_state = {
            "current_location": self.current_location,
            "player_state": self.player_state,
            "location_state": self.db.get_current_world_state(self.current_location).state_data if self.current_location else None
        }
        
        # Process command with LLM
        result = self.llm.process_command(player_input, context, world_state, debug)

        # Record the action
        self.db.record_action(
            player_input=player_input,
            action_type=result["action"],
            result=result["description"],
            world_state_snapshot=json.dumps(world_state)
        )
        
        if result["success"]:
            # Update location if specified
            if "new_state" in result and "location" in result["new_state"]:
                new_location_id = result["new_state"]["location"]
                if new_location_id:
                    current_state = self.db.get_current_world_state(new_location_id)
                    new_state = json.loads(current_state.state_data) if current_state else {}
                    new_state.update(new_state)
                    self.current_location = new_location_id
                    self.rag.update_world_state(new_location_id, new_state)
            
            # Update inventory if specified
            if "new_state" in result and "inventory" in result["new_state"]:
                self.player_state["inventory"] = result["new_state"]["inventory"]
            
            # Update discovered items/locations if specified
            if "new_state" in result and "discovered" in result["new_state"]:
                for item in result["new_state"]["discovered"]:
                    if item not in self.player_state["discovered"]:
                        self.player_state["discovered"].append(item)
            
            # Update RAG system with new information
            if result["description"]:
                self.rag.add_knowledge(
                    text=result["description"],
                    metadata={
                        "type": "action_result",
                        "action": result["action"],
                        "target": result.get("target", ""),
                        "timestamp": str(datetime.utcnow())
                    }
                )
        
        return result["description"]
    
    def get_current_location_description(self, debug: bool = False) -> str:
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
        
        return self.llm.generate_description(location_data, debug)
    
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