from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import json
import logging
from datetime import datetime
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Base = declarative_base()

class WorldEntity(Base):
    __tablename__ = 'world_entities'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    entity_type = Column(String(50), nullable=False)
    properties = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<WorldEntity(id={self.id}, name='{self.name}', type='{self.entity_type}')>"

class GameAction(Base):
    __tablename__ = 'game_actions'
    
    id = Column(Integer, primary_key=True)
    player_input = Column(Text, nullable=False)
    action_type = Column(String(50))
    result = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    world_state_snapshot = Column(Text)  # JSON string of world state at time of action

class WorldState(Base):
    __tablename__ = 'world_states'
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey('world_entities.id'))
    state_data = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    entity = relationship("WorldEntity", back_populates="states")
    
    def __repr__(self):
        return f"<WorldState(id={self.id}, entity_id={self.entity_id})>"

WorldEntity.states = relationship("WorldState", back_populates="entity")

class Database:
    def __init__(self, db_url: str = "sqlite:///game.db"):
        logger.debug("Initializing database with URL: %s", db_url)
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.Session()
    
    def add_entity(self, id: int = None, name: str = None, description: str = None, 
                  entity_type: str = None, properties: str = None) -> WorldEntity:
        logger.debug("Adding new entity: name=%s, type=%s", name, entity_type)
        session = self.get_session()
        try:
            entity = WorldEntity(
                id=id,
                name=name,
                description=description,
                entity_type=entity_type,
                properties=properties,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(entity)
            session.commit()
            logger.debug("Successfully added entity with ID: %d", entity.id)
            return entity
        except Exception as e:
            logger.error("Error adding entity: %s", str(e))
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_entity(self, entity_id: int) -> WorldEntity:
        logger.debug("Retrieving entity with ID: %d", entity_id)
        session = self.get_session()
        try:
            entity = session.query(WorldEntity).filter_by(id=entity_id).first()
            if entity:
                logger.debug("Found entity: %s", entity.name)
            else:
                logger.debug("Entity not found")
            return entity
        finally:
            session.close()
    
    def update_entity(self, entity_id: int, **kwargs) -> bool:
        logger.debug("Updating entity with ID: %d", entity_id)
        session = self.get_session()
        try:
            result = session.query(WorldEntity).filter_by(id=entity_id).update(kwargs)
            session.commit()
            logger.debug("Update result: %d rows affected", result)
            return result > 0
        except Exception as e:
            logger.error("Error updating entity: %s", str(e))
            session.rollback()
            raise
        finally:
            session.close()
    
    def delete_entity(self, entity_id: int) -> bool:
        logger.debug("Deleting entity with ID: %d", entity_id)
        session = self.get_session()
        try:
            result = session.query(WorldEntity).filter_by(id=entity_id).delete()
            session.commit()
            logger.debug("Delete result: %d rows affected", result)
            return result > 0
        except Exception as e:
            logger.error("Error deleting entity: %s", str(e))
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_current_world_state(self, entity_id: int) -> WorldState:
        logger.debug("Getting current world state for entity ID: %d", entity_id)
        session = self.get_session()
        try:
            state = session.query(WorldState).filter_by(entity_id=entity_id).order_by(WorldState.created_at.desc()).first()
            if state:
                logger.debug("Found world state")
            else:
                logger.debug("No world state found")
            return state
        finally:
            session.close()
    
    def add_world_state(self, entity_id: int, state_data: str) -> WorldState:
        logger.debug("Adding new world state for entity ID: %d", entity_id)
        session = self.get_session()
        try:
            state = WorldState(entity_id=entity_id, state_data=state_data, created_at=datetime.utcnow())
            session.add(state)
            session.commit()
            logger.debug("Successfully added world state with ID: %d", state.id)
            return state
        except Exception as e:
            logger.error("Error adding world state: %s", str(e))
            session.rollback()
            raise
        finally:
            session.close()
    
    def record_action(self, player_input, action_type, result, world_state_snapshot) -> GameAction:
        session = self.get_session()
        action = GameAction(
            player_input=player_input,
            action_type=action_type,
            result=result,
            world_state_snapshot=world_state_snapshot
        )
        session.add(action)
        session.commit()
        session.refresh(action)  # <--- This ensures the entity remains attached
        session.close() 
        return action
    
    def get_recent_actions(self, limit=10) -> List[GameAction]:
        session = self.get_session()
        return session.query(GameAction).order_by(GameAction.timestamp.desc()).limit(limit).all() 