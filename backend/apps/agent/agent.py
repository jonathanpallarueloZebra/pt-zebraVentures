import json
import os
from openai import OpenAI
from .tools.date_tool import DATE_TOOLS


class Agent:
    """AI Agent — uses AGENT_MODEL from env."""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))
        self.model = os.getenv('AGENT_MODEL')
        if not self.model:
            raise ValueError('AGENT_MODEL not set in environment')
        self.system_prompt = os.getenv('AGENT_PERSONALITY', 'Eres un asistente útil y profesional.')
        all_tools = list(DATE_TOOLS)
        self.tools = self._build_tools(all_tools)
        self.tool_functions = {t['name']: t['function'] for t in all_tools}
        self.conversation_history = []

    def _build_tools(self, tool_list):
        return [
            {
                'type': 'function',
                'function': {
                    'name': tool['name'],
                    'description': tool['description'],
                    'parameters': tool.get('parameters', {'type': 'object', 'properties': {}}),
                },
            }
            for tool in tool_list
        ]

    def chat(self, message: str) -> str:
        self.conversation_history.append({'role': 'user', 'content': message})

        messages = [
            {'role': 'system', 'content': self.system_prompt},
            *self.conversation_history,
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
        )

        assistant_message = response.choices[0].message

        # Handle tool calls
        while assistant_message.tool_calls:
            self.conversation_history.append(assistant_message)
            for tool_call in assistant_message.tool_calls:
                fn = self.tool_functions.get(tool_call.function.name)
                if fn:
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    result = fn(**args)
                else:
                    result = 'Tool not found'
                self.conversation_history.append({
                    'role': 'tool',
                    'tool_call_id': tool_call.id,
                    'content': str(result),
                })

            messages = [
                {'role': 'system', 'content': self.system_prompt},
                *self.conversation_history,
            ]
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
            )
            assistant_message = response.choices[0].message

        self.conversation_history.append(
            {'role': 'assistant', 'content': assistant_message.content}
        )
        return assistant_message.content
