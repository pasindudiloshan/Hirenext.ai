from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from app.services.admin_service import AdminService
from app.services.auth_service import AuthService


# --------------------------------------------------
# Blueprint
# --------------------------------------------------
auth_bp = Blueprint(
    "auth_bp",
    __name__,
    url_prefix="/auth"
)


# ==================================================
# LOGIN PAGE (GET)
# ==================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template(
        "auth/login.html",
        login_action=url_for("auth_bp.login_submit"),
        login_title="Sign In",
        login_subtitle="Welcome back! Please login to continue.",
        is_admin_login=False
    )


# ==================================================
# LOGIN SUBMIT (POST)
# ==================================================
@auth_bp.route("/login", methods=["POST"])
def login_submit():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Email and password are required.", "error")
        return render_template(
            "auth/login.html",
            email=email,
            login_action=url_for("auth_bp.login_submit"),
            login_title="Sign In",
            login_subtitle="Welcome back! Please login to continue.",
            is_admin_login=False
        )

    # ----------------------------------------------
    # 1. Try Admin Login
    # ----------------------------------------------
    admin = AdminService.verify_admin_login(email, password)

    if admin:
        session.clear()
        session["user_id"] = admin.get("id")
        session["user_name"] = admin.get("username")
        session["user_email"] = admin.get("email")
        session["role"] = "admin"

        session["admin_id"] = admin.get("id")
        session["admin_username"] = admin.get("username")
        session["admin_role"] = admin.get("role", "admin")

        flash("Admin login successful.", "success")
        return redirect(url_for("admin_bp.dashboard"))

    # ----------------------------------------------
    # 2. Try Staff Login
    # ----------------------------------------------
    staff = AuthService.login_staff(email, password)

    if staff:
        session.clear()
        session["user_id"] = staff.get("id")
        session["user_name"] = staff.get("full_name")
        session["user_email"] = staff.get("email")
        session["role"] = "staff"

        session["staff_id"] = staff.get("id")
        session["staff_name"] = staff.get("full_name")
        session["staff_role"] = staff.get("role", "staff")
        session["staff_organization"] = staff.get("organization", "")

        flash("Login successful.", "success")
        return redirect(url_for("job_bp.dashboard_page"))

    # ----------------------------------------------
    # 3. Try Candidate Login
    # ----------------------------------------------
    candidate = AuthService.login_candidate(email, password)

    if candidate:
        session.clear()
        session["user_id"] = candidate.get("id")
        session["user_name"] = candidate.get("full_name")
        session["user_email"] = candidate.get("email")
        session["role"] = "candidate"

        session["candidate_id"] = candidate.get("id")
        session["candidate_name"] = candidate.get("full_name")

        flash("Login successful.", "success")
        return render_template("interview/interview_prep.html")

    flash("Invalid email or password.", "error")
    return render_template(
        "auth/login.html",
        email=email,
        login_action=url_for("auth_bp.login_submit"),
        login_title="Sign In",
        login_subtitle="Welcome back! Please login to continue.",
        is_admin_login=False
    )


# ==================================================
# REGISTER PAGE (GET)
# ==================================================
@auth_bp.route("/register", methods=["GET"])
def register_page():
    return render_template("auth/register.html")


# ==================================================
# REGISTER SUBMIT (POST)
# ==================================================
@auth_bp.route("/register", methods=["POST"])
def register_submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not name or not email or not password:
        flash("All fields are required.", "error")
        return render_template(
            "auth/register.html",
            name=name,
            email=email
        )

    success, message = AuthService.register_candidate(
        full_name=name,
        email=email,
        password=password
    )

    flash(message, "success" if success else "error")

    if success:
        return redirect(url_for("auth_bp.login_page"))

    return render_template(
        "auth/register.html",
        name=name,
        email=email
    )


# ==================================================
# LOGOUT
# ==================================================
@auth_bp.route("/logout", methods=["GET"])
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect("/")