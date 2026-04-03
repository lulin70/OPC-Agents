import re
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.helpers import extract_content

class RuleMatcher:
    """Rule-based memory matcher."""
    
    def __init__(self, rules: List[Dict[str, Any]]):
        """Initialize the rule matcher.
        
        Args:
            rules: List of rules to use for matching.
        """
        self.rules = rules
    
    def match(self, message: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Match rules against a message.
        
        Args:
            message: The message to match against.
            context: Optional context for the message.
            
        Returns:
            A list of matching memories.
        """
        matches = []
        
        for rule in self.rules:
            pattern = rule.get('pattern')
            memory_type = rule.get('memory_type')
            tier = rule.get('tier')
            action = rule.get('action')
            description = rule.get('description')
            
            # Check if the pattern matches the message
            if re.search(pattern, message):
                # Extract content based on action
                content = extract_content(message, pattern, action)
                
                if content:
                    match = {
                        'memory_type': memory_type,
                        'tier': tier,
                        'content': content,
                        'confidence': 1.0,  # Rule-based matches have high confidence
                        'source': f'rule:{pattern}',
                        'description': description
                    }
                    matches.append(match)
        
        return matches
    
    def add_rule(self, rule: Dict[str, Any]):
        """Add a new rule to the matcher.
        
        Args:
            rule: The rule to add.
        """
        self.rules.append(rule)
    
    def remove_rule(self, pattern: str):
        """Remove a rule from the matcher.
        
        Args:
            pattern: The pattern of the rule to remove.
        """
        self.rules = [rule for rule in self.rules if rule.get('pattern') != pattern]
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all rules.
        
        Returns:
            List of rules.
        """
        return self.rules
