FROM node:20-alpine
WORKDIR /srv/web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
EXPOSE 5203
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
