# Frontend Dockerfile
FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
    listen 5173;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://middleware:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
EOF

EXPOSE 5173

CMD ["nginx", "-g", "daemon off;"]
