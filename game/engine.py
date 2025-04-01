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
    
    def process_command(self, player_input: str) -> str:
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
        result = self.llm.process_command(player_input, context, world_state)
        
        # Record the action
        self.db.record_action(
            player_input=player_input,
            action_type=result["action"],
            result=result["player_response"],
            world_state_snapshot=json.dumps(world_state)
        )
        
        # Update world state based on changes
        if result["world_state_changes"]:
            for entity_id, changes in result["world_state_changes"].items():
                current_state = self.db.get_current_world_state(entity_id)
                new_state = json.loads(current_state.state_data) if current_state else {}
                new_state.update(new_state)
                if entity_id == "current_location":
                    self.current_location = changes
                self.rag.update_world_state(entity_id, new_state)
        
        return result["player_response"]
    
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