FROM node:20-alpine

WORKDIR /app

# 의존성 먼저 — 캐시 효율성.
COPY package.json ./
RUN npm install --no-audit --no-fund

# 소스.
COPY tsconfig.json next.config.mjs next-env.d.ts ./
COPY src ./src

EXPOSE 3000

# MVP는 dev 서버로 띄운다 (HMR + 빠른 기동).
CMD ["npm", "run", "dev"]
