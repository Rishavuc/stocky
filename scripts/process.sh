#!/bin/bash
# Use only process IDs that still belong to this checkout and expected module.
eye_process_matches() {
  local eye_pid="$1" eye_pattern="$2" eye_command eye_cwd
  [[ "$eye_pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$eye_pid" 2>/dev/null || return 1
  eye_command=$(ps -p "$eye_pid" -o command= 2>/dev/null) || return 1
  [[ "$eye_command" == *"$eye_pattern"* ]] || return 1
  if command -v lsof >/dev/null 2>&1; then
    eye_cwd=$(lsof -a -p "$eye_pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
    [[ "$eye_cwd" == "$PWD" ]] || return 1
  fi
}
