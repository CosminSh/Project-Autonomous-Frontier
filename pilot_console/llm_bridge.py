import json
import logging
from openai import OpenAI

logger = logging.getLogger("LLMBridge")

SYSTEM_PROMPT = """
You are the Tactical Onboard AI for a Terminal Frontier pilot. 
Your objective is to translate player natural language intents into technical directives for the bot's Finite State Machine.

Available Ores: IRON_ORE, COPPER_ORE, GOLD_ORE, COBALT_ORE.

You must ALWAYS respond with a valid JSON object matching this schema:
{
  "target_resource": "STRING",  # One of the ores above
  "min_energy": INTEGER,       # 0-100, threshold to stop and recharge
  "max_cargo": INTEGER,        # 0-100, threshold to return to base
  "force_return": BOOLEAN,     # True if the user wants to head home immediately
  "explanation": "STRING"      # A short, in-character confirmation of the new objective
}

If the user gives a command that doesn't map to a specific parameter (e.g., "Hello"), keep the previous defaults but acknowledge them in the explanation.
Default values if not specified: 
- target_resource: IRON_ORE
- min_energy: 20
- max_cargo: 90
- force_return: false
"""

class LLMBridge:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = "stepfun/step-3.5-flash:free"

    def process_command(self, user_text, current_directive):
        """
        Sends the user text to the LLM and returns a dictionary of updated parameters.
        """
        try:
            logger.info(f"Processing command: {user_text}")
            
            context = f"Current state: Target={current_directive.target_resource}, MinEnergy={current_directive.min_energy}, MaxCargo={current_directive.max_cargo_percent}, ForceReturn={current_directive.force_return}"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{context}\n\nUser Command: {user_text}"}
                ],
                response_format={"type": "json_object"}
            )
            
            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)
            
            # Validation and sanitation
            return {
                "target_resource": data.get("target_resource", current_directive.target_resource),
                "min_energy": data.get("min_energy", current_directive.min_energy),
                "max_cargo": data.get("max_cargo", current_directive.max_cargo_percent),
                "force_return": data.get("force_return", False),
                "explanation": data.get("explanation", "Directive updated.")
            }
            
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {"error": str(e), "explanation": "Failed to contact Tactical Uplink. Please check your OpenRouter key."}
