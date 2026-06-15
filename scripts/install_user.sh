#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage: scripts/install_user.sh [--prefix PATH] [--project PATH] [--skip-mcp] [--skip-skills] [--skills-root PATH] [--install-chat-hook] [--hook-root PATH]

Installs user-local Mythify launchers from this checkout.

Options:
  --prefix PATH        Install launchers under PATH/bin. Default: $HOME/.local
  --project PATH       Initialize Mythify state for that project and print MCP setup.
  --skip-mcp           Install only the mythify CLI wrapper.
  --skip-skills        Do not install Codex-style Mythify chat skills.
  --skills-root PATH   Install chat skills under PATH. Default: $CODEX_HOME/skills or $HOME/.codex/skills
  --install-chat-hook  Install the optional report hook helper script.
  --hook-root PATH     Install hook helpers under PATH. Default: $CODEX_HOME/hooks or $HOME/.codex/hooks
  --help               Show this help.
USAGE
}

fail() {
  printf '%s\n' "[FAIL] $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

pack_dir=""
cleanup_pack_dir() {
  if [ -n "$pack_dir" ] && [ -d "$pack_dir" ]; then
    rm -rf "$pack_dir"
  fi
}
trap cleanup_pack_dir EXIT

prefix="${PREFIX:-$HOME/.local}"
project=""
skip_mcp=0
skip_skills=0
install_chat_hook=0
codex_home="${CODEX_HOME:-$HOME/.codex}"
skills_root="${MYTHIFY_SKILLS_ROOT:-$codex_home/skills}"
hook_root="${MYTHIFY_HOOK_ROOT:-$codex_home/hooks}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      [ "$#" -ge 2 ] || fail "--prefix requires a path"
      prefix="$2"
      shift 2
      ;;
    --project)
      [ "$#" -ge 2 ] || fail "--project requires a path"
      project="$2"
      shift 2
      ;;
    --skip-mcp)
      skip_mcp=1
      shift
      ;;
    --skip-skills)
      skip_skills=1
      shift
      ;;
    --skills-root)
      [ "$#" -ge 2 ] || fail "--skills-root requires a path"
      skills_root="$2"
      shift 2
      ;;
    --install-chat-hook)
      install_chat_hook=1
      shift
      ;;
    --hook-root)
      [ "$#" -ge 2 ] || fail "--hook-root requires a path"
      hook_root="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
bin_dir="$prefix/bin"
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"

[ -f "$repo_root/scripts/mythify.py" ] || fail "Run this from a Mythify checkout"
[ -f "$repo_root/mcp-server/package.json" ] || fail "Missing mcp-server/package.json"

require_command python3
python_bin=$(command -v python3)

mkdir -p "$bin_dir"

cat > "$bin_dir/mythify" <<EOF
#!/usr/bin/env sh
set -eu
exec "$python_bin" "$repo_root/scripts/mythify.py" "\$@"
EOF
chmod 755 "$bin_dir/mythify"

printf '%s\n' "[OK] Installed mythify CLI: $bin_dir/mythify"

if [ "$skip_skills" -eq 0 ]; then
  [ -d "$repo_root/skills" ] || fail "Missing skills directory"
  mkdir -p "$skills_root"
  for skill_dir in "$repo_root"/skills/mythify*; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    destination="$skills_root/$skill_name"
    rm -rf "$destination"
    cp -R "$skill_dir" "$destination"
    printf '%s\n' "[OK] Installed Mythify chat skill: $destination"
  done
fi

if [ "$install_chat_hook" -eq 1 ]; then
  [ -f "$repo_root/scripts/mythify_chat_report_hook.sh" ] || fail "Missing scripts/mythify_chat_report_hook.sh"
  mkdir -p "$hook_root"
  cp "$repo_root/scripts/mythify_chat_report_hook.sh" "$hook_root/mythify-chat-report-hook.sh"
  chmod 755 "$hook_root/mythify-chat-report-hook.sh"
  printf '%s\n' "[OK] Installed chat report hook helper: $hook_root/mythify-chat-report-hook.sh"
fi

if [ "$skip_mcp" -eq 0 ]; then
  require_command node
  require_command npm
  require_command tar
  node_bin=$(command -v node)
  version=$(node -e "console.log(require('$repo_root/mcp-server/package.json').version)")
  install_root="$data_home/mythify/$version"
  mcp_dir="$install_root/mcp-server"

  pack_dir=$(mktemp -d "${TMPDIR:-/tmp}/mythify-pack.XXXXXX")
  tarball=$(CDPATH= cd -- "$repo_root/mcp-server" && npm pack --silent --pack-destination "$pack_dir")
  rm -rf "$mcp_dir"
  mkdir -p "$mcp_dir"
  tar -xzf "$pack_dir/$tarball" -C "$mcp_dir" --strip-components=1
  npm install --prefix "$mcp_dir" --omit=dev --ignore-scripts >/dev/null

  cat > "$bin_dir/mythify-mcp" <<EOF
#!/usr/bin/env sh
set -eu
exec "$node_bin" "$mcp_dir/src/index.js" "\$@"
EOF
  chmod 755 "$bin_dir/mythify-mcp"

  printf '%s\n' "[OK] Installed mythify MCP: $bin_dir/mythify-mcp"
  printf '%s\n' "[OK] Installed MCP package: $mcp_dir"
fi

if [ -n "$project" ]; then
  project_dir=$(CDPATH= cd -- "$project" && pwd -P)
  (cd "$project_dir" && "$bin_dir/mythify" init >/dev/null)
  printf '%s\n' "[OK] Initialized project state: $project_dir/.mythify"

  if [ "$skip_mcp" -eq 0 ]; then
    cat <<EOF
[OK] Codex MCP setup command:
codex mcp add mythify \\
  --env MYTHIFY_DIR=$project_dir/.mythify \\
  --env MYTHIFY_HOST_PLATFORM=codex-desktop \\
  -- $bin_dir/mythify-mcp
EOF
  fi
fi

case ":$PATH:" in
  *":$bin_dir:"*) ;;
  *)
    printf '%s\n' "[WARN] Add $bin_dir to PATH if your shell cannot find mythify."
    ;;
esac
