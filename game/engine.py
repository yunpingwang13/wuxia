from typing import Dict, Any, Optional
import json
from datetime import datetime
from .database import Database
from .rag import RAGSystem
from .llm import GameLLM

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
        """Initialize the game world with basic entities and states."""
        # Create locations
        locations = {
            "starting_room": self.db.add_entity(
                name="Ancient Temple Entrance",
                description="A grand entrance hall of an ancient temple. The walls are covered in mysterious hieroglyphs, and a single torch flickers on the wall. The air is thick with the scent of incense.",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["north", "east", "west"],
                    "items": ["torch", "hieroglyphs"],
                    "description": "A grand entrance hall of an ancient temple. The walls are covered in mysterious hieroglyphs, and a single torch flickers on the wall. The air is thick with the scent of incense."
                })
            ),
            "sanctuary": self.db.add_entity(
                name="Inner Sanctuary",
                description="A circular chamber with a domed ceiling. Ancient statues line the walls, and a mysterious altar stands in the center. The air feels charged with magical energy.",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["south", "east"],
                    "items": ["altar", "statues", "magical_energy"],
                    "description": "A circular chamber with a domed ceiling. Ancient statues line the walls, and a mysterious altar stands in the center. The air feels charged with magical energy."
                })
            ),
            "library": self.db.add_entity(
                name="Ancient Library",
                description="A vast library filled with ancient scrolls and books. The shelves are made of dark wood, and a single window lets in moonlight. A mysterious book glows on a pedestal.",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["west", "north"],
                    "items": ["scrolls", "glowing_book", "pedestal"],
                    "description": "A vast library filled with ancient scrolls and books. The shelves are made of dark wood, and a single window lets in moonlight. A mysterious book glows on a pedestal."
                })
            ),
            "garden": self.db.add_entity(
                name="Sacred Garden",
                description="An overgrown garden with exotic plants and flowers. A small fountain trickles water, and ancient stone paths wind through the vegetation. Strange insects buzz around.",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["south", "west"],
                    "items": ["fountain", "exotic_plants", "stone_paths"],
                    "description": "An overgrown garden with exotic plants and flowers. A small fountain trickles water, and ancient stone paths wind through the vegetation. Strange insects buzz around."
                })
            )
        }
        
        # Create items
        items = {
            "torch": self.db.add_entity(
                name="Ancient Torch",
                description="A brass torch mounted on the wall. The flame burns with an unnatural blue color.",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["starting_room"].id,
                    "properties": ["flammable", "magical"],
                    "state": "lit"
                })
            ),
            "hieroglyphs": self.db.add_entity(
                name="Mysterious Hieroglyphs",
                description="Ancient symbols carved into the walls. They seem to tell a story about the temple's history.",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["starting_room"].id,
                    "properties": ["readable", "historical"],
                    "state": "intact"
                })
            ),
            "glowing_book": self.db.add_entity(
                name="Book of Ancient Magic",
                description="A leather-bound book that emits a soft blue glow. The pages are filled with magical formulas.",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["library"].id,
                    "properties": ["magical", "readable"],
                    "state": "glowing"
                })
            )
        }
        
        # Create characters
        characters = {
            "guardian": self.db.add_entity(
                name="Temple Guardian",
                description="An ancient spirit that watches over the temple. It appears as a translucent figure in ceremonial robes.",
                entity_type="character",
                properties=json.dumps({
                    "location": locations["sanctuary"].id,
                    "properties": ["spiritual", "knowledgeable"],
                    "state": "watching"
                })
            )
        }
        
        # Set initial world states
        for location_id, location in locations.items():
            self.db.update_world_state(
                location.id,
                json.dumps({
                    "visited": False,
                    "state": "normal",
                    "timestamp": str(datetime.utcnow())
                })
            )
        
        # Add world knowledge to RAG system
        world_knowledge = [
            {
                "text": "The temple is an ancient place of worship and magical study. It has been abandoned for centuries but maintains its mystical properties.",
                "metadata": {"type": "world_background"}
            },
            {
                "text": "The Temple Guardian is a spiritual entity that protects the temple's secrets and guides worthy visitors.",
                "metadata": {"type": "character_background"}
            },
            {
                "text": "The Book of Ancient Magic contains powerful spells and rituals that were once practiced in the temple.",
                "metadata": {"type": "item_background"}
            }
        ]
        
        for knowledge in world_knowledge:
            self.rag.add_knowledge(
                knowledge["text"],
                metadata=knowledge["metadata"]
            )
        
        # Set starting location
        self.current_location = locations["starting_room"].id
        
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
        # print(result)
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