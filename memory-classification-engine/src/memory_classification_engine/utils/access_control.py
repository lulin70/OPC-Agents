from typing import Dict, List, Optional

class AccessControlManager:
    """Access control manager for memory classification engine."""
    
    def __init__(self):
        """Initialize the access control manager."""
        self.users = {}
        self.roles = {
            'admin': ['read', 'write', 'delete', 'admin'],
            'user': ['read', 'write'],
            'guest': ['read']
        }
    
    def add_user(self, user_id: str, role: str = 'user'):
        """Add a user with specified role.
        
        Args:
            user_id: User ID.
            role: User role.
        """
        if role not in self.roles:
            raise ValueError(f"Invalid role: {role}")
        
        self.users[user_id] = role
    
    def has_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission.
        
        Args:
            user_id: User ID.
            permission: Permission to check.
            
        Returns:
            True if user has permission, False otherwise.
        """
        if user_id not in self.users:
            return False
        
        role = self.users[user_id]
        return permission in self.roles.get(role, [])
    
    def get_user_role(self, user_id: str) -> Optional[str]:
        """Get user role.
        
        Args:
            user_id: User ID.
            
        Returns:
            User role or None if user not found.
        """
        return self.users.get(user_id)
    
    def update_user_role(self, user_id: str, role: str):
        """Update user role.
        
        Args:
            user_id: User ID.
            role: New role.
        """
        if role not in self.roles:
            raise ValueError(f"Invalid role: {role}")
        
        if user_id in self.users:
            self.users[user_id] = role
        else:
            raise ValueError(f"User not found: {user_id}")
    
    def remove_user(self, user_id: str):
        """Remove user.
        
        Args:
            user_id: User ID.
        """
        if user_id in self.users:
            del self.users[user_id]
    
    def get_all_users(self) -> Dict[str, str]:
        """Get all users and their roles.
        
        Returns:
            Dictionary of user IDs to roles.
        """
        return self.users.copy()
    
    def get_all_roles(self) -> Dict[str, List[str]]:
        """Get all roles and their permissions.
        
        Returns:
            Dictionary of roles to permissions.
        """
        return self.roles.copy()

# Create global access control manager instance
access_control_manager = AccessControlManager()
