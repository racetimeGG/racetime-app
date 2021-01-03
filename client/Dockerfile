FROM node:alpine AS base

# Development runtime
FROM base AS client
WORKDIR /opt/client
RUN yarn install
ENTRYPOINT yarn run dev

