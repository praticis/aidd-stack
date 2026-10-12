# Versions are pinned (base image and packages) and the server runs from the installed copy:
# nothing is downloaded from npm when the container starts.
FROM node:24.21.0-alpine

WORKDIR /app

RUN npm install -g @mauricio.wolff/mcp-obsidian@0.8.2 mcp-proxy@6.7.16 --quiet

EXPOSE 3000

CMD ["mcp-proxy", "--port", "3000", "--", "mcp-obsidian", "/vault"]
