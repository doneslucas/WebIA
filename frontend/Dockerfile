FROM node:24-alpine
ARG HTTPS_PROXY
ARG NO_PROXY
ENV HTPPS_PROXY=${HTTPS_PROXY}
ENV NO_PROXY=${NO_PROXY}
WORKDIR /app

COPY package*.json ./
RUN npm ci
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
