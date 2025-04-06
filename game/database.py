from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class WorldEntity(Base):
    __tablename__ = 'world_entities'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    entity_type = Column(String(50))  # location, item, character, etc.
    properties = Column(Text)  # JSON string of additional properties
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    state_data = Column(Text)  # JSON string of current state
    timestamp = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self, db_url="sqlite:///game.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.Session()
    
    def add_entity(self, id, name, description, entity_type, properties=None):
        session = self.get_session()
        entity = WorldEntity(
            id=id,
            name=name,
            description=description,
            entity_type=entity_type,
            properties=properties
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)  # <--- This ensures the entity remains attached
        session.close()  # <--- Explicitly close the session
        return entity
    
    def record_action(self, player_input, action_type, result, world_state_snapshot):
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
    
    def update_world_state(self, entity_id, state_data):
        session = self.get_session()
        state = WorldState(
            entity_id=entity_id,
            state_data=state_data
        )
        session.add(state)
        session.commit()
        session.refresh(state)  # <--- This ensures the entity remains attached
        session.close()
        return state
    
    def get_entity(self, entity_id):
        session = self.get_session()
        return session.query(WorldEntity).filter_by(id=entity_id).first()
    
    def get_recent_actions(self, limit=10):
        session = self.get_session()
        return session.query(GameAction).order_by(GameAction.timestamp.desc()).limit(limit).all()
    
    def get_current_world_state(self, entity_id):
        session = self.get_session()
        return session.query(WorldState).filter_by(entity_id=entity_id).order_by(WorldState.timestamp.desc()).first() 