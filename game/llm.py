from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate, MessagesPlaceholder
from langchain.chains import LLMChain
from typing import Dict, Any, List
import json
import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence
from langchain_community.llms import LlamaCpp

load_dotenv()

class GameLLM:
    def __init__(self, model_path: str = None):
        """Initialize the LLM interface with either a local or OpenAI model."""
        if model_path:
            # Use local model
            self.llm = LlamaCpp(
                model_path=model_path,
                temperature=0.7,
                max_tokens=2000,
                top_p=1,
                n_ctx=2048,
                verbose=True
            )
        else:
            # Use OpenAI model
            self.llm = ChatOpenAI(
                temperature=0.7,
                model_name="gpt-4o-mini"
            )
        
        # Define the action prompt template
        self.action_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a game master for a text-based adventure game. 
            Your task is to interpret player actions and determine their outcomes.

            Available actions:
            - move: Move to a different location
            - examine: Look at an object or location
            - take: Pick up an item
            - use: Use an item
            - talk: Interact with a character
            - inventory: Check player's inventory
            
            Respond with a JSON object containing:
            {{
                "action": "one of the available actions",
                "target": "the target of the action (if applicable)",
                "description": "a detailed description of what happens",
                "success": true/false,
                "new_state": {{
                    "location": "new location if moved",
                    "inventory": ["list of items if changed"],
                    "discovered": ["new locations or items if discovered"]
                }}
            }}

            It is imperative that you output the response in Chinese.
            """),
            ("human", "{input}")
        ])
        
        # Create the action chain using the new syntax
        self.action_chain = self.action_prompt | self.llm | JsonOutputParser()
    
    def process_command(self, player_input: str, context: Dict[str, Any], world_state: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
        """Process a player command and return the game's response."""
        try:
            # Format the input with context, including exits
            current_location = context.get("location_context", {})
            location_props = json.loads(current_location.get("properties", "{}"))
            exits = location_props.get("exits", {})
            
            if debug:
                print("Context:", context)
                print("Current Location:", current_location)
                print("Location Properties:", location_props)
                print("Exits:", exits)

            # Format exits for readability
            formatted_exits = {direction: f"{target_id}" for direction, target_id in exits.items()}
            
            # Create enhanced context with exits
            enhanced_context = {
                **context,
                "current_location_exits": formatted_exits,
                "world_state": world_state
            }
            
            # Format the input with enhanced context
            input_data = {
                "input": f"Player command: {player_input}\nCurrent context: {json.dumps(enhanced_context, indent=2)}"
            }
            
            # Print input to LLM if in debug mode
            if debug:
                print("Input to LLM:")
                print("Player Input:", player_input)
                print("Context:", enhanced_context)
            
            # Run the chain
            result = self.action_chain.invoke(input_data)
            
            if debug:
                print("Output from LLM:")
                print(result)
            
            return result
            
        except Exception as e:
            return {
                "action": "error",
                "description": f"Error processing command: {str(e)}",
                "success": False,
                "new_state": {}
            }
    
    def generate_description(self, entity: Dict[str, Any], debug: bool = False) -> str:
        """Generate a natural language description of an entity or situation."""
        description_prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate a vivid, engaging description of the following game entity or situation.
            The description should be detailed and immersive, suitable for a text adventure game.
            
            It is imperative that you output the response in Chinese."""),
            ("human", "{entity}")
        ])
        
        if debug:
            print("Input to LLM:")
            print("Entity:", entity)
        
        description_chain = description_prompt | self.llm
        result = description_chain.invoke({"entity": json.dumps(entity, indent=2)})
        
        if debug:
            print("Output from LLM:")
            print(result)
            
        return result.content