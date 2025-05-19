from typing import Dict, Any, Optional, List, Set
import json
import logging
from datetime import datetime
from .database import Database, WorldEntity
from .rag import RAGSystem
from .llm import GameLLM
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
        self.location_connections = {}  # Maps location IDs to their connections
        
        # Initialize the game world
        self._initialize_world()
        # Load location connections from database
        self._load_location_connections()
        # Initialize world state for starting location
        self._initialize_world_state()
    
    def _initialize_world(self):
        self.current_location = 1
        
        # Initialize player state
        self.player_state = {
            "inventory": [],
            "discovered_locations": [],
            "quests": [],
            "relationships": {}
        }

        # Initialize starting location with no connections
        self.location_connections[self.current_location] = {}

    def _initialize_world_state(self):
        """Initialize or update world state for the current location."""
        if not self.current_location:
            return

        session = self.db.get_session()
        current_state = self.db.get_current_world_state(self.current_location)
        
        if not current_state:
            # Create initial world state
            initial_state = {
                "visited": False,
                "visit_count": 0,
                "last_visited": None,
                "discovered_items": [],
                "environmental_changes": {},
                "interactions": {}
            }
            self.db.add_world_state(
                entity_id=self.current_location,
                state_data=json.dumps(initial_state)
            )
        else:
            # Update existing state
            state_data = json.loads(current_state.state_data)
            state_data["visited"] = True
            state_data["visit_count"] = state_data.get("visit_count", 0) + 1
            state_data["last_visited"] = str(datetime.utcnow())
            current_state.state_data = json.dumps(state_data)
            session.commit()

    def _update_world_state(self, location_id: int, updates: Dict[str, Any]):
        """Update the world state for a specific location."""
        session = self.db.get_session()
        current_state = self.db.get_current_world_state(location_id)
        
        if current_state:
            state_data = json.loads(current_state.state_data)
            state_data.update(updates)
            current_state.state_data = json.dumps(state_data)
            session.commit()
            logger.debug("Updated world state for location %d", location_id)

    def _load_location_connections(self):
        """Load all location connections from the database."""
        session = self.db.get_session()
        locations = session.query(WorldEntity).filter_by(entity_type="location").all()
        
        for location in locations:
            props = json.loads(location.properties)
            if "connections" in props:
                self.location_connections[location.id] = props["connections"]
            else:
                # Initialize empty connections for legacy data
                self.location_connections[location.id] = {}
                props["connections"] = {}
                location.properties = json.dumps(props)
                session.commit()
        
        logger.debug("Loaded %d location connections from database", len(self.location_connections))

    def _save_location_connections(self, location_id: int, connections: Dict[str, Any]):
        """Save location connections to the database."""
        session = self.db.get_session()
        location = session.query(WorldEntity).filter_by(id=location_id).first()
        if location:
            props = json.loads(location.properties)
            props["connections"] = connections
            location.properties = json.dumps(props)
            session.commit()
            logger.debug("Saved connections for location %d", location_id)

    def _get_location_by_connection(self, current_location_id: int, connection_name: str) -> Optional[WorldEntity]:
        """Find a location connected through the given connection name."""
        connections = self.location_connections.get(current_location_id, {})
        connection_data = connections.get(connection_name)
        if connection_data:
            target_id = connection_data.get("target_id")
            if target_id:
                return self.db.get_entity(target_id)
        return None

    def _create_new_location(self, connection_name: str, current_location: WorldEntity, placeholder_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a new location connected through the given connection name."""
        logger.debug("Creating new location through connection: %s", connection_name)
        
        # Convert current_location to a dictionary if it's a WorldEntity
        current_location = {
            "id": current_location.id,
            "name": current_location.name,
            "description": current_location.description,
            "properties": current_location.properties
        }
        
        # Generate a description for the new location
        location_context = {
            "current_location": current_location,
            "connection_name": connection_name,
            "is_placeholder": placeholder_id is not None
        }
        
        # Get a unique ID for the new location
        session = self.db.get_session()
        max_id = session.query(WorldEntity).order_by(WorldEntity.id.desc()).first()
        new_id = placeholder_id if placeholder_id else ((max_id.id + 1) if max_id else 1)
        logger.debug("Generated new location ID: %d", new_id)
        
        # Generate location details using LLM
        location_prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate a new location description for a wuxia-themed game.
            The location should be connected to the current location through the specified connection.
            Include details about the environment, atmosphere, and any notable features.
            
            Respond with a JSON object containing:
            {{
                "name": "location name",
                "description": "detailed description",
                "properties": {{
                    "connections": {{
                        "connection_name": {{
                            "description": "how to use this connection",
                            "target_id": null,
                            "is_placeholder": false
                        }}
                    }},
                    "items": ["list of items"],
                    "description": "detailed description"
                }}
            }}
            
            Important rules:
            1. Always include a connection back to the previous location
            2. Use descriptive names for connections (e.g., "ancient gate", "narrow passage")
            3. Include clear descriptions of how to use each connection
            4. Make sure the description mentions all available connections
            5. All unspecified connections are considered blocked
            6. You can create placeholder connections to non-existent locations
            7. For placeholder connections, set is_placeholder to true and generate a unique target_id
            8. Make sure the description hints at what might be beyond placeholder connections
            
            It is imperative that you output the response in Chinese."""),
            ("human", "{context}")
        ])
        
        location_chain = location_prompt | self.llm.llm | JsonOutputParser()
        location_data = location_chain.invoke({"context": json.dumps(location_context, indent=2)})
        logger.debug("Generated location data: %s", json.dumps(location_data, indent=2, ensure_ascii=False))
        
        # Ensure bidirectional connection exists in the properties
        current_id = current_location["id"]
        location_data["properties"]["connections"][connection_name] = {
            "target_id": current_id,
            "description": f"通向{current_location['name']}的{connection_name}",
            "is_placeholder": False
        }
        
        # Create the new location
        new_location = self.db.add_entity(
            id=new_id,
            name=location_data["name"],
            description=location_data["description"],
            entity_type="location",
            properties=json.dumps(location_data["properties"])
        )
        
        # Set up bidirectional connections
        current_id = current_location["id"]
        
        # Add connection from current location to new location
        current_connections = self.location_connections.get(current_id, {})
        current_connections[connection_name] = {
            "target_id": new_id,
            "description": f"通向{location_data['name']}的{connection_name}",
            "is_placeholder": False
        }
        self.location_connections[current_id] = current_connections
        self._save_location_connections(current_id, current_connections)
        
        # Add connection from new location to current location
        new_connections = location_data["properties"]["connections"]
        self.location_connections[new_id] = new_connections
        self._save_location_connections(new_id, new_connections)
        
        logger.debug("Created new location: %s with connections", new_location.name)
        return new_location
    
    def _get_current_context(self, player_input: str) -> Dict[str, Any]:
        # Get relevant context from RAG system
        return self.rag.get_relevant_context(
            player_input,
            self.current_location
        )

    def _get_world_state(self) -> Dict[str, Any]:
        """Get current world state including location state."""
        if not self.current_location:
            return {
                "current_location": None,
                "player_state": self.player_state,
                "location_state": None
            }

        current_state = self.db.get_current_world_state(self.current_location)
        state_data = json.loads(current_state.state_data) if current_state else {}
        
        return {
            "current_location": self.current_location,
            "player_state": self.player_state,
            "location_state": state_data
        }
    
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
            connections = self.location_connections.get(current_location.id, {})
            
            # Check if the connection exists
            if result["target"] not in connections:
                result["action"] = "blocked"
                return result
            
            # Get the connection data
            connection_data = connections[result["target"]]
            target_id = connection_data.get("target_id")
            
            if target_id:
                # Check if this is a placeholder connection
                if connection_data.get("is_placeholder", False):
                    # Create the location on demand
                    new_location = self._create_new_location(
                        result["target"],
                        current_location,
                        placeholder_id=target_id
                    )
                    result["new_state"]["location"] = new_location.id
                    result["description"] = f"你发现了一个新的地方，通向{new_location.name}。\n{new_location.description}"
                else:
                    # Visit existing location
                    target_location = self.db.get_entity(target_id)
                    if target_location:
                        # Update world state for the new location
                        self._update_world_state(target_id, {
                            "visited": True,
                            "visit_count": self.db.get_current_world_state(target_id).visit_count + 1 if self.db.get_current_world_state(target_id) else 1,
                            "last_visited": str(datetime.utcnow())
                        })
                        
                        result["new_state"]["location"] = target_id
                        result["description"] = f"你来到了{target_location.name}。\n{target_location.description}"
                    else:
                        # Location was deleted or invalid, create new one
                        new_location = self._create_new_location(result["target"], current_location)
                        result["new_state"]["location"] = new_location.id
                        result["description"] = f"你发现了一个新的地方，通向{new_location.name}。\n{new_location.description}"
            else:
                # Create new location
                new_location = self._create_new_location(result["target"], current_location)
                result["new_state"]["location"] = new_location.id
                result["description"] = f"你发现了一个新的地方，通向{new_location.name}。\n{new_location.description}"
            
            # Initialize world state for the new location
            if "location" in result["new_state"]:
                self._update_world_state(
                    result["new_state"]["location"],
                    {
                        "visited": True,
                        "visit_count": 1,
                        "last_visited": str(datetime.utcnow()),
                        "discovered_items": [],
                        "environmental_changes": {},
                        "interactions": {}
                    }
                )
        
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
                self.player_state["discovered_locations"].extend(
                    result["new_state"]["discovered"].get("locations", [])
                )
                self.player_state["discovered_items"].extend(
                    result["new_state"]["discovered"].get("items", [])
                )
                logger.debug("Updated discovered locations: %s", json.dumps(self.player_state["discovered_locations"], indent=2, ensure_ascii=False))
                logger.debug("Updated discovered items: %s", json.dumps(self.player_state["discovered_items"], indent=2, ensure_ascii=False))
            
            # Update environmental changes
            if "environmental_changes" in result["new_state"]:
                self._update_world_state(
                    self.current_location,
                    {"environmental_changes": result["new_state"]["environmental_changes"]}
                )
            
            # Update interactions
            if "interactions" in result["new_state"]:
                self._update_world_state(
                    self.current_location,
                    {"interactions": result["new_state"]["interactions"]}
                )
        
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