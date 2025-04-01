import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json
from typing import List, Dict, Any
from .database import Database

class RAGSystem:
    def __init__(self, db: Database):
        self.db = db
        self.client = chromadb.Client(Settings(
            persist_directory="./data/chroma",
            anonymized_telemetry=False
        ))
        self.collection = self.client.create_collection("world_knowledge")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def _encode_text(self, text: str) -> List[float]:
        return self.encoder.encode(text).tolist()
    
    def add_knowledge(self, text: str, metadata: Dict[str, Any] = None):
        """Add new knowledge to the RAG system."""
        embedding = self._encode_text(text)
        self.collection.add(
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata] if metadata else None,
            ids=[f"doc_{len(self.collection.get()['ids']) + 1}"]
        )
    
    def query_knowledge(self, query: str) -> List[Dict[str, Any]]:
        """Query the knowledge base for relevant information."""
        query_embedding = self._encode_text(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=3
        )
        
        return [
            {
                "text": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )
        ]
    
    def get_relevant_context(self, player_input: str, current_location: str = None) -> Dict[str, Any]:
        """Get relevant context for the current game state."""
        # Get recent actions for temporal context
        recent_actions = [json.dumps({
            "id": game_action.id,
            "player_input": game_action.player_input,
            "action_type": game_action.action_type,
            "result": game_action.result,
            "timestamp": game_action.timestamp.isoformat(),
            "world_state_snapshot": json.loads(game_action.world_state_snapshot) if game_action.world_state_snapshot else None
        }) for game_action in self.db.get_recent_actions(limit=5)]
        
        # Query for relevant world knowledge
        relevant_knowledge = self.query_knowledge(player_input)
        
        # Get current location context if available
        location_context = None
        if current_location:
            location_entity = self.db.get_entity(current_location)
            if location_entity:
                location_state = self.db.get_current_world_state(current_location)
                location_context = {
                    "name": location_entity.name,
                    "description": location_entity.description,
                    "current_state": location_state.state_data if location_state else None
                }
        
        return {
            "recent_actions": recent_actions,
            "relevant_knowledge": relevant_knowledge,
            "location_context": location_context
        }
    
    def update_world_state(self, entity_id: int, new_state: Dict[str, Any]):
        """Update the world state and add it to the knowledge base."""
        entity = self.db.get_entity(entity_id)
        if entity:
            # Update the database
            self.db.update_world_state(entity_id, json.dumps(new_state))
            
            # Add to RAG system
            state_text = f"{entity.name} is now in the following state: {json.dumps(new_state)}"
            self.add_knowledge(
                state_text,
                metadata={
                    "entity_id": entity_id,
                    "entity_type": entity.entity_type,
                    "timestamp": str(new_state.get("timestamp", ""))
                }
            ) 