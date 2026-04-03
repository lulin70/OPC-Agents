from typing import Dict, List, Optional, Any

class PatternAnalyzer:
    """Pattern-based memory analyzer."""
    
    def __init__(self):
        """Initialize the pattern analyzer."""
        # Initialize counters for pattern detection
        self.message_history = []
        self.task_patterns = {}
    
    def analyze(self, message: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Analyze a message for patterns.
        
        Args:
            message: The message to analyze.
            context: Optional context for the message.
            
        Returns:
            A list of detected patterns.
        """
        patterns = []
        
        # Add current message to history
        self.message_history.append(message)
        
        # Limit history size
        if len(self.message_history) > 10:
            self.message_history.pop(0)
        
        # Detect task patterns
        task_pattern = self._detect_task_pattern(message)
        if task_pattern:
            patterns.append(task_pattern)
        
        # Detect decision patterns
        decision_pattern = self._detect_decision_pattern(message)
        if decision_pattern:
            patterns.append(decision_pattern)
        
        # Detect sentiment patterns
        sentiment_pattern = self._detect_sentiment_pattern(message)
        if sentiment_pattern:
            patterns.append(sentiment_pattern)
        
        return patterns
    
    def _detect_task_pattern(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect task patterns.
        
        Args:
            message: The message to analyze.
            
        Returns:
            A task pattern if detected, None otherwise.
        """
        # Check for repeated task requests
        task_keywords = ['需要', '帮忙', '做', '写', '改', '查', '找', '创建', '生成']
        
        for keyword in task_keywords:
            if keyword in message:
                # Extract task content
                task_content = message
                
                # Check if this task has been requested before
                task_hash = hash(task_content)
                if task_hash in self.task_patterns:
                    self.task_patterns[task_hash] += 1
                    if self.task_patterns[task_hash] >= 2:
                        # This is a repeated task
                        return {
                            'memory_type': 'task_pattern',
                            'tier': 3,
                            'content': task_content,
                            'confidence': 0.8,
                            'source': 'pattern:task_repeat',
                            'description': '重复任务模式'
                        }
                else:
                    self.task_patterns[task_hash] = 1
        
        return None
    
    def _detect_decision_pattern(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect decision patterns.
        
        Args:
            message: The message to analyze.
            
        Returns:
            A decision pattern if detected, None otherwise.
        """
        # Check for decision keywords
        decision_keywords = ['决定', '确认', '同意', '批准', '通过', '好的', '行', '可以', '没问题']
        
        for keyword in decision_keywords:
            if keyword in message:
                # Check if there's a previous message that contains a proposal
                if len(self.message_history) >= 2:
                    previous_message = self.message_history[-2]
                    return {
                        'memory_type': 'decision',
                        'tier': 3,
                        'content': f"决定: {message}. 基于: {previous_message}",
                        'confidence': 0.7,
                        'source': 'pattern:decision',
                        'description': '决策模式'
                    }
        
        return None
    
    def _detect_sentiment_pattern(self, message: str) -> Optional[Dict[str, Any]]:
        """Detect sentiment patterns.
        
        Args:
            message: The message to analyze.
            
        Returns:
            A sentiment pattern if detected, None otherwise.
        """
        # Check for sentiment keywords
        positive_keywords = ['喜欢', '爱', '好', '棒', '优秀', '满意', '推荐', '赞']
        negative_keywords = ['讨厌', '不喜欢', '差', '糟糕', '失望', '不满', '反感', '垃圾']
        
        for keyword in positive_keywords:
            if keyword in message:
                return {
                    'memory_type': 'sentiment_marker',
                    'tier': 3,
                    'content': f"正面情感: {message}",
                    'confidence': 0.6,
                    'source': 'pattern:positive_sentiment',
                    'description': '正面情感模式'
                }
        
        for keyword in negative_keywords:
            if keyword in message:
                return {
                    'memory_type': 'sentiment_marker',
                    'tier': 3,
                    'content': f"负面情感: {message}",
                    'confidence': 0.6,
                    'source': 'pattern:negative_sentiment',
                    'description': '负面情感模式'
                }
        
        return None
    
    def clear_history(self):
        """Clear the message history."""
        self.message_history = []
        self.task_patterns = {}
