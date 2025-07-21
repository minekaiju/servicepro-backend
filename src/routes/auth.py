from flask import Blueprint, request, jsonify
from src.models.user import db, User
from functools import wraps
import re

auth_bp = Blueprint('auth', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            current_user = User.verify_token(token)
            if not current_user:
                return jsonify({'error': 'Token is invalid'}), 401
        except Exception as e:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    return len(password) >= 8

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        # Validation
        if not email or not password or not name:
            return jsonify({'error': 'Email, password, and name are required'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Create new user
        user = User(
            email=email,
            name=name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Generate token
        token = user.generate_token()
        
        return jsonify({
            'success': True,
            'message': 'User registered successfully',
            'token': token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Generate token
        token = user.generate_token()
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    }), 200

@auth_bp.route('/complete-onboarding', methods=['POST'])
@token_required
def complete_onboarding(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update user with onboarding data
        current_user.business_name = data.get('businessName')
        current_user.business_type = data.get('businessType')
        current_user.business_description = data.get('businessDescription')
        current_user.primary_location = data.get('primaryLocation')
        current_user.service_radius = data.get('serviceRadius')
        current_user.business_phone = data.get('businessPhone')
        current_user.business_email = data.get('businessEmail')
        current_user.primary_color = data.get('primaryColor', '#2563eb')
        current_user.team_size = data.get('teamSize')
        current_user.onboarding_completed = True
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Onboarding completed successfully',
            'user': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Onboarding failed: {str(e)}'}), 500

@auth_bp.route('/update-profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update allowed fields
        if 'name' in data:
            current_user.name = data['name'].strip()
        if 'business_name' in data:
            current_user.business_name = data['business_name']
        if 'business_phone' in data:
            current_user.business_phone = data['business_phone']
        if 'business_email' in data:
            current_user.business_email = data['business_email']
        if 'primary_color' in data:
            current_user.primary_color = data['primary_color']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Profile update failed: {str(e)}'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Current password and new password are required'}), 400
        
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        if not validate_password(new_password):
            return jsonify({'error': 'New password must be at least 8 characters long'}), 400
        
        current_user.set_password(new_password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Password change failed: {str(e)}'}), 500

@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    try:
        data = request.get_json()
        token = data.get('token') if data else None
        
        if not token:
            return jsonify({'valid': False, 'error': 'Token is required'}), 400
        
        user = User.verify_token(token)
        if user:
            return jsonify({
                'valid': True,
                'user': user.to_dict()
            }), 200
        else:
            return jsonify({'valid': False, 'error': 'Invalid or expired token'}), 401
            
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500

