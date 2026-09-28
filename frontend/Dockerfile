FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Next.js inlines NEXT_PUBLIC_* variables into the client bundle at build
# time, not read at runtime - so they must be supplied as build args, not
# just regular container env vars. Render (and plain `docker build
# --build-arg`) both pass these through.
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}

RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

# CLERK_SECRET_KEY (server-side only, never inlined into the client bundle)
# is read at request time, so it's passed as a normal runtime env var -
# no ARG/build-time handling needed for it.
CMD ["sh", "-c", "npx next start -p ${PORT:-3000}"]
