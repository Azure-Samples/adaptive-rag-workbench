FROM node:18-alpine AS build

WORKDIR /app

# Copy package files
COPY package.json ./

# Install ALL dependencies (including dev dependencies needed for build)
RUN npm install

# Copy source code
COPY . .

# Accept build args for environment variables
ARG VITE_API_BASE_URL
ARG VITE_AAD_CLIENT_ID
ARG VITE_AAD_TENANT_ID
ARG VITE_AAD_USER_FLOW
ARG VITE_AAD_AUTHORITY
ARG VITE_AAD_REDIRECT_URI
ARG VITE_API_SCOPE

# Set environment variables for the build
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_AAD_CLIENT_ID=$VITE_AAD_CLIENT_ID
ENV VITE_AAD_TENANT_ID=$VITE_AAD_TENANT_ID
ENV VITE_AAD_USER_FLOW=$VITE_AAD_USER_FLOW
ENV VITE_AAD_AUTHORITY=$VITE_AAD_AUTHORITY
ENV VITE_AAD_REDIRECT_URI=$VITE_AAD_REDIRECT_URI
ENV VITE_API_SCOPE=$VITE_API_SCOPE

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Remove the stock config so our template wins
RUN rm /etc/nginx/conf.d/default.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Rename the template so it does not clash with the deleted file
COPY nginx.conf.template /etc/nginx/templates/api-proxy.conf.template

# Optional banner to show environment variables
RUN printf '#!/bin/sh\necho "Environment variables:"\nenv | grep -E "(API_|VITE_)"\necho "Starting nginx..."\n' \
    > /docker-entrypoint.d/00-print-env.sh && chmod +x /docker-entrypoint.d/00-print-env.sh

# Expose port 80
EXPOSE 80

# Revert to the normal CMD so the entrypoint renders templates
CMD ["nginx", "-g", "daemon off;"]
