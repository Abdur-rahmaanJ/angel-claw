"""
Temporary notice:

Need help?

- Join the discord https://discord.com/invite/k37Ef6w
- Raise an issue https://github.com/shopyo/shopyo/issues/new/choose
- Mail maintainers https://github.com/shopyo/shopyo#-contact

Hope it helps! We welcome all questions and even requests for walkthroughs
"""

import importlib
import os
import sys
import logging
import warnings

# Silence noisy warnings and logs
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    from sqlalchemy.exc import LegacyAPIWarning, SAWarning
    warnings.filterwarnings("ignore", category=LegacyAPIWarning)
    warnings.filterwarnings("ignore", category=SAWarning)
except ImportError:
    pass

logging.getLogger("werkzeug").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)

import click
import jinja2
from flask import Flask
from flask_admin import Admin
from flask_admin.menu import MenuLink
from flask_login import current_user

from shopyo.api.assets import register_devstatic
from shopyo.api.debug import is_yo_debug
from shopyo.api.file import trycopy

logger = logging.getLogger("angel-claw-app")

base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
from config import app_config

# from init import db
from init import load_extensions
from init import modules_path

try:
    from init import installed_packages
except ImportError:
    click.echo(
        "This version of Shopyo requires that\n"
        "init.py contains the line\n"
        "installed_packages = []\n"
        "please add it."
    )
    sys.exit()

from shopyo_admin import MyAdminIndexView


def create_app(config_name="development"):
    global_template_variables = {}
    global_configs = {}
    app = Flask(
        __name__,
        instance_path=os.path.join(base_path, "instance"),
        instance_relative_config=True,
    )

    load_plugins(app, global_template_variables, global_configs, config_name)
    load_config_from_obj(app, config_name)
    load_config_from_instance(app, config_name)
    # create_config_json()
    load_extensions(app)

    from shopyo_base import ShopyoBase
    from shopyo_auth import ShopyoAuth
    from shopyo_appadmin import ShopyoAppAdmin
    from shopyo_dashboard import ShopyoDashboard
    # from shopyo_page import ShopyoPage
    # from shopyo_i18n import Shopyoi18n
    from shopyo_settings import ShopyoSettings
    from shopyo_theme import ShopyoTheme

    sh_base = ShopyoBase()
    sh_auth = ShopyoAuth()
    sh_appadmin = ShopyoAppAdmin()
    sh_dashboard = ShopyoDashboard()
    # sh_page = ShopyoPage()
    # sh_i18n = Shopyoi18n()
    sh_settings = ShopyoSettings()
    sh_theme = ShopyoTheme()

    sh_base.init_app(app)
    sh_auth.init_app(app)
    sh_appadmin.init_app(app)
    sh_dashboard.init_app(app)
    # sh_page.init_app(app)
    # sh_i18n.init_app(app)
    sh_settings.init_app(app)
    sh_theme.init_app(app)

    setup_flask_admin(app)
    register_devstatic(app, modules_path)
    load_blueprints(app, config_name, global_template_variables, global_configs)
    setup_theme_paths(app)
    inject_global_vars(app, global_template_variables)

    from init import db

    custom_commands(db, app)
    @app.route("/")
    def home_redirect():
        return redirect(url_for("agent.index"))

    return app


def _register_module(
    app, module_name, global_template_variables, global_configs, config_name
):
    """
    Helper to register a module/plugin:
    1. Register blueprint from .view
    2. Update global_template_variables from .global
    3. Update global_configs from .global
    """

    try:
        view_mod = importlib.import_module(f"{module_name}.view")
        # Try 'blueprint' attribute first
        bp = getattr(view_mod, "blueprint", None)
        if bp is None:
            # Fallback: try 'modulename_blueprint'
            # For modules.box__x.mod_y -> mod_y
            short_name = module_name.split(".")[-1]
            bp = getattr(view_mod, f"{short_name}_blueprint", None)

        if bp:
            app.register_blueprint(bp)
    except (ImportError, AttributeError) as e:
        if isinstance(e, AttributeError):
            if is_yo_debug():
                logger.debug(f"[ ] Blueprint skipped for {module_name}: {e}")
        else:
            raise e

    try:
        global_mod = importlib.import_module(f"{module_name}.global")
        if hasattr(global_mod, "available_everywhere"):
            global_template_variables.update(global_mod.available_everywhere)
    except (ImportError, AttributeError) as e:
        if is_yo_debug():
            logger.debug(f"[ ] Template var skipped for {module_name}: {e}")

    try:
        global_mod = importlib.import_module(f"{module_name}.global")
        if hasattr(global_mod, "configs") and config_name in global_mod.configs:
            global_configs.update(global_mod.configs[config_name])
    except (ImportError, AttributeError) as e:
        if is_yo_debug():
            logger.debug(f"[ ] Config skipped for {module_name}: {e}")


def load_plugins(app, global_template_variables, global_configs, config_name):
    for plugin in installed_packages:
        if plugin not in ["shopyo_admin"]:
            _register_module(
                app, plugin, global_template_variables, global_configs, config_name
            )


def load_config_from_obj(app, config_name):
    try:
        configuration = app_config[config_name]
    except KeyError as e:
        print(
            f"[ ] Invalid config name {e}. Available configurations are: "
            f"{list(app_config.keys())}\n"
        )
        sys.exit(1)

    app.config.from_object(configuration)


def load_config_from_instance(app, config_name):
    if config_name != "testing":
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True)

    # create empty instance folder and empty config if not present
    try:
        os.makedirs(app.instance_path)
        with open(os.path.join(app.instance_path, "config.py"), "a"):
            pass
    except OSError:
        pass


def setup_flask_admin(app):
    admin = Admin(
        app,
        name="My App",
        index_view=MyAdminIndexView(),
    )
    # admin.add_view(DefaultModelView(Settings, db.session))
    admin.add_link(MenuLink(name="Logout", category="", url="/auth/logout?next=/admin"))


def load_blueprints(app, config_name, global_template_variables, global_configs):
    """
    - Registers blueprints
    - Adds global template objects from modules
    - Adds global configs from modules
    """
    from shopyo.api.module import iter_modules

    for module_name, _ in iter_modules(base_path):
        _register_module(
            app, module_name, global_template_variables, global_configs, config_name
        )

    app.config.update(**global_configs)


def setup_theme_paths(app):
    with app.app_context():
        front_theme_dir = os.path.join(
            app.config["BASE_DIR"], "static", "themes", "front"
        )
        back_theme_dir = os.path.join(
            app.config["BASE_DIR"], "static", "themes", "back"
        )

        if os.path.exists(front_theme_dir) and os.path.exists(back_theme_dir):
            my_loader = jinja2.ChoiceLoader(
                [
                    app.jinja_loader,
                    jinja2.FileSystemLoader([front_theme_dir, back_theme_dir]),
                ]
            )
            app.jinja_loader = my_loader


def inject_global_vars(app, global_template_variables):
    @app.context_processor
    def inject_global_vars():
        APP_NAME = "dwdwefw"

        base_context = {
            "APP_NAME": APP_NAME,
            "len": len,
            "current_user": current_user,
        }
        base_context.update(global_template_variables)

        return base_context


def custom_commands(db, app):
    from flask.cli import with_appcontext

    @click.command("shopyo-seed")
    @with_appcontext
    def shopyo_upload():
        from shopyo_auth.models import User, Role
        import modules.agent.models
        import importlib
        from init import modules_path, root_path
        
        # Ensure all models are loaded manually into the current app context
        # to ensure db.create_all() picks them up.
        
        # Core Shopyo modules often have models in their .models
        core_packages = ["shopyo_auth", "shopyo_settings", "shopyo_theme", "shopyo_dashboard"]
        for pkg in core_packages:
            try:
                importlib.import_module(f"{pkg}.models")
            except Exception:
                pass

        # Our local modules
        from shopyo.api.module import iter_modules
        for module_name, _ in iter_modules(root_path):
            try:
                importlib.import_module(f"{module_name}.models")
            except Exception:
                pass
        
        # Ensure all tables exist
        db.create_all()
        
        # 1. Standard Shopyo Upload (initializes modules)
        for ext in app.extensions:
            if ext.startswith("shopyo_"):
                try:
                    e = app.extensions[ext]
                    e.upload()
                    db.session.commit()
                    logger.debug("Uploaded for " + ext)
                except AttributeError:
                    pass
        
        # 2. Ensure default roles exist
        admin_role = Role.query.filter_by(name="admin").first()
        if not admin_role:
            admin_role = Role(name="admin")
            db.session.add(admin_role)
        
        user_role = Role.query.filter_by(name="user").first()
        if not user_role:
            user_role = Role(name="user")
            db.session.add(user_role)
        
        db.session.commit()

        # 3. Create or Update Seed Admin with Roles
        admin_email = app.config.get("SEED_ADMIN_EMAIL")
        admin_pass = app.config.get("SEED_ADMIN_PASSWORD")
        
        user = User.query.filter_by(email=admin_email).first()
        if not user:
            user = User()
            user.email = admin_email
            user.password = admin_pass
            user.is_admin = True
            user.is_email_confirmed = True
            db.session.add(user)
            db.session.commit()
            logger.debug(f"Created seed admin: {admin_email}")
        
        if admin_role not in user.roles:
            user.roles.append(admin_role)
        if user_role not in user.roles:
            user.roles.append(user_role)
            
        db.session.commit()
        logger.debug("Roles assigned to seed admin.")

    @click.command("shopyo-confirm-user")
    @click.argument("email")
    @with_appcontext
    def shopyo_confirm_user(email):
        from shopyo_auth.models import User, Role
        import datetime
        
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"User with email {email} not found.")
            return
            
        user.is_email_confirmed = True
        user.email_confirm_date = datetime.datetime.now()
        
        user_role = Role.query.filter_by(name="user").first()
        if user_role and user_role not in user.roles:
            user.roles.append(user_role)
            
        db.session.commit()
        click.echo(f"User {email} confirmed and assigned 'user' role.")

    @click.command("shopyo-promote-user")
    @click.argument("email")
    @with_appcontext
    def shopyo_promote_user(email):
        from shopyo_auth.models import User, Role
        
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"User with email {email} not found.")
            return
            
        user.is_admin = True
        
        admin_role = Role.query.filter_by(name="admin").first()
        if admin_role and admin_role not in user.roles:
            user.roles.append(admin_role)
            
        db.session.commit()
        click.echo(f"User {email} promoted to admin.")

    @click.command("shopyo-create-admin")
    @click.argument("email")
    @click.argument("password")
    @with_appcontext
    def shopyo_create_admin(email, password):
        from shopyo_auth.models import User, Role
        import datetime
        
        user = User.query.filter_by(email=email).first()
        if user:
            click.echo(f"User with email {email} already exists.")
            return
            
        user = User()
        user.email = email
        user.password = password
        user.is_admin = True
        user.is_email_confirmed = True
        user.email_confirm_date = datetime.datetime.now()
        
        db.session.add(user)
        db.session.commit()
        
        admin_role = Role.query.filter_by(name="admin").first()
        if admin_role:
            user.roles.append(admin_role)
            
        user_role = Role.query.filter_by(name="user").first()
        if user_role:
            user.roles.append(user_role)
            
        db.session.commit()
        click.echo(f"Admin user {email} created successfully.")

    @click.command("shopyo-list-users")
    @with_appcontext
    def shopyo_list_users():
        from shopyo_auth.models import User
        users = User.query.all()
        click.echo(f"{'ID':<4} {'Email':<30} {'Confirmed':<10} {'Admin':<6}")
        click.echo("-" * 55)
        for user in users:
            click.echo(f"{user.id:<4} {user.email:<30} {str(user.is_email_confirmed):<10} {str(user.is_admin):<6}")

    @click.command("shopyo-update-password")
    @click.argument("email")
    @click.argument("new_password")
    @with_appcontext
    def shopyo_update_password(email, new_password):
        from shopyo_auth.models import User
        
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"User with email {email} not found.")
            return
            
        user.password = new_password
        db.session.commit()
        click.echo(f"Password for user {email} updated successfully.")

    app.cli.add_command(shopyo_upload)
    app.cli.add_command(shopyo_confirm_user)
    app.cli.add_command(shopyo_promote_user)
    app.cli.add_command(shopyo_create_admin)
    app.cli.add_command(shopyo_list_users)
    app.cli.add_command(shopyo_update_password)
