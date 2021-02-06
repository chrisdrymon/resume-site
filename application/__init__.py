from flask import Flask


def create_app():
    """Initialize the core application"""
    app = Flask(__name__, instance_relative_config=False, static_folder=None)
    app.config.from_object('config.DevConfig')

    with app.app_context():
        # Import parts of our application
        from .home import home
        from .semdoms import semdoms
        from .semdoms.semdoms import create_sd_dash
        # from .wowsim import wowsim
        # from .wowsim.wowsim import create_sim_dash
        create_sd_dash(app)
        # create_sim_dash(app)

        # Register Blueprints
        app.register_blueprint(home.home_bp, url_prefix='/')
        app.register_blueprint(semdoms.semdoms_bp)
        # app.register_blueprint(wowsim.wowsim_bp)

        return app

