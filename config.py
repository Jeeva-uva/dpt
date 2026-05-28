"""Instance + project topology for the multi-department Dependency-Track demo.

Edit only this file to change which departments/projects exist; the bring-up
(docker-compose.yml), SBOM generation (gen_sboms.sh) and upload (setup_and_upload.py)
all follow what is defined here.
"""
import os

# Public IP/hostname of THIS server. The browser must be able to reach the apiserver
# ports, so this must NOT be "localhost" when accessed remotely.
SERVER_HOST = os.environ.get("SERVER_HOST", "127.0.0.1")

# Password the script sets on the built-in `admin` account on first login.
# Dependency-Track ships as admin/admin and forces a change on first use.
ADMIN_PASSWORD = os.environ.get("DT_ADMIN_PASSWORD", "ChangeMe123!")


def _company(name, api_port, fe_port, projects):
    return {
        "name": name,
        "api_url": f"http://{SERVER_HOST}:{api_port}",
        "frontend_url": f"http://{SERVER_HOST}:{fe_port}",
        "default_password": "admin",      # DT factory default
        "new_password": ADMIN_PASSWORD,   # what we change it to on first login
        "projects": projects,
    }


COMPANIES = {
    "acme": _company("Acme Corp", 18081, 8091, [
        {"name": "express",    "version": "latest", "description": "Express.js - Fast Node.js web framework"},
        {"name": "juice-shop", "version": "latest", "description": "OWASP Juice Shop - intentionally insecure Node.js app"},
    ]),
    "beta": _company("Beta Industries", 8082, 8092, [
        {"name": "fastapi", "version": "latest", "description": "FastAPI - Modern Python web framework"},
        {"name": "flask",   "version": "latest", "description": "Flask - Lightweight Python WSGI framework"},
    ]),
    "gamma": _company("Gamma Solutions", 8083, 8093, [
        {"name": "guava",            "version": "latest", "description": "Google Guava - Core Java libraries"},
        {"name": "spring-petclinic", "version": "latest", "description": "Spring PetClinic - Java sample application"},
    ]),
}
