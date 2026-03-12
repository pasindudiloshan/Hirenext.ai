from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from app.services.admin_service import AdminService


# -----------------------------------
# Blueprint
# -----------------------------------
admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


# -----------------------------------
# Helpers
# -----------------------------------
def admin_login_required() -> bool:
    return "admin_id" in session


def redirect_if_not_admin():
    if not admin_login_required():
        flash("Please log in as admin first.", "error")
        return redirect(url_for("admin_bp.login"))
    return None


# -----------------------------------
# Admin Login
# -----------------------------------
@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Admin login page.
    Reuses auth/login.html UI
    and verifies fixed admin credentials through AdminService.
    """
    if admin_login_required():
        return redirect(url_for("admin_bp.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template(
                "auth/login.html",
                login_action=url_for("admin_bp.login"),
                login_title="Admin Sign In",
                login_subtitle="Login to access the admin dashboard",
                is_admin_login=True,
                email=email
            )

        admin = AdminService.verify_admin_login(email, password)

        if not admin:
            flash("Invalid admin email or password.", "error")
            return render_template(
                "auth/login.html",
                login_action=url_for("admin_bp.login"),
                login_title="Admin Sign In",
                login_subtitle="Login to access the admin dashboard",
                is_admin_login=True,
                email=email
            )

        session["admin_id"] = admin.get("id")
        session["admin_username"] = admin.get("username", "Admin")
        session["admin_role"] = admin.get("role", "admin")

        flash("Admin login successful.", "success")
        return redirect(url_for("admin_bp.dashboard"))

    return render_template(
        "auth/login.html",
        login_action=url_for("admin_bp.login"),
        login_title="Admin Sign In",
        login_subtitle="Login to access the admin dashboard",
        is_admin_login=True
    )


# -----------------------------------
# Admin Dashboard
# -----------------------------------
@admin_bp.route("/dashboard", methods=["GET"])
def dashboard():
    """
    Admin dashboard page.
    Displays system statistics and staff list.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    stats = AdminService.get_dashboard_counts()
    staff_list = AdminService.get_all_staff()

    return render_template(
        "admin/admin_dashboard.html",
        stats=stats,
        staff_list=staff_list,
        admin_username=session.get("admin_username", "Admin")
    )


# -----------------------------------
# Add User Page
# -----------------------------------
@admin_bp.route("/add-user", methods=["GET"])
def add_user_page():
    """
    Separate page for adding new staff members.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    return render_template(
        "admin/adduser.html",
        admin_username=session.get("admin_username", "Admin")
    )


# -----------------------------------
# View Staff Page
# -----------------------------------
@admin_bp.route("/staff/<staff_id>", methods=["GET"])
def view_staff(staff_id):
    """
    View a single staff member.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    staff = AdminService.get_staff_by_id(staff_id)

    if not staff:
        flash("Staff member not found.", "error")
        return redirect(url_for("admin_bp.dashboard"))

    return render_template(
        "admin/view_staff.html",
        staff=staff,
        admin_username=session.get("admin_username", "Admin")
    )


# -----------------------------------
# Edit Staff Page
# -----------------------------------
@admin_bp.route("/staff/<staff_id>/edit", methods=["GET"])
def edit_staff_page(staff_id):
    """
    Show edit page for a single staff member.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    staff = AdminService.get_staff_by_id(staff_id)

    if not staff:
        flash("Staff member not found.", "error")
        return redirect(url_for("admin_bp.dashboard"))

    return render_template(
        "admin/edit_staff.html",
        staff=staff,
        admin_username=session.get("admin_username", "Admin")
    )


# -----------------------------------
# Staff Create
# -----------------------------------
@admin_bp.route("/staff/create", methods=["POST"])
def create_staff():
    """
    Create a new staff/recruiter account from admin panel.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    full_name = request.form.get("full_name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    organization = request.form.get("organization", "").strip()
    password = request.form.get("password", "").strip()
    status = request.form.get("status", "Active").strip()

    if not full_name or not role or not email or not organization or not password:
        flash("All staff fields are required.", "error")
        return redirect(url_for("admin_bp.add_user_page"))

    success, message = AdminService.create_staff(
        full_name=full_name,
        role=role,
        email=email,
        organization=organization,
        password=password,
        status=status
    )

    flash(message, "success" if success else "error")

    if success:
        return redirect(url_for("admin_bp.dashboard"))

    return redirect(url_for("admin_bp.add_user_page"))


# -----------------------------------
# Optional Staff List Page
# -----------------------------------
@admin_bp.route("/staff", methods=["GET"])
def list_staff():
    """
    Optional separate page for staff listing.
    Use this route only if admin/staff_list.html exists.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    staff_list = AdminService.get_all_staff()

    return render_template(
        "admin/staff_list.html",
        staff_list=staff_list,
        admin_username=session.get("admin_username", "Admin")
    )


# -----------------------------------
# Staff Update
# -----------------------------------
@admin_bp.route("/staff/<staff_id>/update", methods=["POST"])
def update_staff(staff_id):
    """
    Update a staff member using MongoDB ObjectId string.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    full_name = request.form.get("full_name", "").strip()
    role = request.form.get("role", "").strip()
    email = request.form.get("email", "").strip()
    organization = request.form.get("organization", "").strip()
    status = request.form.get("status", "").strip()
    password = request.form.get("password", "").strip()

    success, message = AdminService.update_staff(
        staff_id=staff_id,
        full_name=full_name or None,
        role=role or None,
        email=email or None,
        organization=organization or None,
        status=status or None,
        password=password or None
    )

    flash(message, "success" if success else "error")

    if success:
        return redirect(url_for("admin_bp.view_staff", staff_id=staff_id))

    return redirect(url_for("admin_bp.edit_staff_page", staff_id=staff_id))


# -----------------------------------
# Staff Delete
# -----------------------------------
@admin_bp.route("/staff/<staff_id>/delete", methods=["POST"])
def delete_staff(staff_id):
    """
    Delete a staff member using MongoDB ObjectId string.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    success, message = AdminService.delete_staff(staff_id)
    flash(message, "success" if success else "error")
    return redirect(url_for("admin_bp.dashboard"))


# -----------------------------------
# Staff Status Toggle
# -----------------------------------
@admin_bp.route("/staff/<staff_id>/toggle-status", methods=["POST"])
def toggle_staff_status(staff_id):
    """
    Toggle staff status between Active and Suspended.
    """
    auth_redirect = redirect_if_not_admin()
    if auth_redirect:
        return auth_redirect

    success, message = AdminService.toggle_staff_status(staff_id)
    flash(message, "success" if success else "error")
    return redirect(url_for("admin_bp.dashboard"))


# -----------------------------------
# Admin Logout
# -----------------------------------
@admin_bp.route("/logout", methods=["GET"])
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect("/")