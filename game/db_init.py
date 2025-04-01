from typing import Dict, Any
import json
from datetime import datetime
from .database import Database, WorldEntity

class DatabaseInitializer:
    def __init__(self, db: Database):
        self.db = db
    
    def initialize_world(self):
        """Initialize the game world with all entities and background knowledge."""
        # Check for existing locations
        existing_locations = self._get_existing_locations()
        
        if existing_locations:
            print("Found existing locations in database. Using existing world state.")
            return existing_locations["starting_room"].id
        
        print("No existing locations found. Creating new world...")
        
        # Create locations
        locations = self._create_locations()
        
        # Create items
        items = self._create_items(locations)
        
        # Create characters
        characters = self._create_characters(locations)
        
        # Set initial world states
        self._set_initial_states(locations)
        
        # Add world knowledge
        self._add_world_knowledge(locations, items, characters)
        
        return locations["starting_room"].id
    
    def _get_existing_locations(self) -> Dict[str, Any]:
        """Get existing locations from the database."""
        session = self.db.get_session()
        locations = session.query(WorldEntity).filter_by(entity_type="location").all()
        
        if not locations:
            return {}
        
        # Convert to dictionary format
        location_dict = {}
        for location in locations:
            props = json.loads(location.properties)
            if "name" in props:
                location_dict[props["name"]] = location
        
        return location_dict
    
    def _create_locations(self) -> Dict[str, Any]:
        """Create all game locations."""
        return {
            "starting_room": self.db.add_entity(
                name="隐剑山庄山门",
                description="山门伫立于群山之间，石牌坊上刻着'剑道即心道'四个大字。石碑上铭刻着'古剑虽折，余锋犹存'。青铜孤灯幽幽闪烁，似乎隐藏着某种机关。",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["north", "east", "west"],
                    "items": ["青铜孤灯", "石匾铭文"],
                    "description": "山门伫立于群山之间，曾是江湖英雄拜师求剑之地，如今只剩青松苍翠，孤灯摇曳。"
                })
            ),
            "sanctuary": self.db.add_entity(
                name="玉剑大殿",
                description="隐剑山庄的核心之地，供奉着一柄玉色古剑'秋水寒'。剑气隐约弥漫，令人不寒而栗。白发飘然的凌霄子端坐大殿中央，目光深邃，仿佛在等待着什么。",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["south", "east"],
                    "items": ["秋水寒剑", "剑道壁画"],
                    "description": "大殿内武林先贤画像静立两侧，中央供奉着传说中的'秋水寒'剑。"
                })
            ),
            "library": self.db.add_entity(
                name="藏经阁",
                description="朱红色木门紧闭，阁内书架高耸，摆满各类武学典籍。紫金匣中封存着一卷'无名剑诀'，但剑谱表面浮现裂痕，似乎缺少了某些重要内容。",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["west", "north"],
                    "items": ["武学典籍", "无名剑诀", "灯烛"],
                    "description": "此处藏有天下剑道之秘，唯有有缘人方能得窥。"
                })
            ),
            "garden": self.db.add_entity(
                name="竹影幽庭",
                description="山庄后庭，一片寂静的竹林。湖面倒映着月光，水波不兴。池畔怪石分布奇异，似隐藏着某种剑阵玄机。",
                entity_type="location",
                properties=json.dumps({
                    "exits": ["south", "west"],
                    "items": ["剑气留痕", "石阵机关", "古旧碑文"],
                    "description": "竹林之中，剑意弥漫。此地曾是凌霄子闭关悟剑之所。"
                })
            )
        }
    
    def _create_items(self, locations: Dict[str, Any]) -> Dict[str, Any]:
        """Create all game items."""
        return {
            "青铜孤灯": self.db.add_entity(
                name="青铜孤灯",
                description="长明不熄的灯火，似乎与某种机关相连。",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["starting_room"].id,
                    "properties": ["照明", "隐藏机关"],
                    "state": "点燃"
                })
            ),
            "无名剑诀": self.db.add_entity(
                name="无名剑诀（残缺）",
                description="剑谱古旧，内容残缺，唯有补全后方能修炼。",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["library"].id,
                    "properties": ["武学", "未完整"],
                    "state": "残缺"
                })
            ),
            "秋水寒剑": self.db.add_entity(
                name="秋水寒剑",
                description="剑身如秋水，剑气无形，唯悟者得之。",
                entity_type="item",
                properties=json.dumps({
                    "location": locations["sanctuary"].id,
                    "properties": ["锋利", "剑气无形"],
                    "state": "封存"
                })
            )
        }
    
    def _create_characters(self, locations: Dict[str, Any]) -> Dict[str, Any]:
        """Create all game characters."""
        return {
            "凌霄子": self.db.add_entity(
                name="凌霄子",
                description="昔日天下第一剑客，现隐居于玉剑大殿。他将考验有缘之人，决定是否传授无名剑诀。",
                entity_type="character",
                properties=json.dumps({
                    "location": locations["sanctuary"].id,
                    "properties": ["剑道宗师", "深不可测"],
                    "state": "等待"
                })
            ),
            "黑衣人": self.db.add_entity(
                name="黑衣人",
                description="神秘江湖势力，试图阻止无名剑诀重现于世。身份成谜，或许与凌霄子昔日恩怨有关。",
                entity_type="character",
                properties=json.dumps({
                    "location": locations["library"].id,
                    "properties": ["危险", "江湖势力"],
                    "state": "潜伏"
                })
            )
        }
    
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
    
    def _add_world_knowledge(self, locations: Dict[str, Any], items: Dict[str, Any], characters: Dict[str, Any]):
        """Add all world knowledge to the database."""
        world_knowledge = [
            {
                "text": "隐剑山庄乃昔日武林圣地，掌门凌霄子创无名剑诀，剑法通神。但数十年前，他突然归隐，江湖再无其踪迹。",
                "metadata": {"type": "world_background"}
            },
            {
                "text": "凌霄子虽退隐，但仍在等待有缘人。唯有真正悟剑通心者，方可得他指点。",
                "metadata": {"type": "character_background", "character_id": characters["凌霄子"].id}
            },
            {
                "text": "无名剑诀残缺不全，传言另一半已遗失。若能补全，或可得天下无敌之剑道。",
                "metadata": {"type": "item_background", "item_id": items["无名剑诀"].id}
            },
            {
                "text": "秋水寒剑乃隐剑山庄镇派之宝，剑身如秋水，剑气无形。唯有真正悟剑之人，方能驾驭其威力。",
                "metadata": {"type": "item_background", "item_id": items["秋水寒剑"].id}
            },
            {
                "text": "竹影幽庭中的石阵机关，暗含剑道真谛。若能参悟其中玄机，或可得凌霄子指点。",
                "metadata": {"type": "location_background", "location_id": locations["garden"].id}
            }
        ]
        
        for knowledge in world_knowledge:
            self.db.add_entity(
                name=f"Knowledge_{knowledge['metadata']['type']}",
                description=knowledge["text"],
                entity_type="knowledge",
                properties=json.dumps(knowledge["metadata"])
            ) 