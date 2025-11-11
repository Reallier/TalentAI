FROM nginx:alpine

# 复制前端文件到 nginx 默认目录
COPY index.html /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]