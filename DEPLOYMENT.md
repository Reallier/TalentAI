# TalentAI 生产环境部署指南

## 📋 项目概述

TalentAI 是一个基于 RAG 的智能招聘匹配系统，采用现代前后端分离架构：

- **前端**: 纯静态HTML/CSS/JS + Nginx
- **后端**: FastAPI + PostgreSQL + pgvector
- **部署**: Docker + Docker Compose + Traefik

## 🏗️ 架构设计

```
[用户浏览器] → HTTPS
    ↓
[Traefik Reverse Proxy] (端口:5443)
├── talentai.reallier.top → Frontend Container (nginx:80)
└── api.talentai.reallier.top → Backend Container (FastAPI:8000)
                                     ↓
                               Database Container (PostgreSQL:5432)
```

## 📦 部署组件

### 前端容器 (talentai-frontend)
- **镜像**: `ccr.ccs.tencentyun.com/reallier/talentai-frontend:latest`
- **技术栈**: Nginx + 静态文件
- **端口**: 80
- **域名**: `https://talentai.reallier.top:5443`

### 后端容器 (talentai-backend)
- **镜像**: `ccr.ccs.tencentyun.com/reallier/talentai-backend:latest`
- **技术栈**: Python + FastAPI + PostgreSQL + pgvector
- **端口**: 8000
- **域名**: `https://api.talentai.reallier.top:5443`

### 数据库容器 (talentai-db)
- **镜像**: `pgvector/pgvector:pg15`
- **技术栈**: PostgreSQL + pgvector 扩展
- **端口**: 5432 (仅内部访问)

## 🚀 部署流程

### 1. 本地构建镜像

```bash
# 前端镜像构建
cd frontend
docker build -t ccr.ccs.tencentyun.com/reallier/talentai-frontend:latest .

# 后端镜像构建
cd ../backend
docker build -t ccr.ccs.tencentyun.com/reallier/talentai-backend:latest .

# 登录腾讯云镜像仓库
docker login ccr.ccs.tencentyun.com --username=100026572558

# 推送镜像
docker push ccr.ccs.tencentyun.com/reallier/talentai-frontend:latest
docker push ccr.ccs.tencentyun.com/reallier/talentai-backend:latest
```

### 2. 服务器部署

```bash
# 上传配置文件到服务器
scp -i "key.pem" compose.yml .env root@server:/data/app-stack/talentai/

# SSH到服务器
ssh -i "key.pem" root@server
cd /data/app-stack/talentai

# 设置环境变量
export DASHSCOPE_API_KEY="your-api-key-here"

# 部署应用
docker compose up -d

# 检查状态
docker ps
docker logs talentai_backend
```

### 3. 验证部署

```bash
# 测试前端访问
curl -I https://talentai.reallier.top:5443

# 测试API访问
curl https://api.talentai.reallier.top:5443/api/stats
```

## ⚙️ 配置说明

### 环境变量 (.env)
```bash
DASHSCOPE_API_KEY=sk-your-api-key-here
```

### Traefik 配置
- **网络**: `traefik` (外部网络)
- **SSL**: 自动通过 Let's Encrypt 生成
- **路由**: 基于 Host 规则

### 数据库配置
- **用户**: talentai
- **密码**: talentai123
- **数据库**: talentai
- **扩展**: vector (pgvector)

## 🔧 运维命令

### 查看日志
```bash
# 后端日志
docker logs talentai_backend

# 前端日志
docker logs talentai_frontend

# 数据库日志
docker logs talentai_db
```

### 服务管理
```bash
# 重启服务
docker compose restart talentai-backend

# 停止服务
docker compose down

# 更新镜像
docker compose pull && docker compose up -d
```

### 数据库操作
```bash
# 进入数据库
docker exec -it talentai_db psql -U talentai -d talentai

# 备份数据
docker exec talentai_db pg_dump -U talentai talentai > backup.sql
```

## 🔒 安全配置

### API 密钥管理
- ✅ 敏感信息存储在 `.env` 文件中
- ✅ 不提交到版本控制系统
- ✅ 生产环境使用环境变量注入

### 网络安全
- ✅ 数据库仅内部网络访问
- ✅ Traefik 自动 SSL 证书
- ✅ HTTPS 强制加密

## 📊 监控和日志

### 健康检查
- 数据库: `pg_isready` 每10秒检查
- 应用: 依赖关系确保启动顺序

### 日志收集
- 容器日志通过 `docker logs` 查看
- 应用日志输出到容器 stdout/stderr

## 🎯 功能验证

部署完成后，可以通过以下功能验证系统正常：

1. **前端页面加载**: `https://talentai.reallier.top:5443`
2. **简历上传**: 支持 PDF/DOCX 格式
3. **智能匹配**: JD 匹配候选人
4. **候选人搜索**: 关键词全文搜索
5. **统计信息**: 系统状态监控

## 📝 更新流程

### 前端更新
```bash
# 修改前端代码
cd frontend
# 编辑 index.html, app.js 等

# 重新构建镜像
docker build -t ccr.ccs.tencentyun.com/reallier/talentai-frontend:latest .
docker push ccr.ccs.tencentyun.com/reallier/talentai-frontend:latest

# 服务器更新
ssh root@server
cd /data/app-stack/talentai
docker compose pull talentai-frontend
docker compose up -d talentai-frontend
```

### 后端更新
```bash
# 修改后端代码
cd backend
# 编辑 Python 代码

# 重新构建镜像
docker build -t ccr.ccs.tencentyun.com/reallier/talentai-backend:latest .
docker push ccr.ccs.tencentyun.com/reallier/talentai-backend:latest

# 服务器更新
ssh root@server
cd /data/app-stack/talentai
docker compose pull talentai-backend
docker compose up -d talentai-backend
```

## 🚨 故障排除

### 常见问题

1. **页面无法访问**
   - 检查 Traefik 日志: `docker logs traefik-traefik-1`
   - 验证 DNS 解析: `nslookup talentai.reallier.top`

2. **API 调用失败**
   - 检查后端日志: `docker logs talentai_backend`
   - 验证数据库连接: `docker exec talentai_db pg_isready -U talentai`

3. **数据库连接错误**
   - 检查数据库状态: `docker ps | grep talentai_db`
   - 验证网络连接: `docker exec talentai_backend ping talentai-db`

### 紧急恢复
```bash
# 完整重启
docker compose down
docker compose up -d

# 清理并重新部署
docker compose down -v  # 删除数据卷
docker compose up -d
```

---

**部署日期**: 2025-11-13
**部署环境**: 腾讯云服务器 + Traefik + Docker
**维护人员**: TalentAI Team