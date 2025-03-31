from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from typing import Dict, Any
import json
import os
from dotenv import load_dotenv

load_dotenv()

class GameLLM:
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.7,
            model_name="gpt-4o-mini"
        )
        
        self.action_prompt = PromptTemplate(
            input_variables=["player_input", "context", "world_state"],
            template="""
            You are the game engine for an interactive text adventure. The player has entered the following command:
            {player_input}
            
            Here is the relevant context about the world and recent events:
            {context}
            
            Current world state:
            {world_state}
            
            Based on this information, determine:
            1. What action should be taken
            2. What changes should be made to the world state
            3. What response should be given to the player
            
            Format your response as a JSON object with the following structure:
            {{
                "action": "string describing the action",
                "world_state_changes": {{}},
                "player_response": "string response to the player"
            }}

            Do not include any other text in your response.
            """
        )
        
        self.action_chain = LLMChain(
            llm=self.llm,
            prompt=self.action_prompt
        )
    
    def process_command(self, player_input: str, context: Dict[str, Any], world_state: Dict[str, Any]) -> Dict[str, Any]:
        """Process a player command and return the game's response."""
        # Format context for the prompt
        # print(context)
        context_str = json.dumps(context, indent=2)
        world_state_str = json.dumps(world_state, indent=2)
        
        # Generate response using the LLM
        response = self.action_chain.invoke(
            {"player_input": player_input,
            "context": context_str,
            "world_state": world_state_str
        })
        
        try:
            # Parse the response as JSON
            # print(response)
            # print(response["text"])
            result = json.loads(response["text"])
            return result
        except json.JSONDecodeError:
            # Fallback response if JSON parsing fails
            return {
                "action": "error",
                "world_state_changes": {},
                "player_response": "I'm sorry, I encountered an error processing your command. Please try again."
            }
    
    def generate_description(self, entity: Dict[str, Any]) -> str:
        """Generate a natural language description of an entity or situation."""
        description_prompt = PromptTemplate(
            input_variables=["entity"],
            template="""
            Generate a vivid, engaging description of the following game entity or situation:
            {entity}
            
            The description should be detailed and immersive, suitable for a text adventure game.
            """
        )
        
        description_chain = LLMChain(
            llm=self.llm,
            prompt=description_prompt
        )
        
        return description_chain.invoke({"entity": json.dumps(entity, indent=2)})["text"]