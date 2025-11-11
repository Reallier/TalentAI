#!/bin/bash

echo "🧪 TalentAI API 测试脚本"
echo "========================"
echo ""

API_URL="http://localhost:8000"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试函数
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local data=$4
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "测试 $TOTAL_TESTS: $name ... "
    
    if [ "$method" == "GET" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
    elif [ "$method" == "POST" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    if [ "$response" == "200" ] || [ "$response" == "422" ]; then
        echo -e "${GREEN}✓ PASSED${NC} (HTTP $response)"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAILED${NC} (HTTP $response)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 3

# 1. 健康检查
echo -e "\n${YELLOW}=== 基础健康检查 ===${NC}"
test_endpoint "健康检查" "GET" "/health"
test_endpoint "API 信息" "GET" "/"

# 2. 统计信息
echo -e "\n${YELLOW}=== 统计信息 ===${NC}"
test_endpoint "系统统计" "GET" "/api/stats"

# 3. 候选人列表
echo -e "\n${YELLOW}=== 候选人管理 ===${NC}"
test_endpoint "候选人列表" "GET" "/api/candidates?limit=10"

# 4. 搜索功能
echo -e "\n${YELLOW}=== 搜索功能 ===${NC}"
test_endpoint "关键词搜索" "GET" "/api/search?q=Python&top_k=10"

# 5. JD 匹配（需要数据）
echo -e "\n${YELLOW}=== JD 匹配 ===${NC}"
JD_DATA='{
  "jd": "招聘 Python 后端工程师，要求 3 年以上工作经验，熟悉 FastAPI、Django、PostgreSQL、Redis 等技术栈。熟悉微服务架构优先。",
  "top_k": 10,
  "explain": true
}'
test_endpoint "JD 匹配" "POST" "/api/match" "$JD_DATA"

# 6. 简历上传测试（需要实际文件）
echo -e "\n${YELLOW}=== 简历上传 ===${NC}"
echo "⚠️  简历上传需要实际的 PDF/DOCX 文件，请手动测试"

# 结果汇总
echo ""
echo "========================"
echo "测试结果汇总:"
echo "  总测试数: $TOTAL_TESTS"
echo -e "  ${GREEN}通过: $PASSED_TESTS${NC}"
echo -e "  ${RED}失败: $FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}✅ 所有测试通过！${NC}"
    exit 0
else
    echo -e "\n${RED}❌ 部分测试失败${NC}"
    exit 1
fi