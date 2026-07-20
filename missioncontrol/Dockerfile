FROM node:20-alpine AS build
WORKDIR /build
COPY missioncontrol/package.json missioncontrol/package-lock.json ./
RUN npm ci
COPY missioncontrol/index.html ./index.html
COPY missioncontrol/commands.html ./commands.html
COPY missioncontrol/plugins/ ./plugins/

FROM nginx:alpine
COPY --from=build /build/index.html /usr/share/nginx/html/index.html
COPY --from=build /build/commands.html /usr/share/nginx/html/commands.html
COPY --from=build /build/plugins/ /usr/share/nginx/html/plugins/
COPY --from=build /build/node_modules/openmct/dist/ /usr/share/nginx/html/dist/
COPY missioncontrol/nginx.conf /etc/nginx/conf.d/default.conf
