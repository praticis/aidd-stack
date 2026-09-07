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

  success "Global .aidd structure provisioned successfully."
}

# ------------------------------------------------------------------------------
# 4. Skills Module
# ------------------------------------------------------------------------------
run_skills() {
  local mode="${1:-}"
  local scope
  local tools=()

  # Prompt for scan skill execution mode
  echo ""
  info "Scan Skill Configuration:"
  echo "  1) Auto Mode (default)"
  echo "  2) Specify Company Name / Context"
  read -r -p "Select an option [1/2, default: 1]: " scan_option

  SCAN_TENANT_VALUE="auto"

  if [[ "$scan_option" == "2" ]]; then
    read -r -p "Enter company/context name [default: auto]: " company_name
    SCAN_TENANT_VALUE="${company_name:-auto}"
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
run_environment() {
  local env_file="$AIDD_DIR/.env"
  local docker_dir="$AIDD_DIR/_docker"

  info "Configuring infrastructure environment at $AIDD_DIR..."

  # Ensure Docker persistence directories exist
  mkdir -p "$docker_dir/obsidian-vault"
  mkdir -p "$docker_dir/qdrant-storage"

  if [ -f "$env_file" ]; then
    info "$env_file already exists — leaving it untouched."
  else
    echo ""
    read -r -p "Enter your workspace path [Default: $HOME/workspace]: " user_workspace
    
    local workspace_path="${user_workspace:-$HOME/workspace}"
    workspace_path="${workspace_path/#\~/$HOME}"

    cat > "$env_file" << EOF
# MCP Git & Container Workspace Mapping
WORKSPACE_PATH=$workspace_path

# Persistent Storage inside ~/.aidd/_docker
OBSIDIAN_VAULT_PATH=$docker_dir/obsidian-vault
QDRANT_STORAGE_PATH=$docker_dir/qdrant-storage

# Service Endpoints
QDRANT_URL=http://localhost:6333
EOF
    success "Created $env_file with WORKSPACE_PATH=$workspace_path"
  fi

  echo ""
  read -r -p "Bring up the Docker Compose stack now? [y/N] " reply
  if [[ "$reply" =~ ^[Yy]$ ]]; then
    info "Starting Docker Compose inside $AIDD_DIR..."
    (cd "$AIDD_DIR" && docker compose up -d --build)
    success "Docker Compose started."
  else
    info "Skipped. Run 'docker compose up -d --build' inside $AIDD_DIR when ready."
  fi

  success "Infrastructure setup completed successfully."
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

  # Locates .git directories up to a maximum depth of 3 folders
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
  printf "\n${BOLD}=== Starting .aidd Global Declarative Setup ===${NC}\n\n"

  printf "${BOLD}=== 1. Provisioning ~/.aidd Structure ===${NC}\n"
  provision_aidd_structure

  echo ""
  printf "${BOLD}=== 2. Installing Skills ===${NC}\n"
  run_skills "$@"

  echo ""
  printf "${BOLD}=== 3. Infrastructure Environment ===${NC}\n"
  run_environment

  echo ""
  printf "${BOLD}=== 4. Distributing MCP Configuration ===${NC}\n"
  distribute_mcp_config

  printf "\n${GREEN}${BOLD}✓ Setup completed successfully at $AIDD_DIR!${NC}\n\n"
}

main "$@"