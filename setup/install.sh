#!/usr/bin/env bash
#
# install.sh — Self-contained declarative setup script.
# Synchronizes template directories and docker assets directly into ~/.aidd,
# manages AI skills, configures global Docker infrastructure, and
# distributes .mcp.json files based on tenant configuration.
#
# Usage:
#   ./install.sh                 # Global skills + ~/.aidd infra setup
#   ./install.sh --project       # Project-scoped skills + ~/.aidd infra setup
#
# Can also be run remotely:
#   curl -fsSL https://raw.githubusercontent.com/praticis/aidd-stack/main/setup/install.sh | bash
#

set -eo pipefail

# ------------------------------------------------------------------------------
# Bootstrap: detect whether this is running from a real local checkout
# or via `curl | bash` (no files on disk). If the latter, clone the
# repository into a temp directory first and continue from there.
# ------------------------------------------------------------------------------
REPO_URL="https://github.com/praticis/aidd-stack.git"

_candidate_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"

if [ -n "$_candidate_script_dir" ] && [ -d "$_candidate_script_dir/../git" ]; then
  # Real checkout: install.sh has its sibling folders (git/, obsidian/,
  # qdrant/, skills/) right there on disk. Use it as-is.
  SCRIPT_DIR="$_candidate_script_dir"
  ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  # No usable local checkout (e.g. curl | bash) — clone the repo into a
  # temp directory and point everything at that instead.
  if ! command -v git &> /dev/null; then
    echo "git is required to install aidd-stack this way. Install git and try again." >&2
    exit 1
  fi
  TMP_CLONE="$(mktemp -d -t aidd-stack.XXXXXX)"
  echo "No local checkout detected — cloning $REPO_URL into $TMP_CLONE..."
  git clone --depth 1 "$REPO_URL" "$TMP_CLONE"
  ROOT_DIR="$TMP_CLONE"
  SCRIPT_DIR="$TMP_CLONE/setup"
fi

AIDD_DIR="$HOME/.aidd"

# Folders to copy from $ROOT_DIR into $AIDD_DIR
SYNC_FOLDERS=(
  "git"
  "obsidian"
  "qdrant"
  "neo4j"
  "indexer"
  "gateway"
)

# Files at the root to copy directly into $AIDD_DIR
ROOT_FILES_TO_COPY=(
  "docker-compose.yml"
  "docker-compose.yaml"
)

# Exception / Exclude patterns (ignored during directory copy)
EXCLUDE_PATTERNS=(
  ".git*"
  ".DS_Store"
  "*.tmp"
  "*.log"
  "node_modules"
  "__pycache__"
)

# Global variable to store current selected tenant across modules
SCAN_TENANT_VALUE="auto"
# Set when this run created a fresh .env (drives the stale-volume check)
ENV_CREATED_NOW=0

# ------------------------------------------------------------------------------
# 2. Output Formatting & Helpers
# ------------------------------------------------------------------------------
BOLD='\033[1m'
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color / Reset

info()    { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
success() { printf "${GREEN}[OK]${NC} %s\n" "$1"; }
warn()    { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$1" >&2; exit 1; }

cleanup() {
  trap - EXIT
  echo ""
  warn "Installation interrupted by user."
  exit 130
}
trap cleanup INT TERM

# Helper function to copy directories with exclusion rules
copy_with_excludes() {
  local src="$1"
  local dest="$2"

  mkdir -p "$dest"

  if command -v rsync &> /dev/null; then
    local rsync_opts=(-a --delete)
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
      rsync_opts+=(--exclude="$pattern")
    done
    rsync "${rsync_opts[@]}" "$src/" "$dest/"
  else
    local tar_opts=()
    for pattern in "${EXCLUDE_PATTERNS[@]}"; do
      tar_opts+=(--exclude="$pattern")
    done
    (cd "$src" && tar "${tar_opts[@]}" -cf - .) | (cd "$dest" && tar -xf -)
  fi
}

# ------------------------------------------------------------------------------
# 3. .aidd Provisioning Engine
# ------------------------------------------------------------------------------
provision_aidd_structure() {
  info "Provisioning global .aidd structure at $AIDD_DIR..."

  mkdir -p "$AIDD_DIR"

  # Sync configured folders from ROOT_DIR
  for folder in "${SYNC_FOLDERS[@]}"; do
    local src_path="$ROOT_DIR/$folder"
    local dest_path="$AIDD_DIR/$folder"

    if [ -d "$src_path" ]; then
      copy_with_excludes "$src_path" "$dest_path"
      printf "  ${GREEN}[synced]${NC} %s -> ~/.aidd/%s\n" "$folder" "$folder"
    else
      printf "  ${YELLOW}[skipped]${NC} %s: source directory not found at %s\n" "$folder" "$src_path"
    fi
  done

  # Copy root files (e.g., docker-compose.yml) from ROOT_DIR
  for file in "${ROOT_FILES_TO_COPY[@]}"; do
    if [ -f "$ROOT_DIR/$file" ]; then
      cp "$ROOT_DIR/$file" "$AIDD_DIR/$file"
      printf "  ${GREEN}[copied]${NC} %s -> ~/.aidd/%s\n" "$file" "$file"
    fi
  done

  # Health check script, runnable from the install dir: ~/.aidd/install-check.sh
  if [ -f "$SCRIPT_DIR/install-check.sh" ]; then
    cp "$SCRIPT_DIR/install-check.sh" "$AIDD_DIR/install-check.sh" && chmod +x "$AIDD_DIR/install-check.sh"
    printf "  ${GREEN}[copied]${NC} install-check.sh -> ~/.aidd/install-check.sh\n"
  fi

  # Host-side client: runs indexer commands in the refresher / indexer containers and manages
  # the refresher (`aidd schedule ...`). Also linked into ~/.local/bin when that exists.
  if [ -f "$SCRIPT_DIR/aidd" ]; then
    cp "$SCRIPT_DIR/aidd" "$AIDD_DIR/aidd" && chmod +x "$AIDD_DIR/aidd"
    printf "  ${GREEN}[copied]${NC} aidd -> ~/.aidd/aidd\n"
    # left by versions that fetched on the host; the image carries its own copy now
    rm -f "$AIDD_DIR/git-askpass.sh"
    if [ -d "$HOME/.local/bin" ] && [ -w "$HOME/.local/bin" ]; then
      ln -sf "$AIDD_DIR/aidd" "$HOME/.local/bin/aidd"
      printf "  ${GREEN}[linked]${NC} ~/.local/bin/aidd\n"
    fi
  fi

  success "Global .aidd structure provisioned successfully."
}

# ------------------------------------------------------------------------------
# 4. Skills Module
# ------------------------------------------------------------------------------
run_skills() {
  local mode="${1:-}"
  local scope
  local tools=()

  # Tenant: on an upgrade the value already lives in ~/.aidd/.env — keep it by default and
  # only offer to change it; the full prompt is for first installs.
  local existing_tenant=""
  if [ -f "$HOME/.aidd/.env" ]; then
    existing_tenant="$(grep -E '^AIDD_TENANT=' "$HOME/.aidd/.env" | head -1 | cut -d= -f2- | tr -d '"')"
  fi
  echo ""
  if [ -n "$existing_tenant" ]; then
    info "Scan Skill Configuration: tenant '$existing_tenant' already configured (~/.aidd/.env)."
    echo "  1) Keep '$existing_tenant'   [default]"
    echo "  2) Change it"
    read -r -p "Select an option [1/2, default: 1]: " keep_tenant </dev/tty
    if [[ "$keep_tenant" == "2" ]]; then
      read -r -p "Enter company/context name (or 'auto'): " company_name </dev/tty
      SCAN_TENANT_VALUE="${company_name:-$existing_tenant}"
    else
      SCAN_TENANT_VALUE="$existing_tenant"
    fi
  else
    info "Scan Skill Configuration:"
    echo "  1) Auto Mode (default)"
    echo "  2) Specify Company Name / Context"
    read -r -p "Select an option [1/2, default: 1]: " scan_option </dev/tty
    SCAN_TENANT_VALUE="auto"
    if [[ "$scan_option" == "2" ]]; then
      read -r -p "Enter company/context name [default: auto]: " company_name </dev/tty
      SCAN_TENANT_VALUE="${company_name:-auto}"
    fi
  fi

  info "Scan skill tenant set to: $SCAN_TENANT_VALUE"

  if [ "$mode" = "--project" ]; then
    scope="project ($(pwd))"
    tools=(
      "Claude Code|.claude|.claude/skills"
      "Antigravity CLI|.agents|.agents/skills"
      "Cursor|.cursor|.cursor/skills"
    )
  else
    scope="global"
    tools=(
      "Claude Code|$HOME/.claude|$HOME/.claude/skills"
      "Antigravity CLI|$HOME/.gemini/config|$HOME/.gemini/config/skills"
      "Cursor|$HOME/.cursor|$HOME/.cursor/skills"
    )
  fi

  # Fallback check: look inside $SCRIPT_DIR/skills first, then $ROOT_DIR/skills
  local skills_src_dir="$SCRIPT_DIR/skills"
  if [ ! -d "$skills_src_dir" ]; then
    skills_src_dir="$ROOT_DIR/skills"
  fi

  info "Installing skills from $skills_src_dir (scope: $scope)..."

  if [ ! -d "$skills_src_dir" ]; then
    warn "Skills directory not found at $skills_src_dir. Skipping skills setup."
    return 0
  fi

  # Directory to store processed/customized skills
  local processed_skills_dir="$AIDD_DIR/processed_skills"
  mkdir -p "$processed_skills_dir"

  for entry in "${tools[@]}"; do
    IFS='|' read -r tool_name marker_dir skills_base <<< "$entry"

    if [ ! -d "$marker_dir" ]; then
      printf "  ${YELLOW}[skipped]${NC} %s: not detected (%s does not exist)\n" "$tool_name" "$marker_dir"
      continue
    fi

    for skill_dir in "$skills_src_dir"/*/; do
      [ -d "$skill_dir" ] || continue

      local skill_name
      skill_name="$(basename "$skill_dir")"
      local source_file="${skill_dir}SKILL.md"

      if [ ! -f "$source_file" ]; then
        continue
      fi

      local target_source="$source_file"

      # Customize scan skill if present
      if [ "$skill_name" = "scan" ]; then
        mkdir -p "$processed_skills_dir/scan"
        target_source="$processed_skills_dir/scan/SKILL.md"

        cp "$source_file" "$target_source"

        if grep -qiE "^(tenant|mode|company):" "$target_source"; then
          sed -i '' -E "s/^(tenant|mode|company):.*/tenant: $SCAN_TENANT_VALUE/i" "$target_source" 2>/dev/null || \
          sed -i -E "s/^(tenant|mode|company):.*/tenant: $SCAN_TENANT_VALUE/i" "$target_source"
        else
          echo -e "---\ntenant: $SCAN_TENANT_VALUE\n---\n$(cat "$target_source")" > "$target_source"
        fi
      fi

      local dest_dir="$skills_base/$skill_name"
      local dest_file="$dest_dir/SKILL.md"

      mkdir -p "$dest_dir"

      if [ -L "$dest_file" ] || [ -f "$dest_file" ]; then
        rm -f "$dest_file"
      fi

      ln -s "$target_source" "$dest_file"
      printf "  ${GREEN}[ok]${NC} %s: %s -> %s\n" "$tool_name" "$skill_name" "$dest_file"
    done
  done

  success "Skills setup completed successfully."
}

# ------------------------------------------------------------------------------
# 5. Infrastructure & Environment (.env)
# ------------------------------------------------------------------------------
# docker-compose.yml treats every variable it reads as required (${VAR:?}).
# When .env predates a new variable, append it with a sane default instead
# of letting compose abort. Existing values are never touched.
random_secret() {
  if command -v openssl &> /dev/null; then openssl rand -hex 24
  elif [ -r /dev/urandom ]; then head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else echo "aidd-$(date +%s)-$$"; fi
}

# Bind-mount sources the containers write to (mirrors, state) and the secret file compose mounts
# must exist before `docker compose up`, owned by the user: Docker would create them as root, and a
# missing secret file aborts compose. An empty token file is valid (no remote fetch).
ensure_runtime_dirs() {
  local token_file
  token_file="$(grep -E '^AIDD_GIT_TOKEN_FILE=' "$AIDD_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
  token_file="${token_file:-$AIDD_DIR/secrets/git-token}"
  local d
  for d in "$AIDD_DIR/mirrors" "$AIDD_DIR/state"; do
    # left by a run under sudo: an empty directory owned by someone else is recreated as yours
    if [ -d "$d" ] && [ ! -O "$d" ]; then
      if rmdir "$d" 2>/dev/null; then printf "  ${YELLOW}[fixed]${NC} %s was owned by another user — recreated as yours\n" "$d"
      else warn "$d is not owned by you and not empty — run: sudo chown -R $(id -u):$(id -g) $d"; fi
    fi
  done
  mkdir -p "$AIDD_DIR/mirrors" "$AIDD_DIR/state" "$(dirname "$token_file")"
  chmod 700 "$(dirname "$token_file")" 2>/dev/null || true
  [ -e "$token_file" ] || { : > "$token_file" && chmod 600 "$token_file"; }
}

# Manifests generated by earlier versions say `fetch: false` because the host wrapper fetched. The
# refresher now fetches into its own mirrors, so the generated block flips to `fetch: true`.
# Hand-written manifests (without the generated comment) are left alone.
migrate_atlas_manifest() {
  local manifest="$AIDD_DIR/atlas.yaml"
  [ -f "$manifest" ] && grep -q 'git fetch is NOT part of indexing' "$manifest" || return 0
  local tmp; tmp="$(mktemp)"
  awk '
    /# git fetch is NOT part of indexing/ { print "        # the refresher fetches into its own mirrors (your clones are read-only to it)"; skip=1; next }
    skip && /^ *#/ { next }
    skip && /fetch: false/ { sub(/fetch: false/, "fetch: true"); skip=0 }
    { print }
  ' "$manifest" > "$tmp" && cp "$tmp" "$manifest" && rm -f "$tmp"
  printf "  ${GREEN}[migrated]${NC} atlas.yaml: local sources fetch into the refresher mirrors (fetch: true)\n"
}

ensure_env_defaults() {
  local env_file="$1"
  local key value current
  local neo4j_password
  if command -v openssl &> /dev/null; then
    neo4j_password="$(openssl rand -hex 12)"
  else
    neo4j_password="aidd-$(date +%s)"
  fi

  local defaults=(
    "OBSIDIAN_VAULT_PATH=$AIDD_DIR/_docker/obsidian-vault"
    "NEO4J_USER=neo4j"
    "NEO4J_PASSWORD=$neo4j_password"
    "NEO4J_DATABASE=atlas"
    "NEO4J_HEAP=1G"
    "NEO4J_PAGECACHE=512M"
    "QDRANT_API_KEY=$(random_secret)"
    "AIDD_UID=$(id -u)"
    "AIDD_GID=$(id -g)"
    "AIDD_GIT_TOKEN_FILE=$AIDD_DIR/secrets/git-token"
    "AIDD_REFRESH_INTERVAL_MINUTES=15"
  )

  for kv in "${defaults[@]}"; do
    key="${kv%%=*}"
    value="${kv#*=}"
    if ! grep -q "^${key}=" "$env_file"; then
      printf "\n%s=%s\n" "$key" "$value" >> "$env_file"
      printf "  ${GREEN}[added]${NC} %s to %s\n" "$key" "$env_file"
      [ "$key" = "NEO4J_PASSWORD" ] && info "Generated a random Neo4j password — Browser login at http://localhost:7474 uses NEO4J_USER/NEO4J_PASSWORD from $env_file."
      [ "$key" = "QDRANT_API_KEY" ] && info "Qdrant now requires an API key (QDRANT_API_KEY in $env_file) — the MCP container receives it from compose."
    fi
  done

  # AIDD_TENANT is different: it always follows the choice made in step 2 of
  # this run, so the .env, the skills' frontmatter and the containers agree.
  if grep -q "^AIDD_TENANT=" "$env_file"; then
    current="$(grep "^AIDD_TENANT=" "$env_file" | cut -d'=' -f2-)"
    if [ "$current" != "$SCAN_TENANT_VALUE" ]; then
      sed -i.bak -E "s/^AIDD_TENANT=.*/AIDD_TENANT=$SCAN_TENANT_VALUE/" "$env_file" && rm -f "$env_file.bak"
      printf "  ${YELLOW}[updated]${NC} AIDD_TENANT: %s -> %s\n" "$current" "$SCAN_TENANT_VALUE"
    fi
  else
    printf "\nAIDD_TENANT=%s\n" "$SCAN_TENANT_VALUE" >> "$env_file"
    printf "  ${GREEN}[added]${NC} AIDD_TENANT=%s to %s\n" "$SCAN_TENANT_VALUE" "$env_file"
  fi
}

run_environment() {
  local env_file="$AIDD_DIR/.env"
  local docker_dir="$AIDD_DIR/_docker"

  info "Configuring infrastructure environment at $AIDD_DIR..."

  # Ensure Docker persistence directories exist
  mkdir -p "$docker_dir/obsidian-vault"
  mkdir -p "$docker_dir/qdrant-storage"

  if [ -f "$env_file" ]; then
    info "$env_file already exists — keeping existing values, adding missing keys only."
    ensure_env_defaults "$env_file"
  else
    echo ""
    read -r -p "Enter your workspace path [Default: $HOME/workspace]: " user_workspace </dev/tty

    local workspace_path="${user_workspace:-$HOME/workspace}"
    workspace_path="${workspace_path/#\~/$HOME}"

    # Random Neo4j password (Neo4j requires >= 8 chars). Falls back to a
    # time-based value when neither openssl nor /dev/urandom is available.
    local neo4j_password
    if command -v openssl &> /dev/null; then
      neo4j_password="$(openssl rand -hex 12)"
    elif [ -r /dev/urandom ]; then
      neo4j_password="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    else
      neo4j_password="aidd-$(date +%s)"
    fi

    cat > "$env_file" << EOF
# MCP Git & Container Workspace Mapping
WORKSPACE_PATH=$workspace_path

# Tenant chosen during setup (source of truth: this script, step 2).
# 'auto' = derive from the folder below WORKSPACE_PATH (<workspace>/<tenant>/<repo>);
# any other value is used as-is by skills, indexer and MCPs. Never left unset.
AIDD_TENANT=$SCAN_TENANT_VALUE

# Persistent Storage inside ~/.aidd/_docker
OBSIDIAN_VAULT_PATH=$docker_dir/obsidian-vault
QDRANT_STORAGE_PATH=$docker_dir/qdrant-storage

# Service Endpoints
QDRANT_URL=http://localhost:6333

# Containers that write to your files (workspace, vault, mirrors) run as you, so nothing ends up
# owned by root.
AIDD_UID=$(id -u)
AIDD_GID=$(id -g)

# Qdrant API key — required by Qdrant, passed to the MCP container by compose.
QDRANT_API_KEY=$(random_secret)

# Neo4j (code graph) — the ONLY place these credentials are defined.
# docker-compose.yml refuses to start without NEO4J_PASSWORD.
# The official image only supports 'neo4j' as the initial user.
# Changing the password after first start: 'docker compose down -v'
# (wipes the graph — dev only) or ALTER USER via cypher-shell.
NEO4J_USER=neo4j
NEO4J_PASSWORD=$neo4j_password
# Single user database (Community Edition); name is fixed at first start.
NEO4J_DATABASE=atlas
NEO4J_HEAP=1G
NEO4J_PAGECACHE=512M

# Continuous update — the refresher container (step 6 of install.sh). It fetches the remotes
# into its own mirrors with a READ-ONLY PAT stored in the file below (chmod 600), never in this
# .env. An empty file is valid: the mirrors then follow your own fetches.
AIDD_GIT_TOKEN_FILE=$AIDD_DIR/secrets/git-token
AIDD_REFRESH_INTERVAL_MINUTES=15
EOF
    ENV_CREATED_NOW=1
    success "Created $env_file with WORKSPACE_PATH=$workspace_path"
    info "Generated a random Neo4j password — see NEO4J_PASSWORD in $env_file (Browser login at http://localhost:7474)."
  fi

  # The manifest must exist BEFORE the first `docker compose up`: it is bind-mounted
  # into the indexer as a file, and Docker turns a missing bind source into a directory.
  write_atlas_manifest
  migrate_atlas_manifest
  ensure_runtime_dirs

  # Named volumes outlive ~/.aidd. A brand-new .env carries a brand-new Neo4j
  # password, but an old neo4j_data volume still holds the previous one — the
  # server would start and every connection would fail with "unauthorized".
  if [ "${ENV_CREATED_NOW:-0}" = "1" ]; then
    local old_volumes
    old_volumes="$(docker volume ls -q 2>/dev/null | grep -E '^praticis-aidd_(neo4j|qdrant)_data$' || true)"
    if [ -n "$old_volumes" ]; then
      echo ""
      warn "Data volumes from a previous installation exist:"
      echo "$old_volumes" | sed 's/^/    /'
      warn "The new NEO4J_PASSWORD in .env will NOT match the password stored in the old neo4j_data volume."
      read -r -p "Remove these volumes for a clean start? (all indexed data is lost) [Y/n] " wipe </dev/tty
      if [[ ! "$wipe" =~ ^[Nn]$ ]]; then
        (cd "$AIDD_DIR" && docker compose down -v --remove-orphans >/dev/null 2>&1 || true)
        echo "$old_volumes" | xargs -r docker volume rm >/dev/null 2>&1 || true
        success "Old volumes removed."
      else
        warn "Keeping old volumes — set NEO4J_PASSWORD in $env_file to the previous password, or expect authentication failures."
      fi
    fi
  fi

  echo ""
  info "Infrastructure:"
  echo "  1) Build and start the Docker Compose stack now   [default]"
  echo "  2) Skip — start later with:  cd $AIDD_DIR && docker compose --profile tools build && docker compose up -d"
  read -r -p "Select an option [1/2, default: 1]: " reply </dev/tty
  if [[ "${reply:-1}" != "2" ]]; then
    info "Starting Docker Compose inside $AIDD_DIR..."
    # everything but the refresher: step 4 (bootstrap) runs first, step 6 starts the refresher
    if (cd "$AIDD_DIR" && docker compose --profile tools build && docker compose up -d --remove-orphans --scale refresher=0); then
      success "Docker Compose started (indexer image built as well; the refresher starts in step 6)."
    else
      warn "docker compose up failed. Last Neo4j log lines (most common culprit — APOC download or memory):"
      (cd "$AIDD_DIR" && docker compose logs --tail 40 neo4j 2>/dev/null | sed 's/^/    /')
      warn "Full logs: cd $AIDD_DIR && docker compose logs neo4j   (compose commands must run from $AIDD_DIR, where .env lives)"
      error "Infrastructure did not come up — fix the cause above and re-run this script."
    fi
  else
    info "Skipped. Run 'docker compose --profile tools build && docker compose up -d' inside $AIDD_DIR when ready."
  fi

  success "Infrastructure setup completed successfully."
}

# ------------------------------------------------------------------------------
# 5b. Atlas manifest (atlas.yaml) & bootstrap indexing
# ------------------------------------------------------------------------------
# Writes ~/.aidd/atlas.yaml from the tenant chosen in step 2 and the workspace
# path in .env, then offers to index the local workspace right away.
# Tenant layout mirrors the skills: `auto` = every sub-folder of the workspace
# is a tenant; a fixed value = that folder (or the workspace root if absent).
write_atlas_manifest() {
  local manifest="$AIDD_DIR/atlas.yaml"
  local env_file="$AIDD_DIR/.env"
  local workspace_path
  workspace_path="$(grep "^WORKSPACE_PATH=" "$env_file" | cut -d'=' -f2-)"

  if [ -f "$manifest" ]; then
    info "$manifest already exists — leaving it untouched (edit it, then 'aidd plan')."
    return 0
  fi

  local tenants=()
  if [ "$SCAN_TENANT_VALUE" = "auto" ]; then
    for d in "$workspace_path"/*/; do
      [ -d "$d" ] || continue
      local name; name="$(basename "$d")"
      [[ "$name" == .* ]] && continue
      # a tenant folder holds repositories, not a repository itself
      [ -d "$d/.git" ] && continue
      tenants+=("$name")
    done
    if [ ${#tenants[@]} -eq 0 ]; then
      warn "tenant=auto but no tenant folders found under $workspace_path (expected <workspace>/<tenant>/<repo>). Writing an empty template."
    fi
  else
    tenants+=("$SCAN_TENANT_VALUE")
  fi

  {
    echo "# atlas.yaml — what the aidd indexer feeds into atlas."
    echo "# Generated by setup/install.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ). Reference: indexer/atlas.example.yaml"
    echo "# Preview with: docker compose run --rm indexer plan"
    echo ""
    echo "tenants:"
    for t in "${tenants[@]}"; do
      local path="/workspace/$t"
      # fixed tenant whose folder does not exist: repos live at the workspace root
      [ "$SCAN_TENANT_VALUE" != "auto" ] && [ ! -d "$workspace_path/$t" ] && path="/workspace"
      cat <<YAML
  $t:
    sources:
      - type: local
        path: $path
        include: ["*"]
        exclude: []
        # the refresher fetches into its own mirrors (your clones are read-only to it)
        fetch: true
    refs:
      always: ["main", "master", "develop"]
      patterns: []
      active:
        max_age_days: 14
        max_per_repo: 5
        exclude: ["dependabot/*", "renovate/*", "docs/*", "ci/*", "cd/*", "pipeline/*"]
      gc_ephemeral_after_days: 30
    areas: {}
    schedule: ""
YAML
    done
  } > "$manifest"
  success "Wrote $manifest (tenants: ${tenants[*]:-none})."
}

run_atlas_bootstrap() {
  write_atlas_manifest   # no-op when step 3 already wrote it

  # Guard against the bind-mount gotcha (a directory where the manifest should be).
  if [ -d "$AIDD_DIR/atlas.yaml" ]; then
    warn "$AIDD_DIR/atlas.yaml is a DIRECTORY (created by docker compose before the file existed)."
    warn "Fix: cd $AIDD_DIR && docker compose down && rmdir atlas.yaml && re-run this script."
    return 0
  fi

  # (not `compose ps | grep -q`: with pipefail, grep closing the pipe early fails the whole check)
  if [ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' aidd-core-neo4j 2>/dev/null)" != "healthy" ]; then
    info "Neo4j is not running — skipping bootstrap. Later: cd $AIDD_DIR && docker compose run --rm indexer bootstrap"
    return 0
  fi

  echo ""
  local def=1
  [ "${AIDD_UPGRADE:-0}" = 1 ] && def=2
  info "Atlas bootstrap — populate the code graph with this tenant's repositories:"
  if [ "$def" = 1 ]; then
    echo "  1) Index the local workspace now (repos already cloned)   [default]"
    echo "  2) Skip — run '$AIDD_DIR/aidd bootstrap' later"
  else
    echo "  1) Re-index the local workspace now (only changed snapshots are rewritten)"
    echo "  2) Skip — the graph is already populated; the refresher keeps it current   [default]"
  fi
  echo "  (remote providers — GitHub/GitLab/Azure DevOps — arrive in a later phase; see atlas.yaml comments)"
  read -r -p "Select an option [1/2, default: $def]: " opt </dev/tty
  if [[ "${opt:-$def}" == "2" ]]; then
    info "Skipped."
    if [ "${AIDD_UPGRADE:-0}" = 1 ]; then
      # snapshots are already in the graph; (re)build the cross-repo CONSUMES/CALLED_FROM edges
      # with the current linker — cheap, and the refresher only links when something changed
      info "Linking HTTP calls to endpoints across repositories (aidd link) ..."
      "$AIDD_DIR/aidd" link || warn "Linker failed — see output above; later: $AIDD_DIR/aidd link"
    fi
    return 0
  fi
  echo ""
  info "Computing the indexing plan from $AIDD_DIR/atlas.yaml (local refs as cloned — no git fetch at install time) ..."
  if ! AIDD_NO_FETCH=1 "$AIDD_DIR/aidd" plan; then
    warn "Could not compute the plan — see output above. Later: $AIDD_DIR/aidd plan"
    return 0
  fi
  echo ""
  read -r -p "Index everything listed above into atlas? [Y/n] " go </dev/tty
  if [[ "$go" =~ ^[Nn]$ ]]; then
    info "Skipped. Later: $AIDD_DIR/aidd bootstrap"
    return 0
  fi
  # plan already fetched a moment ago — skip the second host fetch
  AIDD_NO_FETCH=1 "$AIDD_DIR/aidd" bootstrap --yes --quiet-plan \
    || warn "Bootstrap finished with errors — see output above; '$AIDD_DIR/aidd status' shows what landed."
}

# ------------------------------------------------------------------------------
# 5c. Continuous update — the refresher container (+ optional read-only PAT)
# ------------------------------------------------------------------------------
# Installation indexes what is cloned. Keeping atlas current is the refresher's job
# (docker-compose.yml): it syncs every repo into its own mirror and re-indexes what changed.
# With a read-only PAT it also fetches the remotes (what the team pushed); without one the mirrors
# follow your own fetches. Reconfigure later with `aidd schedule install`.
run_continuous_update() {
  local env_file="$AIDD_DIR/.env"
  local token_file
  token_file="$(grep -E '^AIDD_GIT_TOKEN_FILE=' "$env_file" 2>/dev/null | head -1 | cut -d= -f2-)"
  token_file="${token_file:-$AIDD_DIR/secrets/git-token}"
  ensure_runtime_dirs

  echo ""
  info "Continuous update: the refresher container re-indexes what changed every few minutes."
  local had_old_scheduler=0
  { [ -f "$HOME/.config/systemd/user/aidd-refresh.timer" ] || crontab -l 2>/dev/null | grep '# aidd-atlas-refresh' >/dev/null; } && had_old_scheduler=1
  [ "$had_old_scheduler" = 1 ] && info "A host scheduler from an earlier version exists — it is replaced by the container (removed now)."

  if [ -s "$token_file" ]; then
    info "Read-only token present at $token_file — kept (empty the file to stop remote fetches)."
  else
    echo "  Optional: a READ-ONLY token (GitHub fine-grained PAT, 'Contents: read' on the organization's"
    echo "  repositories) lets the refresher see what the team pushed, not only what you fetched."
    echo "  Your personal ssh key is never used by it."
    read -r -s -p "Read-only PAT (input hidden; leave empty to skip): " pat </dev/tty
    echo ""
    if [ -n "$pat" ]; then
      printf '%s\n' "$pat" > "$token_file" && chmod 600 "$token_file"
      unset pat
      success "Token stored at $token_file (600), mounted read-only into the refresher as a file."
    else
      info "No token — the refresher syncs from your clones; add one later in $token_file + 'aidd schedule install'."
    fi
  fi

  local current every
  current="$(grep -E '^AIDD_REFRESH_INTERVAL_MINUTES=' "$env_file" | head -1 | cut -d= -f2-)"
  read -r -p "Refresh interval in minutes [default: ${current:-15}]: " every </dev/tty
  every="${every:-${current:-15}}"
  if grep -q '^AIDD_REFRESH_INTERVAL_MINUTES=' "$env_file"; then
    sed -i.bak -E "s/^AIDD_REFRESH_INTERVAL_MINUTES=.*/AIDD_REFRESH_INTERVAL_MINUTES=$every/" "$env_file" && rm -f "$env_file.bak"
  else
    printf '\nAIDD_REFRESH_INTERVAL_MINUTES=%s\n' "$every" >> "$env_file"
  fi

  if "$AIDD_DIR/aidd" schedule install; then
    success "Refresher running. Status: $AIDD_DIR/aidd schedule status   Logs: $AIDD_DIR/aidd logs"
  else
    warn "Refresher not started — see the message above; retry with: $AIDD_DIR/aidd schedule install"
  fi
}

# ------------------------------------------------------------------------------
# 6. MCP Config Distribution Module
# ------------------------------------------------------------------------------
distribute_mcp_config() {
  local mcp_source="$SCRIPT_DIR/.mcp.json"
  if [ ! -f "$mcp_source" ]; then
    mcp_source="$ROOT_DIR/.mcp.json"
  fi

  if [ ! -f "$mcp_source" ]; then
    warn "MCP template file not found at setup/.mcp.json or .mcp.json. Skipping distribution."
    return 0
  fi

  local env_file="$AIDD_DIR/.env"
  if [ ! -f "$env_file" ]; then
    warn "Environment file $env_file not found. Cannot resolve WORKSPACE_PATH."
    return 0
  fi

  # Extract WORKSPACE_PATH from .env file
  local workspace_path
  workspace_path="$(grep "^WORKSPACE_PATH=" "$env_file" | cut -d'=' -f2-)"

  if [ -z "$workspace_path" ] || [ ! -d "$workspace_path" ]; then
    warn "Target workspace directory '$workspace_path' does not exist. Skipping .mcp.json distribution."
    return 0
  fi

  echo ""
  info "Distributing .mcp.json across git repositories (Tenant: $SCAN_TENANT_VALUE)..."

  local search_base="$workspace_path"
  if [ "$SCAN_TENANT_VALUE" != "auto" ] && [ -d "$workspace_path/$SCAN_TENANT_VALUE" ]; then
    search_base="$workspace_path/$SCAN_TENANT_VALUE"
  fi

  # NEW: also drop a copy at the workspace root itself. Skills like
  # business-refine intentionally run from the workspace root (they
  # need a cross-project view, not a single-project one), and Claude
  # Code only reads .mcp.json from the exact directory it's launched
  # from — it does not search upward through parent directories.
  cp "$mcp_source" "$workspace_path/.mcp.json"
  printf "  ${GREEN}[copied]${NC} .mcp.json -> %s/.mcp.json (workspace root)\n" "$workspace_path"

  find "$search_base" -maxdepth 3 -type d -name ".git" 2>/dev/null | while read -r git_dir; do
    local proj_dir
    proj_dir="$(dirname "$git_dir")"

    cp "$mcp_source" "$proj_dir/.mcp.json"
    printf "  ${GREEN}[copied]${NC} .mcp.json -> %s/.mcp.json\n" "$proj_dir"
  done

  success ".mcp.json files distributed across git projects successfully."
}

# ------------------------------------------------------------------------------
# 7. Main Execution
# ------------------------------------------------------------------------------
main() {
  # Everything here is per user (~/.aidd, skills, .mcp.json, the uid the containers run as).
  # Under sudo, AIDD_UID becomes 0 and new directories belong to root — the containers then
  # cannot write to them (Docker Desktop writes as you).
  if [ "$(id -u)" = "0" ] && [ "${AIDD_ALLOW_ROOT:-0}" != "1" ]; then
    error "Do not run install.sh as root/sudo — run it as your user: ${0}  (docker must work without sudo; on Linux add yourself to the 'docker' group). A root-only host: AIDD_ALLOW_ROOT=1."
  fi
  # Upgrade vs first install: an existing ~/.aidd/.env means the stack was configured before,
  # so the interactive steps default to "keep / skip" instead of "configure / index".
  AIDD_UPGRADE=0
  [ -f "$AIDD_DIR/.env" ] && AIDD_UPGRADE=1
  printf "\n${BOLD}=== Starting .aidd Global Declarative Setup ===${NC}\n\n"
  [ "$AIDD_UPGRADE" = 1 ] && info "Existing installation detected at $AIDD_DIR — running as an upgrade (defaults keep what is already configured)."

  printf "${BOLD}=== 1. Provisioning ~/.aidd Structure ===${NC}\n"
  provision_aidd_structure

  echo ""
  printf "${BOLD}=== 2. Installing Skills ===${NC}\n"
  run_skills "$@"

  echo ""
  printf "${BOLD}=== 3. Infrastructure Environment ===${NC}\n"
  run_environment

  echo ""
  printf "${BOLD}=== 4. Atlas Bootstrap ===${NC}\n"
  run_atlas_bootstrap

  echo ""
  printf "${BOLD}=== 5. Distributing MCP Configuration ===${NC}\n"
  distribute_mcp_config

  echo ""
  printf "${BOLD}=== 6. Continuous Update (refresher) ===${NC}\n"
  run_continuous_update

  printf "\n${GREEN}${BOLD}✓ Setup completed successfully at $AIDD_DIR!${NC}\n\n"
}

main "$@"