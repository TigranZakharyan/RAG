# =========================
# Base
# =========================
FROM node:20-alpine AS base

WORKDIR /app

COPY package*.json ./

RUN npm install

# =========================
# Development
# =========================
FROM base AS development

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# =========================
# Build for Production
# =========================
FROM base AS builder

COPY . .

RUN npm run build

# =========================
# Production Server (Nginx)
# =========================
FROM nginx:alpine AS production

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
