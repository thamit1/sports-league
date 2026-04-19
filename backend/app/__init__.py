from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # Set to timedelta in production

    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME', 'slms_db')
    db_user = os.getenv('DB_USER', 'root')
    db_pass = os.getenv('DB_PASSWORD', '')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f'mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    CORS(app, origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.clubs import clubs_bp
    from app.routes.players import players_bp
    from app.routes.teams import teams_bp
    from app.routes.sports import sports_bp
    from app.routes.matches import matches_bp
    from app.routes.tournaments import tournaments_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(clubs_bp, url_prefix='/api/clubs')
    app.register_blueprint(players_bp, url_prefix='/api/players')
    app.register_blueprint(teams_bp, url_prefix='/api/teams')
    app.register_blueprint(sports_bp, url_prefix='/api/sports')
    app.register_blueprint(matches_bp, url_prefix='/api/matches')
    app.register_blueprint(tournaments_bp, url_prefix='/api/tournaments')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

    @app.route('/api/health')
    def health():
        return {'status': 'ok', 'version': '1.0.0'}

    return app
