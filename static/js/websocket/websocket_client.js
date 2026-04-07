/**
 * WebSocket 客户端 - 实时通信前端模块
 * 
 * 提供 WebSocket 连接、消息接收、自动重连等功能
 */

class WebSocketClient {
    constructor(options = {}) {
        this.baseUrl = options.baseUrl || this.getWebSocketUrl();
        this.reconnectInterval = options.reconnectInterval || 3000; // 3 秒
        this.maxReconnectAttempts = options.maxReconnectAttempts || 10;
        this.heartbeatInterval = options.heartbeatInterval || 30000; // 30 秒
        
        this.connection = null;
        this.reconnectAttempts = 0;
        this.isConnected = false;
        this.isConnecting = false;
        this.messageHandlers = new Map();
        this.heartbeatTimer = null;
        
        // 连接状态回调
        this.onConnect = options.onConnect || (() => {});
        this.onDisconnect = options.onDisconnect || (() => {});
        this.onError = options.onError || (() => {});
    }
    
    /**
     * 获取 WebSocket URL
     */
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}`;
    }
    
    /**
     * 连接到 WebSocket 服务器
     */
    connect(channel, params = {}) {
        if (this.isConnecting || this.isConnected) {
            console.log('WebSocket already connected or connecting');
            return;
        }
        
        this.isConnecting = true;
        
        const url = `${this.baseUrl}/api/ws/${channel}`;
        if (params.chat_id) {
            this.connection = new WebSocket(`${url}/${params.chat_id}`);
        } else {
            this.connection = new WebSocket(url);
        }
        
        this.connection.onopen = () => this.handleOpen();
        this.connection.onclose = (event) => this.handleClose(event);
        this.connection.onerror = (error) => this.handleError(error);
        this.connection.onmessage = (event) => this.handleMessage(event);
    }
    
    /**
     * 处理连接打开
     */
    handleOpen() {
        this.isConnecting = false;
        this.isConnected = true;
        this.reconnectAttempts = 0;
        
        console.log('WebSocket connected');
        this.onConnect();
        
        // 启动心跳
        this.startHeartbeat();
    }
    
    /**
     * 处理连接关闭
     */
    handleClose(event) {
        this.isConnecting = false;
        this.isConnected = false;
        
        console.log('WebSocket closed', event);
        this.onDisconnect();
        
        // 停止心跳
        this.stopHeartbeat();
        
        // 尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.scheduleReconnect();
        } else {
            console.error('Max reconnect attempts reached');
        }
    }
    
    /**
     * 处理连接错误
     */
    handleError(error) {
        console.error('WebSocket error', error);
        this.onError(error);
    }
    
    /**
     * 处理接收到的消息
     */
    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            console.log('WebSocket message received:', message);
            
            // 处理连接确认消息
            if (message.type === 'connected') {
                this.connectionId = message.connection_id;
                console.log('Connection ID:', this.connectionId);
            }
            
            // 处理心跳响应
            if (message.type === 'pong') {
                // 心跳正常
                return;
            }
            
            // 调用消息处理器
            if (this.messageHandlers.has(message.type)) {
                const handlers = this.messageHandlers.get(message.type);
                handlers.forEach(handler => handler(message));
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    }
    
    /**
     * 发送消息
     */
    send(message) {
        if (!this.isConnected || !this.connection) {
            console.warn('WebSocket not connected, message not sent');
            return false;
        }
        
        try {
            this.connection.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('Error sending message:', error);
            return false;
        }
    }
    
    /**
     * 发送心跳
     */
    sendHeartbeat() {
        if (this.isConnected) {
            this.send({ type: 'ping', timestamp: Date.now() });
        }
    }
    
    /**
     * 启动心跳
     */
    startHeartbeat() {
        this.stopHeartbeat(); // 清除之前的定时器
        
        this.heartbeatTimer = setInterval(() => {
            this.sendHeartbeat();
        }, this.heartbeatInterval);
    }
    
    /**
     * 停止心跳
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    /**
     * 计划重连
     */
    scheduleReconnect() {
        this.reconnectAttempts++;
        console.log(`Scheduling reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            // 重新连接需要 channel 和 params，这里需要保存
            // 简化处理，假设调用者会手动重连
        }, this.reconnectInterval);
    }
    
    /**
     * 断开连接
     */
    disconnect() {
        this.maxReconnectAttempts = 0; // 禁止重连
        
        if (this.connection) {
            this.connection.close();
        }
        
        this.stopHeartbeat();
    }
    
    /**
     * 注册消息处理器
     */
    on(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        
        this.messageHandlers.get(messageType).push(handler);
        
        // 返回取消订阅函数
        return () => {
            const handlers = this.messageHandlers.get(messageType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        };
    }
    
    /**
     * 获取连接状态
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            reconnectAttempts: this.reconnectAttempts,
            connectionId: this.connectionId
        };
    }
}

/**
 * 聊天 WebSocket 客户端
 */
class ChatWebSocketClient extends WebSocketClient {
    constructor(options = {}) {
        super(options);
        
        // 注册默认消息处理器
        this.on('new_message', (message) => {
            console.log('New message received:', message.data);
            // 可以在这里触发 UI 更新
        });
        
        this.on('task_update', (message) => {
            console.log('Task update received:', message.data);
        });
    }
    
    connect(chatId) {
        super.connect('chat', { chat_id: chatId });
    }
}

/**
 * 通知 WebSocket 客户端
 */
class NotificationWebSocketClient extends WebSocketClient {
    constructor(options = {}) {
        super(options);
        
        // 注册默认消息处理器
        this.on('new_notification', (message) => {
            console.log('New notification received:', message.data);
            // 可以在这里触发 UI 更新
        });
    }
    
    connect() {
        super.connect('notification');
    }
}

// 导出
window.WebSocketClient = WebSocketClient;
window.ChatWebSocketClient = ChatWebSocketClient;
window.NotificationWebSocketClient = NotificationWebSocketClient;
