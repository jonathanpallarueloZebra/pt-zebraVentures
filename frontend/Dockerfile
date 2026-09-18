# ── Build stage ──
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build -- --configuration=production

# ── Production stage ──
FROM nginx:alpine
COPY --from=build /app/dist/browser /usr/share/nginx/html
# Config extraida a nginx-static.conf: cachea los assets hasheados, obliga a
# revalidar index.html y devuelve 404 real (no index.html) si falta un chunk.
COPY nginx-static.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
