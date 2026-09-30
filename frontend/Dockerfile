# The Vite dev server for the web service (build-plan.md, "Docker Compose").
FROM node:22-slim

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
