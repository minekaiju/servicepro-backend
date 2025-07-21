import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from src.models.user import db
from src.routes.user import user_bp
from src.routes.auth import auth_bp
from src.routes.customers import customers_bp
from src.routes.quotes import quotes_bp
from src.routes.jobs import jobs_bp
from src.routes.invoices import invoices_bp
from src.routes.dashboard import dashboard_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Enable CORS for all routes
CORS(app, origins="*", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], 
     allow_headers=["Content-Type", "Authorization"])

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Register blueprints
app.register_blueprint(user_bp, url_prefix='/api/users')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(customers_bp, url_prefix='/api/customers')
app.register_blueprint(quotes_bp, url_prefix='/api/quotes')
app.register_blueprint(jobs_bp, url_prefix='/api/jobs')
app.register_blueprint(invoices_bp, url_prefix='/api/invoices')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

# Initialize database
db.init_app(app)
with app.app_context():
    db.create_all()

# Health check endpoint
@app.route('/api/health')
def health_check():
    return {'status': 'healthy', 'message': 'ServicePro Elite API is running'}, 200

# Serve frontend
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)



