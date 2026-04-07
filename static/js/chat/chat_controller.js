// Chat Center Controller
class ChatCenterController {
  constructor() {
    this.currentConversationId = null;
    this.conversations = [];
    this.messages = [];
    this.isLoading = false;
    this.sidebarCollapsed = false;
    
    this.init();
  }
  
  init() {
    this.loadConversations();
    this.setupEventListeners();
    this.setupAutoSave();
  }
  
  setupEventListeners() {
    // Search box
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.filterConversations(e.target.value);
      });
    }
    
    // Toggle sidebar
    const toggleBtn = document.getElementById('toggleSidebarBtn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.toggleSidebar());
    }
    
    // Auto-resize textarea
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
      messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
      });
    }
  }
  
  setupAutoSave() {
    // Auto-save draft every 30 seconds
    setInterval(() => {
      const input = document.getElementById('messageInput');
      if (input && input.value.trim()) {
        localStorage.setItem(`chat_draft_${this.currentConversationId}`, input.value);
      }
    }, 30000);
  }
  
  async loadConversations(search = '') {
    try {
      const params = new URLSearchParams({
        user_id: 'default_user',
        page: 1,
        limit: 50
      });
      
      if (search) {
        params.append('search', search);
      }
      
      const response = await fetch(`/api/v2/chat?${params}`);
      const data = await response.json();
      
      if (data.success) {
        this.conversations = data.data.items;
        this.renderConversationList();
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
      this.showError('加载对话失败');
    }
  }
  
  filterConversations(search) {
    const filtered = this.conversations.filter(conv => 
      conv.title.toLowerCase().includes(search.toLowerCase())
    );
    this.renderConversationList(filtered);
  }
  
  renderConversationList(list = this.conversations) {
    const container = document.getElementById('conversationList');
    
    if (list.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 40px; color: var(--text-muted);">
          <div style="font-size: 48px; margin-bottom: 10px;">💬</div>
          <div>暂无对话</div>
        </div>
      `;
      return;
    }
    
    container.innerHTML = list.map(conv => `
      <div class="conversation-item ${conv.id === this.currentConversationId ? 'active' : ''}"
           onclick="chatController.selectConversation('${conv.id}')">
        <div class="conversation-item-header">
          <h4 class="conversation-item-title" title="${this.escapeHtml(conv.title)}">
            ${this.escapeHtml(conv.title)}
          </h4>
          <div class="conversation-item-actions">
            <button class="action-btn" onclick="event.stopPropagation(); chatController.renameConversation('${conv.id}')" title="重命名">
              ✏️
            </button>
            <button class="action-btn delete" onclick="event.stopPropagation(); chatController.deleteConversation('${conv.id}')" title="删除">
              🗑️
            </button>
          </div>
        </div>
        <div class="conversation-item-meta">
          <span>${conv.message_count || 0} 条消息</span>
          <span>${this.formatTime(conv.last_message_at)}</span>
        </div>
      </div>
    `).join('');
  }
  
  async selectConversation(id) {
    this.currentConversationId = id;
    this.isLoading = true;
    this.showTypingIndicator();
    
    try {
      const [convResponse, msgResponse] = await Promise.all([
        fetch(`/api/v2/chat/${id}`),
        fetch(`/api/v2/chat/${id}/messages?limit=50`)
      ]);
      
      const convData = await convResponse.json();
      const msgData = await msgResponse.json();
      
      if (convData.success && msgData.success) {
        document.getElementById('chatTitle').textContent = convData.data.title;
        this.messages = msgData.data.messages || [];
        this.renderMessages();
        this.renderConversationList(); // Update active state
        
        // Load draft
        const draft = localStorage.getItem(`chat_draft_${id}`);
        if (draft) {
          document.getElementById('messageInput').value = draft;
        }
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
      this.showError('加载对话失败');
    } finally {
      this.isLoading = false;
      this.hideTypingIndicator();
    }
  }
  
  renderMessages() {
    const container = document.getElementById('chatMessages');
    
    if (this.messages.length === 0) {
      container.innerHTML = `
        <div class="chat-empty-state">
          <div class="chat-empty-state-icon">💬</div>
          <h2 class="chat-empty-state-title">开始对话吧！</h2>
          <p class="chat-empty-state-text">在下方输入框中输入消息，与总裁办开始对话</p>
        </div>
      `;
      return;
    }
    
    container.innerHTML = this.messages.map(msg => `
      <div class="message ${msg.role}">
        <div class="message-avatar">
          ${this.getAvatar(msg.role)}
        </div>
        <div class="message-content">
          <div class="message-bubble">
            <div class="message-text">${this.escapeHtml(msg.content)}</div>
            ${msg.metadata && msg.metadata.task_id ? this.renderTaskCard(msg.metadata) : ''}
          </div>
          <div class="message-meta">
            <span class="message-time">${this.formatTime(msg.created_at)}</span>
            ${msg.role === 'user' ? '<span class="message-status">已发送</span>' : ''}
          </div>
        </div>
      </div>
    `).join('');
    
    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
  }
  
  renderTaskCard(metadata) {
    const task = metadata;
    const progress = task.progress || 0;
    
    return `
      <div class="task-card">
        <div class="task-card-header">
          <h4 class="task-card-title">📋 ${this.escapeHtml(task.task_name || '任务')}</h4>
          <span class="task-card-status ${task.status || 'pending'}">
            ${task.status || '待处理'}
          </span>
        </div>
        <div class="task-card-progress">
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${progress}%"></div>
          </div>
          <div class="progress-text">${progress}% 完成</div>
        </div>
        <div class="task-card-actions">
          <button class="task-card-btn" onclick="chatController.viewTask('${task.task_id}')">
            查看详情
          </button>
          ${task.status === 'in_progress' ? `
            <button class="task-card-btn" onclick="chatController.pauseTask('${task.task_id}')">
              暂停
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }
  
  async sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    
    if (!content || !this.currentConversationId) {
      return;
    }
    
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    
    try {
      // Add user message to UI
      this.messages.push({
        role: 'user',
        content: content,
        created_at: new Date().toISOString()
      });
      this.renderMessages();
      
      input.value = '';
      input.style.height = 'auto';
      
      // Send to API
      const response = await fetch(`/api/v2/chat/${this.currentConversationId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: 'user',
          type: 'text',
          content: content
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        // Reload messages to get updated list
        await this.selectConversation(this.currentConversationId);
        
        // TODO: Send to executive office and get AI response
        // For now, just show the user message
      } else {
        this.showError('发送失败');
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      this.showError('发送失败，请重试');
    } finally {
      sendBtn.disabled = false;
    }
  }
  
  async createNewConversation() {
    const title = prompt('请输入对话标题（可选）:', '新对话');
    
    try {
      const response = await fetch('/api/v2/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default_user',
          title: title || '新对话',
          initial_message: '你好！'
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        await this.loadConversations();
        this.selectConversation(data.data.id);
      } else {
        this.showError('创建对话失败');
      }
    } catch (error) {
      console.error('Failed to create conversation:', error);
      this.showError('创建对话失败');
    }
  }
  
  async renameConversation(id) {
    const conv = this.conversations.find(c => c.id === id);
    if (!conv) return;
    
    const newTitle = prompt('请输入新标题:', conv.title);
    if (!newTitle || newTitle === conv.title) return;
    
    try {
      const response = await fetch(`/api/v2/chat/${id}/title`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      });
      
      const data = await response.json();
      
      if (data.success) {
        await this.loadConversations();
      } else {
        this.showError('重命名失败');
      }
    } catch (error) {
      console.error('Failed to rename conversation:', error);
      this.showError('重命名失败');
    }
  }
  
  async deleteConversation(id) {
    if (!confirm('确定要删除这个对话吗？此操作不可恢复。')) {
      return;
    }
    
    try {
      const response = await fetch(`/api/v2/chat/${id}`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
      if (data.success) {
        if (this.currentConversationId === id) {
          this.currentConversationId = null;
          this.messages = [];
          document.getElementById('chatTitle').textContent = '选择或创建一个对话';
          document.getElementById('chatMessages').innerHTML = '';
        }
        await this.loadConversations();
      } else {
        this.showError('删除失败');
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      this.showError('删除失败');
    }
  }
  
  toggleSidebar() {
    const sidebar = document.querySelector('.chat-sidebar');
    sidebar.classList.toggle('collapsed');
    this.sidebarCollapsed = !this.sidebarCollapsed;
  }
  
  showTypingIndicator() {
    const container = document.getElementById('chatMessages');
    const indicator = document.createElement('div');
    indicator.id = 'typingIndicator';
    indicator.className = 'message';
    indicator.innerHTML = `
      <div class="message-avatar">🎩</div>
      <div class="message-content">
        <div class="message-bubble">
          <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
        </div>
      </div>
    `;
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
  }
  
  hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
      indicator.remove();
    }
  }
  
  viewTask(taskId) {
    window.location.href = `/tasks/${taskId}`;
  }
  
  async pauseTask(taskId) {
    try {
      await fetch(`/api/tasks/${taskId}/pause`, { method: 'POST' });
      alert('任务已暂停');
    } catch (error) {
      console.error('Failed to pause task:', error);
      alert('暂停失败，请重试');
    }
  }
  
  handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
  
  getAvatar(role) {
    const avatars = {
      'user': '👤',
      'executive': '🎩',
      'system': '⚙️',
      'task': '📋'
    };
    return avatars[role] || '💬';
  }
  
  formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}天前`;
    if (hours > 0) return `${hours}小时前`;
    if (minutes > 0) return `${minutes}分钟前`;
    return '刚刚';
  }
  
  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  showError(message) {
    alert(message);
  }
}

// Initialize chat controller
const chatController = new ChatCenterController();
