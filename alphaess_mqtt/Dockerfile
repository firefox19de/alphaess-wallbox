FROM node:22-alpine
WORKDIR /usr/src/app
COPY package*.json ./
ENV NODE_OPTIONS="--max-old-space-size=512"
RUN npm ci --omit=dev
COPY . .
CMD [ "npm", "start" ]
