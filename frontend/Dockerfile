# Stage 1: Build the React app using Vite
FROM node:20-alpine AS build

WORKDIR /app

# Copy dependency configuration and install packages
COPY package*.json ./
RUN npm ci

# Copy all source files and build production distribution
COPY . .
RUN npm run build

# Stage 2: Serve static files with production Nginx
FROM nginx:alpine

# Copy built web app from build stage to Nginx web root
COPY --from=build /app/dist /usr/share/nginx/html

# Replace default Nginx configuration with our routing rules
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Start Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
