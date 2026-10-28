FROM node:22-alpine AS build

WORKDIR /app

RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
ARG VITE_BASE_PATH=/
ARG VITE_API_URL=
ARG VITE_OTEL_EXPORTER_OTLP_ENDPOINT=
ENV VITE_BASE_PATH=${VITE_BASE_PATH} \
    VITE_API_URL=${VITE_API_URL} \
    VITE_OTEL_EXPORTER_OTLP_ENDPOINT=${VITE_OTEL_EXPORTER_OTLP_ENDPOINT}
RUN pnpm build

FROM nginx:1.29-alpine

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
