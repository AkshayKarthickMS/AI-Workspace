FROM node:22-alpine AS dependencies
WORKDIR /app
COPY package.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared/package.json packages/shared/package.json
RUN npm install
FROM dependencies AS build
ARG API_INTERNAL_URL=http://localhost:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
COPY apps/web apps/web
COPY packages/shared packages/shared
RUN npm run build --workspace=@aegisos/web
FROM node:22-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /app
COPY --from=build /app ./
RUN addgroup --system --gid 10001 aegis && adduser --system --uid 10001 aegis && chown -R aegis:aegis /app
USER aegis
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace=@aegisos/web"]
