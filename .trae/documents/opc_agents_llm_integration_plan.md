# OPC-Agents 大模型直接通话改进计划

## 现状分析
当前OPC-Agents系统的大模型调用存在以下问题：
1. 主要依赖Trae的内置模型，缺乏对其他大模型的直接支持
2. 在Trae内置模型不可用时，回退到手动生成响应，这是一种模拟而非真正的大模型调用
3. 没有实现对配置文件中定义的其他模型（如GLM、OpenAI等）的直接调用

## 改进目标
1. 实现对配置文件中定义的所有大模型的直接调用
2. 优化模型选择和调用流程
3. 改进错误处理和回退机制
4. 确保系统能够与大模型进行真正的直接通话，而非依赖模拟

## 任务分解

### [x] 任务1: 实现大模型API调用基础框架
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 创建一个统一的大模型API调用框架，支持多种模型
  - 实现模型配置的加载和管理
  - 实现通用的API调用接口
- **Success Criteria**:
  - 能够加载配置文件中的所有模型配置
  - 能够通过统一接口调用不同的大模型
- **Test Requirements**:
  - `programmatic` TR-1.1: 能够成功加载所有模型配置
  - `programmatic` TR-1.2: 能够通过统一接口调用至少一种大模型

### [x] 任务2: 实现GLM模型的直接调用
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 实现GLM模型的API调用
  - 处理GLM模型的认证和请求格式
  - 测试GLM模型的响应
- **Success Criteria**:
  - 能够成功调用GLM模型API
  - 能够获取有效的响应
- **Test Requirements**:
  - `programmatic` TR-2.1: 能够成功调用GLM模型API并获取响应
  - `human-judgement` TR-2.2: 响应内容符合预期，不是模拟响应

### [x] 任务3: 实现其他模型的直接调用
- **Priority**: P1
- **Depends On**: 任务1
- **Description**:
  - 实现OpenAI模型的API调用
  - 实现Anthropic模型的API调用
  - 实现Google模型的API调用
  - 实现Azure模型的API调用
- **Success Criteria**:
  - 能够成功调用所有配置的模型API
  - 能够获取有效的响应
- **Test Requirements**:
  - `programmatic` TR-3.1: 能够成功调用至少一种其他模型API并获取响应
  - `human-judgement` TR-3.2: 响应内容符合预期，不是模拟响应

### [x] 任务4: 优化trae_request方法
- **Priority**: P0
- **Depends On**: 任务2, 任务3
- **Description**:
  - 修改trae_request方法，优先使用配置的大模型
  - 实现模型选择逻辑
  - 改进错误处理和回退机制
- **Success Criteria**:
  - trae_request方法能够直接调用配置的大模型
  - 只有在所有大模型都不可用时才回退到模拟响应
- **Test Requirements**:
  - `programmatic` TR-4.1: trae_request方法能够成功调用配置的大模型
  - `programmatic` TR-4.2: 当大模型不可用时能够回退到模拟响应

### [x] 任务5: 测试和验证
- **Priority**: P0
- **Depends On**: 任务4
- **Description**:
  - 测试大模型直接通话功能
  - 验证不同模型的响应质量
  - 测试错误处理和回退机制
- **Success Criteria**:
  - 所有大模型都能成功调用
  - 系统能够正确处理错误情况
  - 响应质量符合预期
- **Test Requirements**:
  - `programmatic` TR-5.1: 所有模型调用测试通过
  - `human-judgement` TR-5.2: 响应内容质量符合预期
  - `programmatic` TR-5.3: 错误处理测试通过

## 实现步骤
1. 创建大模型API调用基础框架
2. 实现GLM模型的直接调用
3. 实现其他模型的直接调用
4. 优化trae_request方法
5. 测试和验证

## 预期结果
- OPC-Agents系统能够直接调用配置的大模型
- 系统能够根据配置选择合适的模型
- 系统能够处理模型调用失败的情况
- 总裁办和各部门能够与大模型进行真正的直接通话，而非依赖模拟响应