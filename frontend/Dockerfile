# ==============================================================================
# DataQuery Frontend Dockerfile — Multi-Stage Build with Nginx
# ==============================================================================

# Stage 1: Build the React + TypeScript SPA application
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency manifests
COPY package.json package-lock.json ./

# Install clean production and build dependencies
RUN npm ci

# Copy application source code
COPY . .

# Build production bundle to /app/dist
RUN npm run build

# Stage 2: Serve optimized static assets via Nginx
FROM nginx:1.27-alpine

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled SPA bundle from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check verifying Nginx is serving the root index
HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
