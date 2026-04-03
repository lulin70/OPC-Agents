import json
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.logger import logger

class SemanticClassifier:
    """Semantic memory classifier using LLM."""
    
    def __init__(self, llm_enabled: bool = False, api_key: str = None):
        """Initialize the semantic classifier.
        
        Args:
            llm_enabled: Whether to enable LLM-based classification.
            api_key: API key for the LLM service.
        """
        self.llm_enabled = llm_enabled
        self.api_key = api_key
    
    def classify(self, message: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Classify a message using semantic analysis.
        
        Args:
            message: The message to classify.
            context: Optional context for the message.
            
        Returns:
            A list of classified memories.
        """
        if not self.llm_enabled:
            # Return empty list if LLM is not enabled
            return []
        
        try:
            # Generate prompt
            prompt = self._generate_prompt(message, context)
            
            # Call LLM API
            response = self._call_llm(prompt)
            
            # Parse response
            classified_memories = self._parse_response(response)
            
            return classified_memories
        except Exception as e:
            logger.error(f"Error in semantic classification: {e}", exc_info=True)
            return []
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API.
        
        Args:
            prompt: The prompt to send to the LLM.
            
        Returns:
            The LLM's response.
        """
        import requests
        
        # Use GLM API
        api_url = "https://open.bigmodel.cn/api/messages"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": "glm-4-plus",
            "messages": [
                {"role": "system", "content": "You are a memory classification assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        return response.json()['choices'][0]['message']['content']
    
    def _parse_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse the LLM response.
        
        Args:
            response: The LLM's response.
            
        Returns:
            A list of classified memories.
        """
        import json
        
        try:
            # Parse JSON response
            data = json.loads(response)
            
            if data.get('has_memory'):
                memory = {
                    'memory_type': data.get('memory_type'),
                    'tier': data.get('tier'),
                    'content': data.get('content'),
                    'confidence': data.get('confidence', 0.0),
                    'source': 'semantic:llm',
                    'description': 'LLM semantic classification'
                }
                return [memory]
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error processing LLM response: {e}", exc_info=True)
        
        return []
    
    def _generate_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a prompt for the LLM.
        
        Args:
            message: The message to classify.
            context: Optional context for the message.
            
        Returns:
            The generated prompt.
        """
        prompt = f"""
你是一个记忆分类器。分析以下对话片段，判断是否有值得长期记忆的信息。

记忆类型包括：
- user_preference: 用户表达的偏好或习惯
- fact_declaration: 用户陈述的客观事实
- decision: 达成的明确决定或结论
- relationship: 涉及人物、团队、组织之间的关系
- task_pattern: 反复出现的任务类型
- sentiment_marker: 用户对某话题的情感倾向
- correction: 用户对之前输出的纠正

如果对话中没有值得记忆的信息，返回空。

当前对话：
{message}

已知的用户记忆：
{json.dumps(context.get('existing_memories', []), ensure_ascii=False) if context else '[]'}

请以JSON格式输出，包含以下字段：
- has_memory: boolean
- memory_type: string (枚举值)
- content: string (记忆内容，简洁准确)
- tier: int (2=程序性记忆, 3=情节记忆, 4=语义记忆)
- confidence: float (0.0-1.0)
- reasoning: string (简要判断理由)
"""
        return prompt
