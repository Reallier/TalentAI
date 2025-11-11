#!/bin/bash

echo "🚀 启动 TalentAI 智能招聘匹配系统"
echo "================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未找到 Docker，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: 未找到 Docker Compose，请先安装 Docker Compose"
    exit 1
fi

# 检查 .env 文件
if [ ! -f "backend/.env" ]; then
    echo "📝 创建环境配置文件..."
    cp backend/.env.example backend/.env
    echo "⚠️  请编辑 backend/.env 文件，填入你的 OpenAI API Key"
    echo "   然后重新运行此脚本"
    exit 1
fi

# 检查 OpenAI API Key
if grep -q "sk-your-openai-api-key-here" backend/.env; then
    echo "⚠️  警告: 请在 backend/.env 中配置有效的 OpenAI API Key"
    read -p "是否继续启动? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 构建并启动服务..."
docker-compose up --build -d

echo ""
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "📊 检查服务状态..."
docker-compose ps

echo ""
echo "✅ TalentAI 已启动!"
echo ""
echo "访问地址:"
echo "  🌐 前端界面: http://localhost:3000"
echo "  📡 API 文档: http://localhost:8000/docs"
echo "  💚 健康检查: http://localhost:8000/health"
echo ""
echo "查看日志:"
echo "  docker-compose logs -f backend"
echo ""
echo "停止服务:"
echo "  docker-compose down"
echo ""