"""Exercise deployment preflight with a local Azure CLI double, never Azure."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "azure-appservice.sh"
READ_COMMANDS = {
    ("webapp", "config", "show"),
    ("webapp", "config", "appsettings", "list"),
    ("webapp", "show"),
    ("appservice", "plan", "show"),
}
REQUIRED_SETTINGS = [
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "ENTRA_AUDIENCE",
    "SHAREPOINT_DRIVE_ID",
    "SHAREPOINT_FOLDER_ITEM_ID",
    "SHAREPOINT_OUTPUT_DRIVE_ID",
    "SHAREPOINT_OUTPUT_FOLDER_ITEM_ID",
    "DRAFTS_PATH",
    "SHAREPOINT_CACHE_PATH",
]


@pytest.fixture
def run_deployment(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az = bin_dir / "az"
    az.write_text(
        f"#!{sys.executable}\n"
        """import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["AZ_MOCK_LOG"]).open("a") as log:
    log.write(json.dumps(args) + "\\n")
scenario = json.loads(Path(os.environ["AZ_MOCK_SCENARIO"]).read_text())
command = tuple(args[:next(i for i, arg in enumerate(args) if arg.startswith("-"))])
query = args[args.index("--query") + 1] if "--query" in args else None
if command == ("webapp", "config", "show") and query == "linuxFxVersion":
    print(scenario["runtime"])
elif command == ("webapp", "config", "appsettings", "list"):
    if query == "[?value!=''].name":
        print("\\n".join(scenario["setting_names"]))
    else:
        values = {
            "AUTH_MODE": scenario["auth_mode"],
            "KNOWLEDGE_PROVIDER": scenario["provider"],
            "DRAFTS_PATH": scenario["drafts_path"],
            "SHAREPOINT_CACHE_PATH": scenario["cache_path"],
        }
        queries = {f"[?name=='{key}'].value | [0]": value for key, value in values.items()}
        if query not in queries:
            sys.exit("Unexpected app setting query")
        print(queries[query])
elif command == ("webapp", "show") and query == "serverFarmId":
    print("/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Web/serverfarms/test-plan")
elif command == ("appservice", "plan", "show") and query == "sku.capacity":
    print(scenario["instance_count"])
elif command == ("webapp", "show") and query == "defaultHostName":
    print("test-app.example.invalid")
elif command in {
    ("webapp", "update"),
    ("webapp", "config", "set"),
    ("webapp", "config", "appsettings", "set"),
    ("webapp", "deploy"),
}:
    pass
else:
    sys.exit("Unexpected Azure CLI command")
"""
    )
    az.chmod(0o700)
    archive = tmp_path / "app-deploy.zip"
    archive.write_bytes(b"Mock archive; no upload is performed.")
    scenario_file = tmp_path / "scenario.json"
    log = tmp_path / "az-calls.jsonl"

    def run(**overrides):
        scenario = {
            "runtime": "PYTHON|3.12",
            "auth_mode": "entra",
            "provider": "sharepoint",
            "setting_names": [*REQUIRED_SETTINGS, "ENTRA_ALLOWED_ROLES"],
            "drafts_path": "/home/data/ppt-assistant/jobs",
            "cache_path": "/home/data/ppt-assistant/cache",
            "instance_count": "1",
            **overrides,
        }
        scenario_file.write_text(json.dumps(scenario))
        log.write_text("")
        result = subprocess.run(
            ["bash", str(SCRIPT), "test-rg", "test-app", "test-sub", str(archive)],
            env={
                "PATH": f"{bin_dir}{os.pathsep}{os.defpath}",
                "AZ_MOCK_SCENARIO": str(scenario_file),
                "AZ_MOCK_LOG": str(log),
            },
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()]
        commands = [tuple(call[:next(i for i, arg in enumerate(call) if arg.startswith("-"))]) for call in calls]
        mutations = [command for command in commands if command not in READ_COMMANDS]
        return result, mutations

    return run


@pytest.mark.parametrize("setting", ["drafts_path", "cache_path"])
@pytest.mark.parametrize(
    "path",
    [
        "/home/site/wwwroot/volatile-state",
        "/home/../tmp/state",
        "/home/data/ppt-assistant/../../site/wwwroot/volatile-state",
        "/home/data/ppt-assistant/unused/../jobs",
        "/home/data/ppt-assistant-copy/jobs",
        "/home/data/ppt-assistant",
        "/home/data/ppt-assistant/./",
        "/tmp/state",
        "home/data/ppt-assistant/jobs",
        "/home/data/ppt-assistant/jobs\n/home/site/wwwroot/state",
        "/home/data/ppt-assistant/jobs\n",
    ],
)
def test_unsafe_data_path_stops_before_any_azure_mutation(run_deployment, setting, path):
    result, mutations = run_deployment(**{setting: path})

    assert result.returncode == 2, result.stderr
    assert mutations == []
    assert ("DRAFTS_PATH" if setting == "drafts_path" else "SHAREPOINT_CACHE_PATH") in result.stderr
    assert "/home/data/ppt-assistant/" in result.stderr


@pytest.mark.parametrize(
    ("drafts_path", "cache_path"),
    [
        ("/home/data/ppt-assistant/jobs", "/home/data/ppt-assistant/cache"),
        ("/home//data/ppt-assistant/./jobs/", "/home/data/ppt-assistant/nested/cache"),
        ("/home/data/ppt-assistant/job drafts", "/home/data/ppt-assistant/..cache"),
    ],
)
def test_persistent_data_paths_allow_existing_deployment_sequence(run_deployment, drafts_path, cache_path):
    result, mutations = run_deployment(drafts_path=drafts_path, cache_path=cache_path)

    assert result.returncode == 0, result.stderr
    assert mutations == [
        ("webapp", "update"),
        ("webapp", "config", "set"),
        ("webapp", "config", "appsettings", "set"),
        ("webapp", "deploy"),
    ]


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"runtime": "NODE|22-lts"}, "Linux Python 3.11+"),
        ({"auth_mode": "api_key"}, "AUTH_MODE=entra"),
        ({"provider": "local"}, "KNOWLEDGE_PROVIDER=sharepoint"),
        ({"setting_names": [name for name in REQUIRED_SETTINGS if name != "AZURE_CLIENT_SECRET"]}, "AZURE_CLIENT_SECRET"),
        ({"setting_names": REQUIRED_SETTINGS}, "allowed Entra app role or group"),
        ({"instance_count": "2"}, "one-instance plan"),
    ],
)
def test_other_preflight_failures_still_stop_before_mutation(run_deployment, overrides, error):
    result, mutations = run_deployment(**overrides)

    assert result.returncode == 2, result.stderr
    assert mutations == []
    assert error in result.stderr


def test_allowed_group_can_replace_allowed_role(run_deployment):
    result, mutations = run_deployment(setting_names=[*REQUIRED_SETTINGS, "ENTRA_ALLOWED_GROUPS"])

    assert result.returncode == 0, result.stderr
    assert ("webapp", "deploy") in mutations
