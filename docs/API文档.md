# OPC-Agents API文档

## 1. 概述

OPC-Agents提供了一套RESTful API接口，用于系统的管理和集成。本文档详细说明了所有可用的API端点、请求参数和响应格式。

### 1.1 基础URL

```
http://localhost:5000/api
```

### 1.2 认证

API使用API密钥进行认证，需要在请求头中包含 `Authorization` 字段：

```
Authorization: Bearer <your_api_key>
```

## 2. 部门管理API

### 2.1 获取部门列表

- **方法**：GET
- **端点**：`/departments`
- **参数**：无
- **响应**：
  ```json
  {
    "status": "success",
    "data": [
      {
        "id": "hr",
        "name": "人力资源部",
        "description": "负责人员招聘、培训和管理"
      },
      {
        "id": "it",
        "name": "技术部",
        "description": "负责系统开发和维护"
      }
    ]
  }
  ```

### 2.2 获取部门详情

- **方法**：GET
- **端点**：`/departments/{department_id}`
- **参数**：
  - `department_id`：部门ID
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "hr",
      "name": "人力资源部",
      "description": "负责人员招聘、培训和管理",
      "agents": [
        {
          "id": "agent1",
          "name": "招聘专员",
          "skills": ["招聘", "面试"]
        }
      ]
    }
  }
  ```

## 3. 代理管理API

### 3.1 获取代理列表

- **方法**：GET
- **端点**：`/agents`
- **参数**：
  - `department`（可选）：部门ID，用于过滤特定部门的代理
- **响应**：
  ```json
  {
    "status": "success",
    "data": [
      {
        "id": "agent1",
        "name": "招聘专员",
        "department": "hr",
        "skills": ["招聘", "面试"]
      },
      {
        "id": "agent2",
        "name": "开发工程师",
        "department": "it",
        "skills": ["编程", "调试"]
      }
    ]
  }
  ```

### 3.2 获取代理详情

- **方法**：GET
- **端点**：`/agents/{agent_id}`
- **参数**：
  - `agent_id`：代理ID
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "agent1",
      "name": "招聘专员",
      "department": "hr",
      "skills": ["招聘", "面试"],
      "performance": {
        "response_time": 0.8,
        "accuracy": 0.9
      }
    }
  }
  ```

### 3.3 创建代理

- **方法**：POST
- **端点**：`/agents`
- **参数**：
  ```json
  {
    "name": "新代理",
    "department": "hr",
    "skills": ["技能1", "技能2"]
  }
  ```
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "agent3",
      "name": "新代理",
      "department": "hr",
      "skills": ["技能1", "技能2"]
    }
  }
  ```

### 3.4 更新代理

- **方法**：PUT
- **端点**：`/agents/{agent_id}`
- **参数**：
  ```json
  {
    "name": "更新后的代理",
    "skills": ["技能1", "技能2", "技能3"]
  }
  ```
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "agent1",
      "name": "更新后的代理",
      "department": "hr",
      "skills": ["技能1", "技能2", "技能3"]
    }
  }
  ```

### 3.5 删除代理

- **方法**：DELETE
- **端点**：`/agents/{agent_id}`
- **参数**：
  - `agent_id`：代理ID
- **响应**：
  ```json
  {
    "status": "success",
    "message": "代理删除成功"
  }
  ```

## 4. 技能管理API

### 4.1 获取技能列表

- **方法**：GET
- **端点**：`/skills`
- **参数**：无
- **响应**：
  ```json
  {
    "status": "success",
    "data": [
      {
        "id": "skill1",
        "name": "招聘",
        "description": "负责人员招聘"
      },
      {
        "id": "skill2",
        "name": "编程",
        "description": "负责系统开发"
      }
    ]
  }
  ```

### 4.2 注册技能

- **方法**：POST
- **端点**：`/skills`
- **参数**：
  ```json
  {
    "name": "新技能",
    "description": "技能描述",
    "path": "/path/to/skill"
  }
  ```
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "skill3",
      "name": "新技能",
      "description": "技能描述"
    }
  }
  ```

## 5. 模型管理API

### 5.1 获取模型列表

- **方法**：GET
- **端点**：`/models`
- **参数**：无
- **响应**：
  ```json
  {
    "status": "success",
    "data": [
      {
        "id": "openai",
        "name": "OpenAI GPT",
        "status": "active"
      },
      {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "status": "inactive"
      }
    ]
  }
  ```

### 5.2 注册模型

- **方法**：POST
- **端点**：`/models`
- **参数**：
  ```json
  {
    "name": "新模型",
    "type": "openai",
    "config": {
      "api_key": "your_api_key",
      "model": "gpt-4"
    }
  }
  ```
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "id": "model1",
      "name": "新模型",
      "type": "openai"
    }
  }
  ```

### 5.3 设置当前模型

- **方法**：PUT
- **端点**：`/models/current`
- **参数**：
  ```json
  {
    "model_id": "openai"
  }
  ```
- **响应**：
  ```json
  {
    "status": "success",
    "message": "当前模型已设置为 openai"
  }
  ```

## 6. 系统管理API

### 6.1 获取系统状态

- **方法**：GET
- **端点**：`/system/status`
- **参数**：无
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "system": "running",
      "agents": 5,
      "models": 3,
      "skills": 10
    }
  }
  ```

### 6.2 获取系统信息

- **方法**：GET
- **端点**：`/system/info`
- **参数**：无
- **响应**：
  ```json
  {
    "status": "success",
    "data": {
      "version": "1.0.0",
      "python_version": "3.9.6",
      "os": "macOS"
    }
  }
  ```

## 7. 错误处理

API使用标准HTTP状态码来表示请求的结果：

- **200 OK**：请求成功
- **201 Created**：资源创建成功
- **400 Bad Request**：请求参数错误
- **401 Unauthorized**：认证失败
- **403 Forbidden**：权限不足
- **404 Not Found**：资源不存在
- **500 Internal Server Error**：服务器内部错误

错误响应格式：

```json
{
  "status": "error",
  "message": "错误信息"
}
```

## 8. 示例代码

### 8.1 Python示例

```python
import requests

# 设置API密钥
api_key = "your_api_key"
headers = {
    "Authorization": f"Bearer {api_key}"
}

# 获取代理列表
response = requests.get("http://localhost:5000/api/agents", headers=headers)
print(response.json())

# 创建新代理
data = {
    "name": "新代理",
    "department": "hr",
    "skills": ["招聘", "面试"]
}
response = requests.post("http://localhost:5000/api/agents", json=data, headers=headers)
print(response.json())
```

### 8.2 JavaScript示例

```javascript
// 设置API密钥
const apiKey = "your_api_key";
const headers = {
    "Authorization": `Bearer ${apiKey}`,
    "Content-Type": "application/json"
};

// 获取代理列表
fetch("http://localhost:5000/api/agents", {
    method: "GET",
    headers: headers
})
.then(response => response.json())
.then(data => console.log(data));

// 创建新代理
const data = {
    "name": "新代理",
    "department": "hr",
    "skills": ["招聘", "面试"]
};

fetch("http://localhost:5000/api/agents", {
    method: "POST",
    headers: headers,
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => console.log(data));
```

## 9. 速率限制

API实施速率限制，以防止滥用：

- **每IP限制**：每分钟60个请求
- **每用户限制**：每分钟100个请求

超过限制的请求将返回 `429 Too Many Requests` 状态码。

---

**版本**：1.0.0
**最后更新**：2025-09-26