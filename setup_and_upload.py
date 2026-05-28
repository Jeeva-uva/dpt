#!/usr/bin/env python3
"""Wait for the DT instances, authenticate, create projects, upload SBOMs.

Reads the topology from config.py. SBOMs are read from ./sboms/<dept>-<project>.cdx.json
and the minted API keys are written to ./api_keys.json (all relative to this file).
"""
import sys, os, time, json, base64, urllib.request, urllib.error, urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from config import COMPANIES

SBOM_DIR = os.path.join(BASE_DIR, "sboms")
KEYS_FILE = os.path.join(BASE_DIR, "api_keys.json")
MAX_WAIT = 600  # seconds to wait per instance for the API to come up

ALL_PERMISSIONS = [
    "ACCESS_MANAGEMENT", "BOM_UPLOAD", "POLICY_MANAGEMENT",
    "POLICY_VIOLATION_ANALYSIS", "PORTFOLIO_MANAGEMENT",
    "PROJECT_CREATION_UPLOAD", "SYSTEM_CONFIGURATION",
    "TAG_MANAGEMENT", "VIEW_BADGES", "VIEW_POLICY_VIOLATION",
    "VIEW_PORTFOLIO", "VIEW_VULNERABILITY",
    "VULNERABILITY_ANALYSIS", "VULNERABILITY_MANAGEMENT"
]


def api_request(url, method="GET", data=None, headers=None, timeout=30):
    if headers is None:
        headers = {}
    if data is not None and isinstance(data, (dict, list)):
        data = json.dumps(data).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif data is not None and isinstance(data, str):
        data = data.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, body


def wait_for_api(api_url, label):
    print(f"  Waiting for {label} at {api_url}...", end="", flush=True)
    start = time.time()
    while time.time() - start < MAX_WAIT:
        try:
            status, _ = api_request(f"{api_url}/api/version", timeout=5)
            if status == 200:
                print(" READY")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    print(" TIMEOUT!")
    return False


def force_change_password(api_url, old_pw, new_pw):
    data = urllib.parse.urlencode({
        "username": "admin", "password": old_pw,
        "newPassword": new_pw, "confirmPassword": new_pw
    }).encode()
    req = urllib.request.Request(
        f"{api_url}/api/v1/user/forceChangePassword",
        data=data, headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True
    except urllib.error.HTTPError:
        return False


def login(api_url, username, password):
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{api_url}/api/v1/user/login",
        data=data, headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8").strip().strip('"')
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if "FORCE_PASSWORD_CHANGE" in body:
            return "FORCE_PASSWORD_CHANGE"
        return None


def setup_automation_team(api_url, token):
    """Ensure the built-in Automation team has all permissions; return a fresh API key."""
    headers_auth = {"Authorization": f"Bearer {token}"}
    headers_json = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    status, body = api_request(f"{api_url}/api/v1/team", headers=headers_auth)
    if status != 200:
        return None
    teams = json.loads(body)
    auto_team = next((t for t in teams if t["name"] == "Automation"), None)
    if not auto_team:
        return None

    team_uuid = auto_team["uuid"]
    existing_perms = [p["name"] for p in auto_team.get("permissions", [])]
    for perm in ALL_PERMISSIONS:
        if perm not in existing_perms:
            api_request(
                f"{api_url}/api/v1/permission/{perm}/team/{team_uuid}",
                method="POST", headers=headers_json
            )
            print(f"    Added permission: {perm}")

    # Always generate a new key (existing ones are masked and unusable).
    status, body = api_request(
        f"{api_url}/api/v1/team/{team_uuid}/key",
        method="PUT", headers=headers_auth
    )
    if status in (200, 201):
        key_obj = json.loads(body)
        return key_obj.get("key") or key_obj.get("plainKey") or key_obj.get("apiKey")
    print(f"    Key creation response ({status}): {body[:300]}")
    return None


def create_project(api_url, api_key, name, version, description):
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    status, body = api_request(
        f"{api_url}/api/v1/project?name={urllib.parse.quote(name)}&version={urllib.parse.quote(version)}",
        headers={"X-Api-Key": api_key}
    )
    if status == 200:
        for p in json.loads(body):
            if p["name"] == name and p.get("version") == version:
                return p["uuid"]
    data = {"name": name, "version": version, "description": description}
    status, body = api_request(f"{api_url}/api/v1/project", method="PUT", data=data, headers=headers)
    if status in (200, 201):
        return json.loads(body).get("uuid")
    print(f"    Failed to create project {name}: {status} {body[:200]}")
    return None


def upload_sbom(api_url, api_key, project_uuid, sbom_path):
    with open(sbom_path, "rb") as f:
        sbom_b64 = base64.b64encode(f.read()).decode("utf-8")
    data = {"project": project_uuid, "bom": sbom_b64}
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    status, body = api_request(f"{api_url}/api/v1/bom", method="PUT", data=data, headers=headers)
    if status in (200, 201):
        return True
    print(f"    Upload failed: {status} {body[:200]}")
    return False


def main():
    api_keys = {}

    for company_id, company in COMPANIES.items():
        name = company["name"]
        api_url = company["api_url"]
        print(f"\n{'='*60}\n  Setting up: {name}\n{'='*60}")

        if not wait_for_api(api_url, name):
            print(f"  SKIPPING {name} - API not ready")
            continue

        print("  Logging in as admin...")
        token = login(api_url, "admin", company["new_password"])
        if token == "FORCE_PASSWORD_CHANGE" or token is None:
            token = login(api_url, "admin", company["default_password"])
            if token == "FORCE_PASSWORD_CHANGE":
                print("  Force-changing password...")
                force_change_password(api_url, company["default_password"], company["new_password"])
                token = login(api_url, "admin", company["new_password"])
        if not token or token == "FORCE_PASSWORD_CHANGE":
            print(f"  SKIPPING {name} - cannot authenticate")
            continue
        print("  Authenticated!")

        print("  Configuring Automation team permissions...")
        api_key = setup_automation_team(api_url, token)
        if not api_key:
            print(f"  SKIPPING {name} - no API key")
            continue
        api_keys[company_id] = api_key
        print(f"  API Key: {api_key[:8]}...")

        for proj in company["projects"]:
            proj_name = proj["name"]
            print(f"\n  Creating project: {proj_name}")
            proj_uuid = create_project(api_url, api_key, proj_name, proj["version"], proj["description"])
            if not proj_uuid:
                continue
            print(f"    UUID: {proj_uuid}")

            sbom_file = os.path.join(SBOM_DIR, f"{company_id}-{proj_name}.cdx.json")
            if os.path.exists(sbom_file):
                size_kb = os.path.getsize(sbom_file) // 1024
                print(f"    Uploading SBOM: {os.path.basename(sbom_file)} ({size_kb}KB)")
                print("    Upload successful!" if upload_sbom(api_url, api_key, proj_uuid, sbom_file)
                      else "    Upload FAILED")
            else:
                print(f"    SBOM file not found: {sbom_file}")

    with open(KEYS_FILE, "w") as f:
        json.dump(api_keys, f, indent=2)
    print(f"\n\nAPI keys saved to {KEYS_FILE}")
    print("Setup complete!")


if __name__ == "__main__":
    main()
