FROM node:24-alpine

RUN apk add --no-cache git openssh-client

RUN npm install -g @cyanheads/git-mcp-server --quiet

EXPOSE 3000

ENV MCP_TRANSPORT_TYPE=http
ENV MCP_HTTP_PORT=3000
ENV MCP_HTTP_HOST=0.0.0.0
ENV GIT_BASE_DIR=/workspace

# Restricts operations to the /workspace tree (all cloned repositories).
# Commit identity comes from the mounted ~/.gitconfig; optionally, it can be
# set via GIT_USERNAME/GIT_EMAIL in .env if you prefer not to rely on the mount.
CMD ["git-mcp-server"]
