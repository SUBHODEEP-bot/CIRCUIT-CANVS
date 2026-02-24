import os
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    request,
    send_from_directory,
)
from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "circuit-canvas" / "dist"

# Load environment from the frontend .env so we can reuse Supabase settings
env_path = BASE_DIR / "circuit-canvas" / ".env"
if env_path.exists():
    load_dotenv(env_path)

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "https://jbcmsjhukioowvpivosy.supabase.co")
SUPABASE_KEY = os.getenv(
    "VITE_SUPABASE_PUBLISHABLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpiY21zamh1a2lvb3d2cGl2b3N5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE4MzgwODMsImV4cCI6MjA4NzQxNDA4M30.zDhxR6A87Fu7UJUljfvh2nry3a4UOJh243mw7WNCcOk",
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
# Optional service role key for server-side admin mutations
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE")

REST_URL = f"{SUPABASE_URL}/rest/v1"
AUTH_URL = f"{SUPABASE_URL}/auth/v1"
STORAGE_URL = f"{SUPABASE_URL}/storage/v1"

ACCESS_COOKIE = "sb_access_token"
REFRESH_COOKIE = "sb_refresh_token"

# Admin credentials must be provided via environment variables for security.
# If not provided, admin login is disabled.
ADMIN_NAME = os.getenv("ADMIN_NAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_COOKIE = "cf_is_admin"
ADMIN_ENABLED = bool(ADMIN_NAME and ADMIN_PASSWORD)

# Fallback: if dotenv didn't populate env vars for any reason, try to parse
# the frontend .env file directly to extract ADMIN_NAME/ADMIN_PASSWORD values.
if not ADMIN_ENABLED:
    try:
        raw = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("ADMIN_NAME=") and not ADMIN_NAME:
                val = line.split("=", 1)[1].strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                ADMIN_NAME = val
            if line.startswith("ADMIN_PASSWORD=") and not ADMIN_PASSWORD:
                val = line.split("=", 1)[1].strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                ADMIN_PASSWORD = val
        ADMIN_ENABLED = bool(ADMIN_NAME and ADMIN_PASSWORD)
    except Exception:
        pass

# We serve all frontend files manually via routes below to avoid
# conflicts between Flask's built-in static handler and SPA routes.
app = Flask(__name__)


def _supabase_headers(access_token: str | None = None, use_service: bool = False) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    if use_service:
        # Prefer the service role key if set, otherwise fall back to any service key
        if SUPABASE_SERVICE_ROLE:
            headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE}"
        elif SUPABASE_SERVICE_KEY:
            headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_KEY}"
        else:
            # Service key missing; caller should handle this case
            pass
    elif access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _get_access_token() -> str | None:
    return request.cookies.get(ACCESS_COOKIE)


def _get_current_user(access_token: str):
    resp = requests.get(
        f"{AUTH_URL}/user",
        headers=_supabase_headers(access_token),
        timeout=10,
    )
    if not resp.ok:
        return None
    return resp.json()


def _get_user_roles(access_token: str) -> list[str]:
    resp = requests.get(
        f"{REST_URL}/user_roles?select=role",
        headers=_supabase_headers(access_token),
        timeout=10,
    )
    if not resp.ok:
        return []
    data = resp.json()
    return [row.get("role") for row in data if "role" in row]


@app.route("/api/auth/signup", methods=["POST"])
def api_signup():
    payload = request.get_json(force=True) or {}
    email = payload.get("email")
    password = payload.get("password")
    display_name = payload.get("display_name")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    body = {
        "email": email,
        "password": password,
        "data": {"display_name": display_name or email},
    }

    resp = requests.post(
        f"{AUTH_URL}/signup",
        json=body,
        headers=_supabase_headers(),
        timeout=10,
    )

    if not resp.ok:
        try:
            error_body = resp.json()
            message = error_body.get("msg") or error_body.get("error_description") or "Signup failed"
        except Exception:
            message = "Signup failed"
        return jsonify({"error": message}), resp.status_code

    data = resp.json()

    # If Supabase returns a session directly, user is already logged in
    session = data.get("session")
    access_token = None
    refresh_token = None

    if session:
        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")
    else:
        # If your Supabase project has email confirmation disabled,
        # we can immediately log in with the same credentials to get a session.
        login_resp = requests.post(
            f"{AUTH_URL}/token?grant_type=password",
            json={"email": email, "password": password},
            headers=_supabase_headers(),
            timeout=10,
        )
        if login_resp.ok:
            login_data = login_resp.json()
            access_token = login_data.get("access_token")
            refresh_token = login_data.get("refresh_token")
            # Prefer the user object from the login response if present
            data["user"] = login_data.get("user") or data.get("user")
        else:
            # If email confirmation is enabled, Supabase won't issue a session on signup,
            # and password login will fail until email is confirmed.
            try:
                login_error = login_resp.json()
                message = (
                    login_error.get("error_description")
                    or login_error.get("msg")
                    or login_error.get("error")
                    or "Email confirmation is enabled"
                )
            except Exception:
                message = "Email confirmation is enabled"

            return (
                jsonify(
                    {
                        "error": (
                            f"{message}. Disable Supabase email confirmation: "
                            "Authentication → Providers → Email → turn off 'Confirm email'."
                        )
                    }
                ),
                400,
            )

    response = make_response(jsonify({"user": data.get("user")}))

    if access_token:
        response.set_cookie(
            ACCESS_COOKIE,
            access_token,
            httponly=True,
            samesite="Lax",
        )
    if refresh_token:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh_token,
            httponly=True,
            samesite="Lax",
        )

    return response


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    payload = request.get_json(force=True) or {}
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    body = {"email": email, "password": password}

    resp = requests.post(
        f"{AUTH_URL}/token?grant_type=password",
        json=body,
        headers=_supabase_headers(),
        timeout=10,
    )

    if not resp.ok:
        try:
            message = resp.json().get("error_description") or resp.json().get("msg")
        except Exception:
            message = "Login failed"
        return jsonify({"error": message}), resp.status_code

    data = resp.json()
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    response = make_response(jsonify({"user": data.get("user")}))
    if access_token:
        response.set_cookie(
            ACCESS_COOKIE,
            access_token,
            httponly=True,
            samesite="Lax",
        )
    if refresh_token:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh_token,
            httponly=True,
            samesite="Lax",
        )

    return response


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    access_token = _get_access_token()
    if access_token:
        # best-effort sign out in Supabase
        try:
            requests.post(
                f"{AUTH_URL}/logout",
                headers=_supabase_headers(access_token),
                timeout=10,
            )
        except Exception:
            pass

    response = make_response(jsonify({"success": True}))
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE)
    response.delete_cookie(ADMIN_COOKIE)
    return response


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    payload = request.get_json(force=True) or {}
    if not ADMIN_ENABLED:
        return jsonify({"error": "Admin login is disabled on this server"}), 404
    name = (payload.get("name") or "").strip()
    password = payload.get("password") or ""
    if name == ADMIN_NAME and password == ADMIN_PASSWORD:
        response = make_response(jsonify({"success": True}))
        response.set_cookie(
            ADMIN_COOKIE,
            "1",
            httponly=True,
            samesite="Lax",
        )
        return response

    return jsonify({"error": "Invalid admin credentials"}), 401


@app.route("/api/auth/session", methods=["GET"])
def api_session():
    access_token = _get_access_token()
    if not access_token:
        # If no user token but an admin cookie is present and admin is enabled,
        # expose the admin role so frontend can show the admin dashboard.
        if ADMIN_ENABLED and request.cookies.get(ADMIN_COOKIE) == "1":
            return jsonify({"user": None, "roles": ["admin"]})
        return jsonify({"user": None, "roles": []})

    user = _get_current_user(access_token)

    # If access token is expired or invalid, try to refresh using the refresh token
    if not user:
        refresh_token = request.cookies.get(REFRESH_COOKIE)
        if refresh_token:
            refresh_resp = requests.post(
                f"{AUTH_URL}/token?grant_type=refresh_token",
                json={"refresh_token": refresh_token},
                headers=_supabase_headers(),
                timeout=10,
            )
            if refresh_resp.ok:
                refresh_data = refresh_resp.json()
                access_token = refresh_data.get("access_token")
                new_refresh_token = refresh_data.get("refresh_token") or refresh_token

                if access_token:
                    # Update cookies with fresh tokens
                    response = make_response()
                    response.set_cookie(
                        ACCESS_COOKIE,
                        access_token,
                        httponly=True,
                        samesite="Lax",
                    )
                    response.set_cookie(
                        REFRESH_COOKIE,
                        new_refresh_token,
                        httponly=True,
                        samesite="Lax",
                    )
                    # Fetch user again with new access token
                    user = _get_current_user(access_token)
                    if not user:
                        return jsonify({"user": None, "roles": []})

                    roles = _get_user_roles(access_token)
                    if request.cookies.get(ADMIN_COOKIE) == "1" and "admin" not in roles:
                        roles.append("admin")
                    safe_user = {
                        "id": user.get("id"),
                        "email": user.get("email"),
                        "display_name": (user.get("user_metadata") or {}).get("display_name"),
                    }
                    # Attach JSON to the response we already created to update cookies
                    response.set_data(
                        jsonify({"user": safe_user, "roles": roles}).get_data(as_text=True)
                    )
                    response.mimetype = "application/json"
                    return response

        # If we couldn't refresh, treat as logged out
        return jsonify({"user": None, "roles": []})

    roles = _get_user_roles(access_token)
    if request.cookies.get(ADMIN_COOKIE) == "1" and "admin" not in roles:
        roles.append("admin")
    safe_user = {
        "id": user.get("id"),
        "email": user.get("email"),
        "display_name": (user.get("user_metadata") or {}).get("display_name"),
    }
    return jsonify({"user": safe_user, "roles": roles})


def _proxy_get(path: str, params: dict | None = None):
    access_token = _get_access_token()
    # Allow admin cookie to access admin endpoints even without an access token
    admin_cookie = request.cookies.get(ADMIN_COOKIE) == "1"
    allow_admin = ADMIN_ENABLED and admin_cookie
    if not access_token and not allow_admin:
        return jsonify({"error": "Not authenticated"}), 401

    # Choose headers: prefer user access token; otherwise use service key for admin
    if access_token:
        headers = _supabase_headers(access_token)
    else:
        if not (SUPABASE_SERVICE_ROLE or SUPABASE_SERVICE_KEY):
            return jsonify({"error": "Server misconfiguration: missing SUPABASE_SERVICE_ROLE"}), 500
        headers = _supabase_headers(None, use_service=True)

    resp = requests.get(
        f"{REST_URL}/{path}",
        headers=headers,
        params=params or {},
        timeout=15,
    )
    if not resp.ok:
        # If PostgREST reports a missing table (PGRST205) return an empty list
        # so the frontend can show an empty state instead of an error toast.
        try:
            error_body = resp.json()
            code = error_body.get("code")
            if code == "PGRST205" or (isinstance(error_body, dict) and "table" in str(error_body).lower()):
                return jsonify({"error": "Supabase table missing or not accessible. Create the required tables in your Supabase database."}), 500
        except Exception:
            # fallback to checking raw text
            txt = resp.text or ""
            if "PGRST205" in txt or "could not find the table" in txt.lower():
                return jsonify({"error": "Supabase table missing or not accessible. Create the required tables in your Supabase database."}), 500

        return jsonify({"error": resp.text}), resp.status_code
    return jsonify(resp.json())


def _proxy_mutation(method: str, path: str, json_body: dict | None = None, params: dict | None = None):
    access_token = _get_access_token()
    admin_cookie = request.cookies.get(ADMIN_COOKIE) == "1"
    allow_admin = ADMIN_ENABLED and admin_cookie
    if not access_token and not allow_admin:
        return jsonify({"error": "Not authenticated"}), 401

    # Choose headers: prefer user access token; otherwise require a service role key for admin
    if access_token:
        headers = _supabase_headers(access_token)
    else:
        if not (SUPABASE_SERVICE_ROLE or SUPABASE_SERVICE_KEY):
            return jsonify({"error": "Server misconfiguration: missing SUPABASE_SERVICE_ROLE"}), 500
        headers = _supabase_headers(None, use_service=True)

    func = getattr(requests, method.lower())
    # Ask PostgREST to return the created/updated representation for mutations
    if method.lower() in ("post", "patch", "put"):
        headers.setdefault("Prefer", "return=representation")
    resp = func(
        f"{REST_URL}/{path}",
        headers=headers,
        json=json_body,
        params=params or {},
        timeout=15,
    )
    if not resp.ok:
        try:
            error = resp.json()
        except Exception:
            error = {"error": resp.text}
        return jsonify(error), resp.status_code
    # Some PostgREST mutations return empty body
    try:
        data = resp.json()
    except Exception:
        data = None
    return jsonify(data)


@app.route("/api/projects", methods=["GET"])
def api_projects_list():
    # projects are already filtered by RLS in Supabase
    params = {"select": "*", "order": "updated_at.desc"}
    return _proxy_get("projects", params)


@app.route("/api/projects", methods=["POST"])
def api_projects_create():
    access_token = _get_access_token()
    if not access_token:
        return jsonify({"error": "Not authenticated"}), 401
    
    user = _get_current_user(access_token)
    if not user or not user.get("id"):
        return jsonify({"error": "Failed to get current user"}), 401
    
    body = request.get_json(force=True) or {}
    name = body.get("name") or "Untitled Project"
    canvas_data = body.get("canvas_data") or {"modules": [], "wires": []}
    payload = {"user_id": user["id"], "name": name, "canvas_data": canvas_data}
    params = {"select": "*"}
    return _proxy_mutation("post", "projects", payload, params)


@app.route("/api/projects/<project_id>", methods=["GET"])
def api_project_detail(project_id: str):
    params = {"id": f"eq.{project_id}", "select": "*", "limit": 1}
    return _proxy_get("projects", params)


@app.route("/api/projects/<project_id>", methods=["PUT"])
def api_project_update(project_id: str):
    body = request.get_json(force=True) or {}
    payload = {}
    if "name" in body:
        payload["name"] = body["name"]
    if "canvas_data" in body:
        payload["canvas_data"] = body["canvas_data"]

    params = {"id": f"eq.{project_id}"}
    return _proxy_mutation("patch", "projects", payload, params)


@app.route("/api/projects/<project_id>", methods=["DELETE"])
def api_project_delete(project_id: str):
    params = {"id": f"eq.{project_id}"}
    return _proxy_mutation("delete", "projects", None, params)


@app.route("/api/modules", methods=["GET"])
def api_modules_list():
    params = {"select": "*", "order": "name"}
    return _proxy_get("modules", params)


@app.route("/api/module-pins", methods=["GET"])
def api_module_pins_list():
    params = {"select": "*"}
    module_id = request.args.get("module_id")
    if module_id:
        params["module_id"] = f"eq.{module_id}"
    return _proxy_get("module_pins", params)


@app.route("/api/admin/modules", methods=["POST"])
def api_admin_create_module():
    body = request.get_json(force=True) or {}
    payload = {
        "name": body.get("name"),
        "category": body.get("category"),
        "description": body.get("description"),
        "image_url": body.get("image_url"),
    }
    params = {"select": "*"}
    return _proxy_mutation("post", "modules", payload, params)


@app.route("/api/admin/modules/<module_id>", methods=["PUT"])
def api_admin_update_module(module_id: str):
    body = request.get_json(force=True) or {}
    payload = {
        "name": body.get("name"),
        "category": body.get("category"),
        "description": body.get("description"),
        "image_url": body.get("image_url"),
    }
    params = {"id": f"eq.{module_id}"}
    return _proxy_mutation("patch", "modules", payload, params)


@app.route("/api/admin/modules/<module_id>", methods=["DELETE"])
def api_admin_delete_module(module_id: str):
    params = {"id": f"eq.{module_id}"}
    return _proxy_mutation("delete", "modules", None, params)


@app.route("/api/admin/module-pins/<module_id>", methods=["POST"])
def api_admin_create_pins(module_id: str):
    body = request.get_json(force=True) or {}
    pins = body.get("pins") or []
    payload = [
        {
            "module_id": module_id,
            "name": p["name"],
            "pin_type": p["pin_type"],
            "x": p["x"],
            "y": p["y"],
        }
        for p in pins
    ]
    return _proxy_mutation("post", "module_pins", payload, None)


@app.route("/api/admin/module-pins/<pin_id>", methods=["DELETE"])
def api_admin_delete_pin(pin_id: str):
    params = {"id": f"eq.{pin_id}"}
    return _proxy_mutation("delete", "module_pins", None, params)


@app.route("/api/admin/module-images/upload", methods=["POST"])
def api_upload_module_image():
    access_token = _get_access_token()
    # Allow admin cookie to upload files even without a Supabase user token
    admin_cookie = request.cookies.get(ADMIN_COOKIE) == "1"
    if not access_token and not (ADMIN_ENABLED and admin_cookie):
        return jsonify({"error": "Not authenticated"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = file.filename or "upload"
    ext = filename.split(".")[-1] if "." in filename else "png"
    import uuid

    new_name = f"{uuid.uuid4()}.{ext}"

    # If we have an access token, use Supabase storage as before.
    if access_token:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {access_token}",
        }

        resp = requests.post(
            f"{STORAGE_URL}/object/module-images/{new_name}",
            headers=headers,
            data=file.stream.read(),
            timeout=30,
        )

        if not resp.ok:
            return jsonify({"error": resp.text}), resp.status_code

        public_url = f"{SUPABASE_URL}/storage/v1/object/public/module-images/{new_name}"
        return jsonify({"public_url": public_url})
    # Admin cookie case: require a service role key so uploads go to Supabase
    role_key = SUPABASE_SERVICE_ROLE or SUPABASE_SERVICE_KEY
    if not role_key:
        return (
            jsonify({"error": "Server misconfiguration: SUPABASE_SERVICE_ROLE is required for admin uploads"}),
            500,
        )

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {role_key}",
    }

    resp = requests.post(
        f"{STORAGE_URL}/object/module-images/{new_name}",
        headers=headers,
        data=file.stream.read(),
        timeout=30,
    )

    if not resp.ok:
        return jsonify({"error": resp.text}), resp.status_code

    public_url = f"{SUPABASE_URL}/storage/v1/object/public/module-images/{new_name}"
    return jsonify({"public_url": public_url})


@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok"})


@app.route("/<path:path>")
def serve_static(path: str):
    # Serve API routes separately
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404

    # If frontend build is missing, fall back to health endpoint
    if not FRONTEND_DIR.exists():
        return redirect("/api/health")

    file_path = FRONTEND_DIR / path
    if file_path.is_file():
        return send_from_directory(FRONTEND_DIR, path)
    # Fallback to index.html for SPA routes
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/")
def index():
    if not FRONTEND_DIR.exists():
        return redirect("/api/health")
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

