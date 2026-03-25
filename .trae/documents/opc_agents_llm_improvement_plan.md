# OPC-Agents 大模型调用改进计划

## 现状分析
当前OPC-Agents系统的大模型调用存在以下问题：
1. 大模型调用失败时没有明确的错误提示，用户体验不佳
2. GLM模型调用返回403错误，可能是API密钥或调用方式的问题
3. 没有充分利用本地已经成功连接GLM模型的zeroclaw框架

## 改进目标
1. 实现大模型调用失败时的明确错误提示
2. 参考zeroclaw的GLM模型对接方式，改进OPC-Agents的GLM模型调用
3. 探索与zeroclaw框架的集成可能性

## 任务分解

### [x] 任务1: 实现大模型调用失败的错误提示
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 修改trae_request方法，当大模型调用失败时返回明确的错误信息
  - 在web界面中显示友好的错误提示
  - 区分不同类型的错误（如API密钥错误、网络错误等）
- **Success Criteria**:
  - 当大模型调用失败时，用户能够看到明确的错误提示
  - 错误提示能够反映具体的失败原因
- **Test Requirements**:
  - `programmatic` TR-1.1: 当GLM模型API密钥错误时，返回"大模型Key不可用"的错误提示
  - `programmatic` TR-1.2: 当网络连接失败时，返回"大模型未连接"的错误提示
  - `human-judgement` TR-1.3: 错误提示清晰易懂，能够帮助用户理解问题所在

### [x] 任务2: 参考zeroclaw改进GLM模型调用
- **Priority**: P0
- **Depends On**: 任务1
- **Description**:
  - 分析zeroclaw的GLM模型对接方式
  - 修改OPC-Agents的GLM模型调用代码
  - 确保使用正确的API端点和请求格式
- **Success Criteria**:
  - OPC-Agents能够成功调用GLM模型
  - GLM模型返回有效的响应
- **Test Requirements**:
  - `programmatic` TR-2.1: 能够成功调用GLM模型API并获取响应
  - `human-judgement` TR-2.2: 响应内容符合预期，不是模拟响应

### [/] 任务3: 探索与zeroclaw框架的集成
- **Priority**: P1
- **Depends On**: 任务2
- **Description**:
  - 研究zeroclaw框架的API和集成方式
  - 评估将OPC-Agents与zeroclaw集成的可行性
  - 实现基本的集成方案
- **Success Criteria**:
  - OPC-Agents能够通过zeroclaw框架调用大模型
  - 集成后的系统能够正常工作
- **Test Requirements**:
  - `programmatic` TR-3.1: OPC-Agents能够通过zeroclaw框架调用大模型
  - `programmatic` TR-3.2: 集成后的系统能够正常处理用户请求

## 实现步骤
1. 实现大模型调用失败的错误提示
2. 参考zeroclaw改进GLM模型调用
3. 探索与zeroclaw框架的集成

## 预期结果
- OPC-Agents系统能够在大模型调用失败时提供明确的错误提示
- OPC-Agents系统能够成功调用GLM模型
- OPC-Agents系统能够与zeroclaw框架集成，提高大模型调用的可靠性