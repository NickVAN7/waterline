# The Vite dev server for the web service (build-plan.md, "Docker Compose").
FROM node:22-slim

WORKDIR /app

# Not root (TD-11): the image's `node` user, given the host's user and group IDs (`wl` passes
# them as HOST_UID and HOST_GID), so what Vite writes into the mounted source (its config's
# temporary files) is the developer's. It owns /app and installs the dependencies, so Vite can
# write its cache in node_modules.
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupmod --non-unique --gid "$HOST_GID" node \
    && usermod --non-unique --uid "$HOST_UID" --gid "$HOST_GID" node \
    && chown node:node /app
USER node

# Dependencies first, so a code change doesn't reinstall them.
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci

COPY --chown=node:node . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
