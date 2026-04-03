# OPC-Agents 文档索引

本目录包含 OPC-Agents 项目的完整文档。

## 📚 文档分类

### 架构设计 (architecture/)
- [ARCHITECTURE.md](architecture/ARCHITECTURE.md) - 系统架构设计
- [CODE_MAP.md](architecture/CODE_MAP.md) - 代码地图（模块/API）
- [multi_task_concurrent_management.md](architecture/multi_task_concurrent_management.md) - 多任务并发管理设计方案

### 用户指南 (user_guides/)
- [用户故事和场景](user_guides/user_stories_scenarios.md) - 详细用户故事和使用场景
- [系统用户手册](user_guides/系统用户手册.md) - 完整使用指南
- [部署指南](user_guides/部署指南.md) - 系统部署说明
- [故障排除指南](user_guides/故障排除指南.md) - 常见问题解决

### API 文档 (api/)
- [API 文档](api/API 文档.md) - 完整 API 参考

### 部署指南
- [Docker 部署指南](deployment_guide.md) - Docker 容器化部署

## 📝 更新日志

- [CHANGELOG.md](CHANGELOG.md) - 项目更新日志

## 🔗 快速链接

- [README](../README.md) - 项目说明（中文）
- [README-EN](../README-EN.md) - Project README (English)
- [CODE_MAP](../CODE_MAP.md) - 代码地图（根目录）

## 📖 文档说明

### 多任务并发管理系统

OPC-Agents 现在支持真正的多任务并发执行：

- **并发执行**: 不同 Agent 可同时执行不同任务
- **优先级调度**: 6 级优先级（CRITICAL/URGENT/HIGH/MEDIUM/LOW/BACKGROUND）
- **任务管理**: 暂停/恢复、超时控制、自动重试
- **资源监控**: CPU/内存/进程实时监控
- **事件系统**: 7 种事件回调

详细设计文档：[多任务并发管理方案](architecture/multi_task_concurrent_management.md)

### 用户故事

查看典型使用场景：[用户故事和场景](user_guides/user_stories_scenarios.md)

主要场景包括：
1. 并发任务执行（多个 Agent 同时工作）
2. 任务暂停与恢复
3. 任务超时与重试
4. 事件通知系统
5. 资源监控

## 📊 测试报告

项目包含 130 个测试用例：
- 103 个技能测试
- 27 个并发管理测试
- 测试覆盖率：100%

详细测试报告请参考各测试文件。

---

**文档维护**: OPC-Agents 团队  
**最后更新**: 2026-04-03
