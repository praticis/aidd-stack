FROM node:24-alpine

WORKDIR /app

RUN npm install -g @mauricio.wolff/mcp-obsidian mcp-proxy --quiet

EXPOSE 3000

CMD ["npx", "mcp-proxy", "--port", "3000", "--", "npx", "@mauricio.wolff/mcp-obsidian@latest", "/vault"]
