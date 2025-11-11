# TalentAI - 智能招聘匹配系统

基于 RAG 的智能人才匹配与简历管理系统

## 核心功能

### 1. JD→匹配
- 从职位描述中提取必备/加分技能
- 双路召回（关键词+语义向量）
- 融合排序并提供证据条
- 可解释的匹配结果

### 2. 简历→入库
- 自动解析 PDF/DOCX 简历
- 智能去重与合并
- 1-2 分钟内可被检索
- 完整的合并谱系追踪

## 技术栈

- **后端**: Python 3.11+ / FastAPI
- **数据库**: PostgreSQL 15+ (结构化 + FTS + pgvector)
- **LLM**: OpenAI API (可替换)
- **部署**: Docker Compose

## 系统架构

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   前端界面   │ ───> │   FastAPI    │ ───> │ PostgreSQL  │
│  (Nginx)    │ <─── │   Backend    │ <─── │ + pgvector  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            v
                     ┌──────────────┐
                     │  OpenAI API  │
                     │ (LLM + Embed)│
                     └──────────────┘
```

## 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- OpenAI API Key

### 一键启动

```bash
# 1. 复制环境变量模板
cp backend/.env.example backend/.env

# 2. 编辑 backend/.env，填入你的 OpenAI API Key
# OPENAI_API_KEY=sk-your-actual-key-here

# 3. 给启动脚本添加执行权限
chmod +x start.sh

# 4. 启动服务
./start.sh
```

服务启动后，访问：
- **前端界面**: http://localhost:3000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

### 手动启动（不使用脚本）

```bash
# 构建并启动所有服务
docker-compose up --build -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 完全清理（包括数据）
docker-compose down -v
```

### API 端点

- `POST /api/match` - JD 匹配候选人
- `GET /api/search` - 关键词搜索
- `POST /api/candidates/ingest` - 导入简历
- `GET /api/candidates/{id}` - 获取候选人详情
- `POST /api/reindex` - 重建索引

## 设计原则

1. **模型即索引，原文为真** - 检索与解释交给 LLM+RAG
2. **数据库只管身份与状态** - 不做重建模
3. **最小组件，渐进可替换** - 单体服务，组件可插拔
4. **可解释优先** - 排序有理由，合并有谱系

## 验收标准

- ✅ Top10 合理率 ≥ 70%，每条有 ≥2 条证据
- ✅ 入库后 ≤ 2 分钟可被检索
- ✅ /match P95 ≤ 1 秒
- ✅ 可回溯任意字段来源
- ✅ 向量召回关闭仍可用

## License

MIT

## 核心功能使用

### 1. 简历入库

**Web 界面**:
1. 访问前端页面，切换到"简历上传"标签
2. 拖拽或点击上传 PDF/DOCX 格式简历
3. 系统自动解析、判重、合并，1-2 分钟内可被检索

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/candidates/ingest" \
  -F "file=@resume.pdf" \
  -F "source=api_upload"
```

### 2. JD 匹配

**Web 界面**:
1. 切换到"JD 匹配"标签
2. 输入职位描述
3. 可选：设置过滤条件（地点、年限等）
4. 点击"开始匹配"，查看排序结果和证据

**API 调用**:
```bash
curl -X POST "http://localhost:8000/api/match" \
  -H "Content-Type: application/json" \
  -d '{
    "jd": "招聘 Python 后端工程师，3年以上经验，熟悉 FastAPI、PostgreSQL",
    "top_k": 20,
    "explain": true
  }'
```

### 3. 关键词搜索

**Web 界面**:
切换到"候选人搜索"标签，输入关键词进行全文搜索

**API 调用**:
```bash
curl "http://localhost:8000/api/search?q=Python&top_k=20"
```

## API 端点文档

### 匹配相关
- `POST /api/match` - JD 匹配候选人（核心功能）
- `GET /api/search` - 关键词搜索候选人

### 简历管理
- `POST /api/candidates/ingest` - 上传并入库简历
- `GET /api/candidates/{id}` - 获取候选人详情
- `GET /api/candidates` - 列出候选人（分页）
- `DELETE /api/candidates/{id}` - 删除候选人

### 索引管理
- `POST /api/reindex` - 重建索引
- `GET /api/stats` - 获取系统统计

### 健康检查
- `GET /health` - 健康检查
- `GET /` - API 信息

**完整 API 文档**: http://localhost:8000/docs

## 设计原则

1. **模型即索引，原文为真** - 检索与解释交给 LLM+RAG；原始简历文本是唯一真相源
2. **数据库只管身份与状态** - 主键、去重、过滤字段、版本/时间、证据指针——不做重建模
3. **最小组件，渐进可替换** - 单体服务，组件可插拔，任何瓶颈对应可替换方案
4. **可解释优先** - 排序有理由，入库有谱系，删除有审计

## 验收标准

- ✅ Top10 合理率 ≥ 70%，每条有 ≥2 条证据
- ✅ 入库后 ≤ 2 分钟可被检索
- ✅ /match P95 ≤ 1 秒
- ✅ 可回溯任意字段来源
- ✅ 向量召回关闭仍可用

## 项目结构

```
TalentAI/
├── backend/                # 后端服务
│   ├── services/          # 业务逻辑层
│   │   ├── resume_parser.py       # 简历解析
│   │   ├── deduplication.py       # 去重合并
│   │   ├── llm_service.py         # LLM 服务
│   │   ├── indexing_service.py    # 索引管理
│   │   ├── matching_service.py    # 匹配服务
│   │   └── ingest_service.py      # 入库服务
│   ├── models.py          # 数据模型
│   ├── schemas.py         # API Schema
│   ├── database.py        # 数据库连接
│   ├── config.py          # 配置管理
│   ├── main.py            # FastAPI 主程序
│   └── requirements.txt   # Python 依赖
├── frontend/              # 前端界面
│   ├── index.html        # 主页面
│   ├── app.js            # 前端逻辑
│   └── nginx.conf        # Nginx 配置
├── database/              
│   └── init.sql          # 数据库初始化脚本
├── docker-compose.yml    # Docker 编排
├── start.sh              # 启动脚本
└── README.md             # 说明文档
```

## 常见问题

### 1. 服务启动失败？
- 检查 Docker 是否运行
- 确认 OpenAI API Key 已正确配置
- 查看日志：`docker-compose logs -f backend`

### 2. 匹配结果不理想？
- 调整排序权重（backend/config.py）
- 增加样本数据
- 检查 JD 描述是否清晰

### 3. 简历解析失败？
- 确认文件格式（仅支持 PDF/DOCX）
- 检查文件大小（默认限制 10MB）
- 查看后端日志获取详细错误

### 4. 如何清理数据？
```bash
# 停止并删除所有数据
docker-compose down -v

# 重新启动
./start.sh
```

## 扩展与优化

### 性能优化
- **向量数据库**: 替换为 Milvus 或 Weaviate 以支持更大规模
- **全文搜索**: 替换为 ElasticSearch/OpenSearch
- **任务队列**: 使用 Celery + Redis 处理异步任务
- **缓存**: 添加 Redis 缓存热点数据

### 功能扩展
- **多模型支持**: 接入多个 LLM 提供商（Claude、文心等）
- **学习排序**: 基于用户反馈训练重排模型
- **简历生成**: 根据 JD 自动生成候选人推荐报告
- **协同过滤**: 基于历史匹配数据推荐相似候选人

## License

MIT