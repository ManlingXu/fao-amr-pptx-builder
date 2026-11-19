#!/usr/bin/env bash
# Compatibility entry point: uses an existing approved application.
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$project_dir/deploy/azure-appservice.sh" "$@"
