import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import json
from typing import List, Dict, Any
from .database import Database, WorldEntity
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, db: Database):
        logger.debug("Initializing RAG system")
        self.db = db
        self.client = chromadb.Client(Settings(
            persist_directory="./data/chroma",
            anonymized_telemetry=False
        ))
        self.collection = self.client.create_collection("world_knowledge")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings = HuggingFaceEmbeddings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.vector_store = None
        self._initialize_vector_store()
    
    def _initialize_vector_store(self):
        """Initialize the vector store with existing world knowledge."""
        logger.debug("Initializing vector store")
        session = self.db.get_session()
        try:
            # Get all world entities
            entities = session.query(WorldEntity).all()
            logger.debug("Found %d entities to index", len(entities))
            
            # Prepare documents for indexing
            documents = []
            for entity in entities:
                doc = {
                    "id": str(entity.id),
                    "name": entity.name,
                    "description": entity.description,
                    "type": entity.entity_type,
                    "properties": entity.properties
                }
                text = f"{entity.name}\n{entity.description}\n{entity.properties}"
                chunks = self.text_splitter.split_text(text)
                for i, chunk in enumerate(chunks):
                    documents.append({
                        "page_content": chunk,
                        "metadata": {
                            "entity_id": entity.id,
                            "chunk_index": i,
                            **doc
                        }
                    })
            
            if documents:
                logger.debug("Creating vector store with %d document chunks", len(documents))
                self.vector_store = FAISS.from_texts(
                    [doc["page_content"] for doc in documents],
                    self.embeddings,
                    metadatas=[doc["metadata"] for doc in documents]
                )
            else:
                logger.debug("No documents to index")
                self.vector_store = FAISS.from_texts(
                    ["Initial empty document"],
                    self.embeddings,
                    metadatas=[{"entity_id": 0, "chunk_index": 0}]
                )
        except Exception as e:
            logger.error("Error initializing vector store: %s", str(e))
            raise
        finally:
            session.close()
    
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
    
    def get_relevant_context(self, query: str, current_location_id: int = None) -> Dict[str, Any]:
        """Get relevant context for a given query."""
        logger.debug("Getting relevant context for query: %s", query)
        
        if not self.vector_store:
            logger.warning("Vector store not initialized")
            return {}
        
        try:
            # Get relevant documents
            docs = self.vector_store.similarity_search(query, k=5)
            logger.debug("Found %d relevant documents", len(docs))
            
            # Process and organize context
            context = {
                "current_location": None,
                "nearby_entities": [],
                "relevant_knowledge": []
            }
            
            # Get current location context if provided
            if current_location_id:
                location = self.db.get_entity(current_location_id)
                if location:
                    logger.debug("Found current location: %s", location.name)
                    context["current_location"] = {
                        "id": location.id,
                        "name": location.name,
                        "description": location.description,
                        "properties": json.loads(location.properties) if location.properties else {}
                    }
            
            # Process retrieved documents
            for doc in docs:
                metadata = doc.metadata
                entity_id = metadata.get("entity_id")
                
                if entity_id == current_location_id:
                    continue
                
                if entity_id:
                    entity = self.db.get_entity(entity_id)
                    if entity:
                        logger.debug("Processing entity: %s", entity.name)
                        entity_data = {
                            "id": entity.id,
                            "name": entity.name,
                            "description": entity.description,
                            "type": entity.entity_type,
                            "properties": json.loads(entity.properties) if entity.properties else {}
                        }
                        
                        if entity.entity_type == "location":
                            context["nearby_entities"].append(entity_data)
                        else:
                            context["relevant_knowledge"].append(entity_data)
            
            logger.debug("Context prepared with %d nearby entities and %d knowledge items",
                        len(context["nearby_entities"]), len(context["relevant_knowledge"]))
            return context
            
        except Exception as e:
            logger.error("Error getting relevant context: %s", str(e))
            return {}
    
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
    
    def update_knowledge(self, entity: WorldEntity):
        """Update the vector store with new or modified entity knowledge."""
        logger.debug("Updating knowledge for entity: %s", entity.name)
        
        if not self.vector_store:
            logger.warning("Vector store not initialized")
            return
        
        try:
            # Remove existing chunks for this entity
            self.vector_store.delete([str(entity.id)])
            logger.debug("Removed existing chunks for entity")
            
            # Add new chunks
            text = f"{entity.name}\n{entity.description}\n{entity.properties}"
            chunks = self.text_splitter.split_text(text)
            
            for i, chunk in enumerate(chunks):
                doc = {
                    "page_content": chunk,
                    "metadata": {
                        "entity_id": entity.id,
                        "chunk_index": i,
                        "name": entity.name,
                        "description": entity.description,
                        "type": entity.entity_type,
                        "properties": entity.properties
                    }
                }
                self.vector_store.add_texts(
                    [doc["page_content"]],
                    metadatas=[doc["metadata"]]
                )
            
            logger.debug("Added %d new chunks for entity", len(chunks))
            
        except Exception as e:
            logger.error("Error updating knowledge: %s", str(e))
            raise 