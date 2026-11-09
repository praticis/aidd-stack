# One heavy Docker job at a time on this machine: a corpus, a hold-out, a micro set, the full tests, a dry-run of every
# snapshot. The VM has 10.4 GB and the live stack takes about 3.5, so two of them at once run out of memory, and a time
# or memory measurement is worth nothing next to another job. Source this file, then call, before the first Docker call:
#
#   heavy_lock LABEL [WHO]
#
# It takes ~/.cache/aidd-corpus/heavy.lock, a file with one line, `who pid since label` (the label may hold spaces). If
# another job holds it, the script ends with status 75 and names the holder; with AIDD_HEAVY_WAIT=<seconds> it waits that
# long instead. The lock is the holder's process: it goes within a fraction of a second after that process ends, however it
# ends (a watcher removes it, so `exec`, an error and a kill all release it), and a lock whose process is gone is taken over
# with a notice. A line with no pid in its second field (written by hand, or in another format) is never taken over: it is
# a holder nobody can ask, so remove it by hand when it is stale.
# The file appears with its whole line (it is a hard link to a finished temporary file), so nobody reads it half written.
# A script that a locked script starts does not lock again (AIDD_HEAVY_HELD), which also means a heavy child that outlives
# the script runs unlocked. The lock is the script's process, not the container's: a script killed with SIGKILL frees the
# lock while its container may still run. WHO is the checkout's folder name unless AIDD_AGENT says otherwise, so two chats
# see which one runs. AIDD_HEAVY_LOCK moves the file and AIDD_HEAVY_POLL (seconds, default 5) is the wait's step.
# It is a convention among agents of one user on one machine (kill -0 asks about the user's own processes), not a guard
# against another process: two takers that both judge one stale lock stale in the same instant can both win.

# a process that lives and is no zombie: nobody may have reaped a finished one yet
heavy_alive() {
  kill -0 "$1" 2>/dev/null || return 1
  local state
  if [ -r "/proc/$1/stat" ]; then state=$(sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | cut -c1)
  else state=$(ps -o stat= -p "$1" 2>/dev/null | cut -c1); fi
  [ "$state" != Z ]
}

heavy_lock() {
  [ -z "${AIDD_HEAVY_HELD:-}" ] || return 0
  local label="$1" who="${2:-${AIDD_AGENT:-$(basename "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)")}}"
  local lock="${AIDD_HEAVY_LOCK:-${AIDD_CORPUS_HOME:-$HOME/.cache/aidd-corpus}/heavy.lock}"
  local deadline=$(( $(date +%s) + ${AIDD_HEAVY_WAIT:-0} )) holder pid tries=0 tmp="$lock.$$"
  mkdir -p "$(dirname "$lock")"
  printf '%s %s %s %s\n' "${who// /_}" "$$" "$(date -u +%FT%TZ)" "$label" > "$tmp"
  while ! ln "$tmp" "$lock" 2>/dev/null; do
    if [ ! -e "$lock" ]; then  # released between our try and our look: try again, unless nothing ever works
      tries=$((tries + 1))
      [ "$tries" -lt 50 ] || { rm -f "$tmp"; echo "heavy-lock: cannot create $lock" >&2; exit 74; }
      continue
    fi
    holder=$(cat "$lock" 2>/dev/null || true)
    pid=$(printf '%s' "$holder" | awk '{print $2}')
    if [[ "$pid" =~ ^[0-9]+$ ]] && ! heavy_alive "$pid"; then
      if [ "$(cat "$lock" 2>/dev/null)" = "$holder" ]; then  # still the lock we judged, not a new one
        echo "heavy-lock: the lock of a process that is gone ($holder) is taken over" >&2
        rm -f "$lock"
      fi
      continue
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
      rm -f "$tmp"
      echo "heavy-lock: another heavy job runs: $holder" >&2
      [[ "$pid" =~ ^[0-9]+$ ]] || echo "heavy-lock: that line has no pid, so it is never taken over: remove $lock by hand if it is stale" >&2
      echo "heavy-lock: wait for it, or set AIDD_HEAVY_WAIT=<seconds> to wait here ($lock)" >&2
      exit 75
    fi
    sleep "${AIDD_HEAVY_POLL:-5}"
  done
  rm -f "$tmp"
  export AIDD_HEAVY_HELD=1
  local owner=$$
  ( while heavy_alive "$owner"; do sleep 0.25; done
    [ "$(awk '{print $2}' "$lock" 2>/dev/null)" != "$owner" ] || rm -f "$lock" ) >/dev/null 2>&1 </dev/null &
  disown 2>/dev/null || true
}
