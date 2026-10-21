import ipaddress
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import File, FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings
from .dynsec import DynSec, DynSecError
from .importer import MAX_BYTES, MAX_ROWS, parse_users_csv
from .security import ACL_TYPES, ROLE_RE, USERNAME_RE, LoginLimiter, acl_problem, new_csrf, password_problem

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
BAD_LOGIN = "Invalid username or password."


def create_app(settings: Settings | None = None, dynsec=None) -> FastAPI:
    settings = settings or Settings.from_env()
    owns_dynsec = dynsec is None
    dynsec = dynsec or DynSec(settings.mqtt_host, settings.mqtt_port,
                              settings.svc_user, settings.svc_password, settings.mqtt_tls)
    limiter = LoginLimiter()

    @asynccontextmanager
    async def lifespan(_app):
        if owns_dynsec:
            dynsec.start()
        yield
        if owns_dynsec:
            dynsec.stop()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, max_age=1800,
                       same_site="strict", https_only=settings.secure_cookies, session_cookie="nurb_mqtt")

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'"
        return resp

    # --- helpers -----------------------------------------------------------
    def client_ip(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    def render(request, template, status=200, **ctx):
        if "csrf" not in request.session:
            request.session["csrf"] = new_csrf()
        ctx.update(request=request, csrf=request.session["csrf"], min_len=settings.min_password_length)
        return TEMPLATES.TemplateResponse(request, template, ctx, status_code=status)

    def check_csrf(request: Request, token: str):
        good = request.session.get("csrf", "")
        if not good or not secrets.compare_digest(good, token):
            raise HTTPException(403, "Form expired. Go back, reload, and try again.")

    def redirect(url):
        return RedirectResponse(url, status_code=303)

    def admin_network_ok(request: Request) -> bool:
        try:
            ip = ipaddress.ip_address(client_ip(request))
        except ValueError:
            return False
        return any(ip in net for net in settings.admin_nets)

    def login_attempt(request, username, password, kind):
        """Return an error string, or None after storing the session key for `kind`."""
        ip = client_ip(request)
        if limiter.blocked(ip, username):
            return "Too many failed attempts. Wait 15 minutes and try again."
        ok = bool(USERNAME_RE.match(username)) and dynsec.verify_login(username, password)
        if ok and kind == "admin":
            client = dynsec.get_client(username)
            ok = bool(client) and any(r.get("rolename") == settings.admin_role for r in client.get("roles", []))
        if not ok:
            limiter.fail(ip, username)
            return BAD_LOGIN
        limiter.succeed(ip, username)
        request.session.clear()
        request.session["csrf"] = new_csrf()
        request.session[kind] = username
        return None

    # --- self-service ------------------------------------------------------
    @app.get("/")
    def root():
        return redirect("/account")

    @app.get("/account/login")
    def account_login_form(request: Request):
        return render(request, "login.html", title="Sign in", action="/account/login")

    @app.post("/account/login")
    def account_login(request: Request, username: str = Form(...), password: str = Form(...)):
        err = login_attempt(request, username.strip(), password, "account")
        if err:
            return render(request, "login.html", status=401, title="Sign in", action="/account/login", error=err)
        return redirect("/account")

    @app.get("/account")
    def account(request: Request):
        if not request.session.get("account"):
            return redirect("/account/login")
        return render(request, "account.html", user=request.session["account"])

    @app.post("/account/password")
    def account_password(request: Request, csrf: str = Form(...), current: str = Form(...),
                         new: str = Form(...), confirm: str = Form(...)):
        user = request.session.get("account")
        if not user:
            return redirect("/account/login")
        check_csrf(request, csrf)

        def fail(msg):
            return render(request, "account.html", status=400, user=user, error=msg)

        if limiter.blocked(client_ip(request), user):
            return fail("Too many failed attempts. Wait 15 minutes and try again.")
        if new != confirm:
            return fail("The new passwords do not match.")
        if problem := password_problem(new, user, settings.min_password_length):
            return fail(problem)
        if not dynsec.verify_login(user, current):
            limiter.fail(client_ip(request), user)
            return fail("The current password is wrong.")
        dynsec.set_password(user, new)
        # Any other signed-in browser keeps working until it expires; this one starts clean.
        request.session.clear()
        return render(request, "login.html", title="Sign in", action="/account/login",
                      notice="Password changed. Sign in again with the new password.")

    @app.post("/account/logout")
    def account_logout(request: Request, csrf: str = Form(...)):
        check_csrf(request, csrf)
        request.session.clear()
        return redirect("/account/login")

    # --- administrator -----------------------------------------------------
    def admin_user(request: Request):
        """The signed-in admin, re-checked against the broker so revoking the role is immediate."""
        if not admin_network_ok(request):
            raise HTTPException(404)
        user = request.session.get("admin")
        if not user:
            return None
        client = dynsec.get_client(user)
        if not client or not any(r.get("rolename") == settings.admin_role for r in client.get("roles", [])):
            request.session.clear()
            return None
        return user

    def protected(username):
        return username == settings.svc_user

    def builtin_role(rolename):
        """Roles the portal may read but not change: the broker's own admin role and our marker role."""
        return rolename in {"admin", settings.admin_role}

    @app.get("/admin/login")
    def admin_login_form(request: Request):
        if not admin_network_ok(request):
            raise HTTPException(404)
        return render(request, "login.html", title="Administrator sign in", action="/admin/login")

    @app.post("/admin/login")
    def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
        if not admin_network_ok(request):
            raise HTTPException(404)
        err = login_attempt(request, username.strip(), password, "admin")
        if err:
            return render(request, "login.html", status=401, title="Administrator sign in",
                          action="/admin/login", error=err)
        return redirect("/admin")

    def role_rows():
        rows = []
        for name in sorted(dynsec.list_roles(), key=str.lower):
            role = dynsec.get_role(name) or {}
            rows.append({
                "name": name,
                "builtin": builtin_role(name),
                "acls": sorted(role.get("acls", []), key=lambda a: (a["acltype"], a["topic"])),
            })
        return rows

    def admin_page(request, user, status=200, **ctx):
        clients = sorted(dynsec.list_clients(), key=lambda c: c["username"].lower())
        for c in clients:
            c["role_names"] = [r["rolename"] for r in c.get("roles", [])]
            c["protected"] = protected(c["username"]) or c["username"] == user
        return render(request, "admin.html", status=status, admin=user, clients=clients,
                      roles=dynsec.list_roles(), role_rows=role_rows(), acl_types=list(ACL_TYPES),
                      default_acl=dynsec.get_default_acl(), max_rows=MAX_ROWS, **ctx)

    @app.get("/admin")
    def admin(request: Request):
        user = admin_user(request)
        if not user:
            return redirect("/admin/login")
        return admin_page(request, user, notice=request.session.pop("flash", None))

    def guarded(request, csrf):
        user = admin_user(request)
        if not user:
            raise HTTPException(401, "Sign in again.")
        check_csrf(request, csrf)
        return user

    def done(request, message):
        request.session["flash"] = message
        return redirect("/admin")

    def refuse(request, user, message):
        return admin_page(request, user, status=400, error=message)

    @app.post("/admin/users")
    def admin_create(request: Request, csrf: str = Form(...), username: str = Form(...),
                     password: str = Form(...), textname: str = Form(""), roles: list[str] = Form([])):
        user = guarded(request, csrf)
        username = username.strip()
        if not USERNAME_RE.match(username):
            return refuse(request, user, "Usernames use letters, digits and . _ @ - only, up to 64.")
        if problem := password_problem(password, username, settings.min_password_length):
            return refuse(request, user, problem)
        try:
            dynsec.create_client(username, password, roles, textname.strip())
        except DynSecError as e:
            return refuse(request, user, str(e))
        return done(request, f"Created {username}.")

    @app.post("/admin/users/import")
    def admin_import(request: Request, csrf: str = Form(...), file: UploadFile = File(...)):
        user = guarded(request, csrf)
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return refuse(request, user, f"The file is larger than {MAX_BYTES // 1024} KB.")
        existing = {c["username"] for c in dynsec.list_clients()}
        plan = parse_users_csv(data, set(dynsec.list_roles()), existing, settings.min_password_length)
        if plan.errors:
            return admin_page(request, user, status=400, error="Nothing was imported. Fix these and upload again:",
                              error_list=plan.errors)
        created, failed = [], []
        for new in plan.users:
            try:
                dynsec.create_client(new.username, new.password, new.roles, new.textname)
                created.append(new.username)
            except DynSecError as e:
                failed.append(f"{new.username}: {e}")
                break
        if failed:
            return admin_page(request, user, status=400,
                              error=f"Created {len(created)} of {len(plan.users)} users. The import stopped at "
                                    "the first failure, and the rest of the file was not imported:",
                              error_list=failed)
        return done(request, f"Imported {len(created)} user{'' if len(created) == 1 else 's'}.")

    @app.post("/admin/users/{username}/password")
    def admin_reset(request: Request, username: str, csrf: str = Form(...), password: str = Form(...)):
        user = guarded(request, csrf)
        if protected(username):
            return refuse(request, user, "That account is managed outside the portal.")
        if problem := password_problem(password, username, settings.min_password_length):
            return refuse(request, user, problem)
        dynsec.set_password(username, password)
        return done(request, f"Password reset for {username}.")

    @app.post("/admin/users/{username}/enabled")
    def admin_enabled(request: Request, username: str, csrf: str = Form(...), enabled: str = Form(...)):
        user = guarded(request, csrf)
        if protected(username) or username == user:
            return refuse(request, user, "You cannot disable that account from here.")
        dynsec.set_enabled(username, enabled == "1")
        return done(request, f"{'Enabled' if enabled == '1' else 'Disabled'} {username}.")

    @app.post("/admin/users/{username}/roles")
    def admin_roles(request: Request, username: str, csrf: str = Form(...), roles: list[str] = Form([])):
        user = guarded(request, csrf)
        if protected(username):
            return refuse(request, user, "That account is managed outside the portal.")
        client = dynsec.get_client(username) or {}
        have = {r["rolename"] for r in client.get("roles", [])}
        want = set(roles)
        if username == user and settings.admin_role not in want:
            return refuse(request, user, "You cannot remove your own administrator role.")
        for r in want - have:
            dynsec.add_role(username, r)
        for r in have - want:
            dynsec.remove_role(username, r)
        return done(request, f"Updated roles for {username}.")

    @app.post("/admin/users/{username}/delete")
    def admin_delete(request: Request, username: str, csrf: str = Form(...)):
        user = guarded(request, csrf)
        if protected(username) or username == user:
            return refuse(request, user, "You cannot delete that account from here.")
        dynsec.delete_client(username)
        return done(request, f"Deleted {username}.")

    @app.post("/admin/roles")
    def admin_role_create(request: Request, csrf: str = Form(...), rolename: str = Form(...)):
        user = guarded(request, csrf)
        rolename = rolename.strip()
        if not ROLE_RE.match(rolename):
            return refuse(request, user, "Role names use letters, digits and . _ @ - only, up to 64.")
        if rolename in dynsec.list_roles():
            return refuse(request, user, f"The role {rolename} already exists.")
        try:
            dynsec.create_role(rolename)
        except DynSecError as e:
            return refuse(request, user, str(e))
        return done(request, f"Created role {rolename}. Add topic rules to it below.")

    @app.post("/admin/roles/{rolename}/rules")
    def admin_rule_add(request: Request, rolename: str, csrf: str = Form(...), acltype: str = Form(...),
                       topic: str = Form(...), allow: str = Form("1"), priority: int = Form(0)):
        user = guarded(request, csrf)
        if builtin_role(rolename):
            return refuse(request, user, "That role is managed outside the portal.")
        topic = topic.strip()
        if problem := acl_problem(acltype, topic):
            return refuse(request, user, problem)
        if allow not in ("0", "1"):
            return refuse(request, user, "Choose allow or deny.")
        if not 0 <= priority <= 999:
            return refuse(request, user, "Priority must be between 0 and 999.")
        if dynsec.get_role(rolename) is None:
            return refuse(request, user, f"The role {rolename} does not exist.")
        try:
            dynsec.add_role_acl(rolename, acltype, topic, allow == "1", priority)
        except DynSecError as e:
            return refuse(request, user, str(e))
        verb = "Allowed" if allow == "1" else "Denied"
        return done(request, f"{verb} {acltype} on {topic} for {rolename}.")

    @app.post("/admin/roles/{rolename}/rules/remove")
    def admin_rule_remove(request: Request, rolename: str, csrf: str = Form(...), acltype: str = Form(...),
                          topic: str = Form(...)):
        user = guarded(request, csrf)
        if builtin_role(rolename):
            return refuse(request, user, "That role is managed outside the portal.")
        try:
            dynsec.remove_role_acl(rolename, acltype, topic)
        except DynSecError as e:
            return refuse(request, user, str(e))
        return done(request, f"Removed {acltype} on {topic} from {rolename}.")

    @app.post("/admin/roles/{rolename}/delete")
    def admin_role_delete(request: Request, rolename: str, csrf: str = Form(...)):
        user = guarded(request, csrf)
        if builtin_role(rolename):
            return refuse(request, user, "That role is managed outside the portal.")
        holders = [c["username"] for c in dynsec.list_clients()
                   if any(r["rolename"] == rolename for r in c.get("roles", []))]
        try:
            dynsec.delete_role(rolename)
        except DynSecError as e:
            return refuse(request, user, str(e))
        note = f" It was removed from {len(holders)} account{'' if len(holders) == 1 else 's'}." if holders else ""
        return done(request, f"Deleted role {rolename}.{note}")

    @app.post("/admin/logout")
    def admin_logout(request: Request, csrf: str = Form(...)):
        check_csrf(request, csrf)
        request.session.clear()
        return redirect("/admin/login")

    @app.exception_handler(DynSecError)
    async def dynsec_failed(request, exc):
        return TEMPLATES.TemplateResponse(request, "login.html", {
            "title": "Unavailable", "action": "", "error": str(exc), "csrf": "", "min_len": 0,
            "hide_form": True}, status_code=503)

    return app
