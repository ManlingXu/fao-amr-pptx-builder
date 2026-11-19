#!/usr/bin/env bash
# Deploy only to an existing CSI-approved Linux Python app.
set -euo pipefail
umask 077

if (( $# < 3 || $# > 4 )); then
  printf 'Usage: bash deploy/azure-appservice.sh RESOURCE_GROUP APP_NAME SUBSCRIPTION_ID [SOURCE_ZIP]\n' >&2
  exit 2
fi
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
resource_group=$1
app_name=$2
subscription_id=$3
archive=${4:-"$project_dir/build/app-deploy.zip"}
command -v az >/dev/null || { printf 'Install Azure CLI and sign in to the approved subscription.\n' >&2; exit 2; }
test -r "$archive" || { printf 'Build the source ZIP with python scripts/make_deploy_zip.py first.\n' >&2; exit 2; }

target=(--resource-group "$resource_group" --name "$app_name" --subscription "$subscription_id")
runtime=$(az webapp config show "${target[@]}" --query linuxFxVersion -o tsv)
case "$runtime" in
  "PYTHON|3.11"|"PYTHON|3.12"|"PYTHON|3.13"|"PYTHON|3.14") ;;
  *) printf 'Use an existing Linux Python 3.11+ app; found runtime: %s\n' "$runtime" >&2; exit 2 ;;
esac

auth_mode=$(az webapp config appsettings list "${target[@]}" --query "[?name=='AUTH_MODE'].value | [0]" -o tsv)
provider=$(az webapp config appsettings list "${target[@]}" --query "[?name=='KNOWLEDGE_PROVIDER'].value | [0]" -o tsv)
if [[ "$auth_mode" != entra || "$provider" != sharepoint ]]; then
  printf 'First configure AUTH_MODE=entra and KNOWLEDGE_PROVIDER=sharepoint using .env.production.example.\n' >&2
  exit 2
fi
configured_names=$(az webapp config appsettings list "${target[@]}" --query "[?value!=''].name" -o tsv)
has_setting() { [[ $'\n'"$configured_names"$'\n' == *$'\n'"$1"$'\n'* ]]; }
for setting in AZURE_TENANT_ID AZURE_CLIENT_ID AZURE_CLIENT_SECRET ENTRA_AUDIENCE SHAREPOINT_DRIVE_ID SHAREPOINT_FOLDER_ITEM_ID SHAREPOINT_OUTPUT_DRIVE_ID SHAREPOINT_OUTPUT_FOLDER_ITEM_ID DRAFTS_PATH SHAREPOINT_CACHE_PATH; do
  has_setting "$setting" || { printf 'Missing nonblank application setting: %s\n' "$setting" >&2; exit 2; }
done
if ! has_setting ENTRA_ALLOWED_ROLES && ! has_setting ENTRA_ALLOWED_GROUPS; then
  printf 'Configure an allowed Entra app role or group for the pilot audience.\n' >&2
  exit 2
fi
is_persistent_data_path() {
  local path=$1 normalized='' component
  local -a components
  [[ "$path" == /* && "$path" != *[[:cntrl:]]* ]] || return 1
  IFS=/ read -r -a components <<< "$path"
  for component in "${components[@]}"; do
    case "$component" in
      ''|.) ;;
      # Reject traversal outright; local realpath cannot resolve remote symlinks.
      ..) return 1 ;;
      *) normalized+="/$component" ;;
    esac
  done
  [[ "$normalized" == /home/data/ppt-assistant/* ]]
}
for setting in DRAFTS_PATH SHAREPOINT_CACHE_PATH; do
  # Preserve value newlines; remove only the CLI's output line ending.
  setting_path=$(az webapp config appsettings list "${target[@]}" --query "[?name=='$setting'].value | [0]" -o tsv && printf '.')
  setting_path=${setting_path%.}
  setting_path=${setting_path%$'\n'}
  if ! is_persistent_data_path "$setting_path"; then
    printf '%s must be an absolute child path beneath /home/data/ppt-assistant/ without .. components or control characters.\n' "$setting" >&2
    exit 2
  fi
done

plan_id=$(az webapp show "${target[@]}" --query serverFarmId -o tsv)
instance_count=$(az appservice plan show --ids "$plan_id" --subscription "$subscription_id" --query sku.capacity -o tsv)
if [[ "$instance_count" != 1 ]]; then
  printf 'This pilot requires a one-instance plan; ask CSI to provide a dedicated compatible app.\n' >&2
  exit 2
fi

printf 'Deploying to approved existing app: %s (resource group %s).\n' "$app_name" "$resource_group"
az webapp update "${target[@]}" --https-only true -o none
az webapp config set "${target[@]}" --always-on true --startup-file 'python -m uvicorn presentation_search.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-proxy-headers' -o none
az webapp config appsettings set "${target[@]}" --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true -o none
az webapp deploy "${target[@]}" --src-path "$archive" --type zip -o none
host=$(az webapp show "${target[@]}" --query defaultHostName -o tsv)
printf 'Deployment command finished. Verify https://%s/health, then run the CSI acceptance checks.\n' "$host"
