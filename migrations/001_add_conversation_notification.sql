-- Migration: Add conversation and notification tables
-- Version: 001
-- Date: 2026-04-07
-- Description: Create tables for conversation management and notification system

BEGIN TRANSACTION;

-- 1. Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- active/archived/deleted
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    metadata TEXT  -- JSON format for additional data
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_conversations_user_status 
ON conversations(user_id, status);

CREATE INDEX IF NOT EXISTS idx_conversations_last_message 
ON conversations(user_id, last_message_at DESC);

-- 2. Messages table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user/executive/system/task
    message_type TEXT NOT NULL,  -- text/plan/task/search/result
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON format
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_messages_conversation 
ON messages(conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_unread 
ON messages(conversation_id, read) WHERE read = FALSE;

-- 3. Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- task/confirmation/system/finance/hr
    priority TEXT NOT NULL,  -- urgent/important/normal/info
    title TEXT NOT NULL,
    content TEXT,
    related_object_type TEXT,  -- task/agent/plan
    related_object_id TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_notifications_user_unread 
ON notifications(user_id, is_read) WHERE is_read = FALSE;

CREATE INDEX IF NOT EXISTS idx_notifications_user_created 
ON notifications(user_id, created_at DESC);

-- 4. Task-Conversation Links table
CREATE TABLE IF NOT EXISTS task_conversation_links (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    link_type TEXT NOT NULL,  -- created_from/referenced_in/updated_by
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_link 
ON task_conversation_links(task_id, conversation_id, link_type);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_links_task 
ON task_conversation_links(task_id);

CREATE INDEX IF NOT EXISTS idx_links_conversation 
ON task_conversation_links(conversation_id);

-- 5. Migrate existing tasks to conversations (if needed)
-- This creates a conversation for each existing task
INSERT OR IGNORE INTO conversations (id, title, user_id, status, created_at, last_message_at, message_count)
SELECT 
    'conv_' || SUBSTR(task_id, 6) as conversation_id,
    COALESCE(task_name, 'Task Conversation') as title,
    'default_user' as user_id,
    CASE 
        WHEN status = 'completed' THEN 'archived'
        ELSE 'active'
    END as status,
    datetime(created_at, 'unixepoch') as created_at,
    datetime(updated_at, 'unixepoch') as last_message_at,
    2 as message_count  -- Initial messages: user + system
FROM tasks
WHERE task_id LIKE 'task-%';

-- 6. Create initial messages for migrated tasks
INSERT OR IGNORE INTO messages (id, conversation_id, role, message_type, content, created_at)
SELECT 
    'msg_init_' || SUBSTR(task_id, 6),
    'conv_' || SUBSTR(task_id, 6),
    'system' as role,
    'task' as message_type,
    json_object(
        'task_id', task_id,
        'task_name', task_name,
        'status', status
    ) as content,
    datetime(created_at, 'unixepoch') as created_at
FROM tasks
WHERE task_id LIKE 'task-%';

COMMIT;

-- Verify migration
SELECT 'conversations' as table_name, COUNT(*) as row_count FROM conversations
UNION ALL
SELECT 'messages', COUNT(*) FROM messages
UNION ALL
SELECT 'notifications', COUNT(*) FROM notifications
UNION ALL
SELECT 'task_conversation_links', COUNT(*) FROM task_conversation_links;
