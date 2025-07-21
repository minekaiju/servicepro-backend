from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Subscription info
    subscription_tier = db.Column(db.String(20), default='starter')  # starter, professional, business
    subscription_status = db.Column(db.String(20), default='trial')  # trial, active, cancelled, expired
    trial_ends_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=14))
    stripe_customer_id = db.Column(db.String(100), nullable=True)
    
    # Business info (from onboarding)
    business_name = db.Column(db.String(200), nullable=True)
    business_type = db.Column(db.String(100), nullable=True)
    business_description = db.Column(db.Text, nullable=True)
    primary_location = db.Column(db.String(200), nullable=True)
    service_radius = db.Column(db.String(50), nullable=True)
    business_phone = db.Column(db.String(20), nullable=True)
    business_email = db.Column(db.String(120), nullable=True)
    primary_color = db.Column(db.String(7), default='#2563eb')
    logo_url = db.Column(db.String(500), nullable=True)
    team_size = db.Column(db.String(20), nullable=True)
    onboarding_completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<User {self.email}>'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_token(self):
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        return jwt.encode(payload, os.environ.get('SECRET_KEY', 'dev-secret'), algorithm='HS256')

    @staticmethod
    def verify_token(token):
        try:
            payload = jwt.decode(token, os.environ.get('SECRET_KEY', 'dev-secret'), algorithms=['HS256'])
            return User.query.get(payload['user_id'])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'business_name': self.business_name,
            'business_type': self.business_type,
            'business_description': self.business_description,
            'primary_location': self.primary_location,
            'service_radius': self.service_radius,
            'business_phone': self.business_phone,
            'business_email': self.business_email,
            'primary_color': self.primary_color,
            'logo_url': self.logo_url,
            'team_size': self.team_size,
            'onboarding_completed': self.onboarding_completed
        }

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(10), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax_rate = db.Column(db.Numeric(5, 4), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), default='draft')  # draft, sent, accepted, rejected, expired
    valid_until = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='quotes')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer_id': self.customer_id,
            'quote_number': self.quote_number,
            'title': self.title,
            'description': self.description,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'tax_rate': float(self.tax_rate) if self.tax_rate else 0,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0,
            'total': float(self.total) if self.total else 0,
            'status': self.status,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'customer': self.customer.to_dict() if self.customer else None
        }

class QuoteItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quote = db.relationship('Quote', backref='items')

    def to_dict(self):
        return {
            'id': self.id,
            'quote_id': self.quote_id,
            'description': self.description,
            'quantity': float(self.quantity) if self.quantity else 0,
            'unit_price': float(self.unit_price) if self.unit_price else 0,
            'total_price': float(self.total_price) if self.total_price else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    quote_id = db.Column(db.Integer, db.ForeignKey('quote.id'), nullable=True)
    job_number = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scheduled_date = db.Column(db.DateTime, nullable=True)
    scheduled_time = db.Column(db.String(20), nullable=True)
    duration_hours = db.Column(db.Numeric(4, 2), nullable=True)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, in_progress, completed, cancelled
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='jobs')
    quote = db.relationship('Quote', backref='jobs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer_id': self.customer_id,
            'quote_id': self.quote_id,
            'job_number': self.job_number,
            'title': self.title,
            'description': self.description,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_time': self.scheduled_time,
            'duration_hours': float(self.duration_hours) if self.duration_hours else 0,
            'status': self.status,
            'total_amount': float(self.total_amount) if self.total_amount else 0,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'customer': self.customer.to_dict() if self.customer else None,
            'quote': self.quote.to_dict() if self.quote else None
        }

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tax_rate = db.Column(db.Numeric(5, 4), nullable=False, default=0)
    tax_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), default='draft')  # draft, sent, paid, overdue, cancelled
    due_date = db.Column(db.DateTime, nullable=True)
    paid_date = db.Column(db.DateTime, nullable=True)
    stripe_payment_intent_id = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref='invoices')
    job = db.relationship('Job', backref='invoices')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer_id': self.customer_id,
            'job_id': self.job_id,
            'invoice_number': self.invoice_number,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'tax_rate': float(self.tax_rate) if self.tax_rate else 0,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0,
            'total': float(self.total) if self.total else 0,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'paid_date': self.paid_date.isoformat() if self.paid_date else None,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'customer': self.customer.to_dict() if self.customer else None,
            'job': self.job.to_dict() if self.job else None
        }

