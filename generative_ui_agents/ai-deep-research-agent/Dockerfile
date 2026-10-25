FROM node:22-slim AS app

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./
COPY scripts/patch-zod.cjs ./scripts/patch-zod.cjs
COPY patches/ ./patches/

# Install dependencies
RUN npm ci --ignore-scripts && npm run patch:zod

# Copy source files
COPY . .

# Build Next.js app
RUN npm run build

# Expose port
EXPOSE 3000

# Start server
CMD ["npm", "start"]
