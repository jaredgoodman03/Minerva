import os
from . import db, auth, request
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, Flask
)

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'requests.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Home page
    @app.route('/index')
    def index():
        return render_template("index.html")

    db.init_app(app)

    app.register_blueprint(auth.bp)
    # request.py has blueprints for both requesting and displaying orders
    # KARTHIK: That's the file where you put your cool google sheets stuff!
    #app.register_blueprint(request.bp)
    #app.add_url_rule('/', endpoint='index')

    return app
    