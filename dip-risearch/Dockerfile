FROM node:22-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including tsx)
RUN npm ci

# Copy all source files
COPY . .

# Expose port
EXPOSE 8080

# Run TypeScript with tsx, not node
CMD ["npx", "tsx", "src/api.ts"]
