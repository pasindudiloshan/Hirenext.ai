from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

# If you have a UserModel or AuthService, you can import it here
# from app.models.user_model import UserModel
# from app.services.auth_service import AuthService


# --------------------------------------------------
# Blueprint
# --------------------------------------------------
auth_bp = Blueprint(
    "auth_bp",
    __name__,
    url_prefix="/auth"
)


# ==================================================
# LOGIN (GET)
# Used by modal fetch: /auth/login
# ==================================================
@auth_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("auth/login.html")


# ==================================================
# LOGIN (POST)
# ==================================================
@auth_bp.route("/login", methods=["POST"])
def login_submit():

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    # Basic validation
    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template("auth/login.html", email=email)

    # 🔹 Replace this with real authentication later
    # Example:
    # user = UserModel.authenticate(email, password)
    # if not user:
    #     flash("Invalid credentials.", "danger")
    #     return render_template("auth/login.html", email=email)

    flash("Login successful!", "success")

    # After login → go to dashboard
    return redirect(url_for("job_bp.dashboard_page"))


# ==================================================
# REGISTER (GET)
# Used by modal fetch: /auth/register
# ==================================================
@auth_bp.route("/register", methods=["GET"])
def register_page():
    return render_template("auth/register.html")


# ==================================================
# REGISTER (POST)
# ==================================================
@auth_bp.route("/register", methods=["POST"])
def register_submit():

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not name or not email or not password:
        flash("All fields are required.", "danger")
        return render_template(
            "auth/register.html",
            name=name,
            email=email
        )

    if len(password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return render_template(
            "auth/register.html",
            name=name,
            email=email
        )

    # 🔹 Replace this with real DB save later
    # Example:
    # success, message = AuthService.register_user(name, email, password)
    # if not success:
    #     flash(message, "danger")
    #     return render_template("auth/register.html", name=name, email=email)

    flash("Registration successful! Please login.", "success")

    return redirect(url_for("auth_bp.login_page"))