from flask import Blueprint, request, jsonify
from src.models.user import db, Customer
from src.routes.auth import token_required

customers_bp = Blueprint('customers', __name__)

@customers_bp.route('/', methods=['GET'])
@token_required
def get_customers(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        
        query = Customer.query.filter_by(user_id=current_user.id)
        
        if search:
            query = query.filter(
                db.or_(
                    Customer.name.ilike(f'%{search}%'),
                    Customer.email.ilike(f'%{search}%'),
                    Customer.phone.ilike(f'%{search}%')
                )
            )
        
        customers = query.order_by(Customer.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'customers': [customer.to_dict() for customer in customers.items],
            'pagination': {
                'page': customers.page,
                'pages': customers.pages,
                'per_page': customers.per_page,
                'total': customers.total,
                'has_next': customers.has_next,
                'has_prev': customers.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch customers: {str(e)}'}), 500

@customers_bp.route('/', methods=['POST'])
@token_required
def create_customer(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Customer name is required'}), 400
        
        customer = Customer(
            user_id=current_user.id,
            name=name,
            email=data.get('email', '').strip() or None,
            phone=data.get('phone', '').strip() or None,
            address=data.get('address', '').strip() or None,
            city=data.get('city', '').strip() or None,
            state=data.get('state', '').strip() or None,
            zip_code=data.get('zip_code', '').strip() or None,
            notes=data.get('notes', '').strip() or None
        )
        
        db.session.add(customer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer created successfully',
            'customer': customer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create customer: {str(e)}'}), 500

@customers_bp.route('/<int:customer_id>', methods=['GET'])
@token_required
def get_customer(current_user, customer_id):
    try:
        customer = Customer.query.filter_by(
            id=customer_id, 
            user_id=current_user.id
        ).first()
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        return jsonify({
            'success': True,
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch customer: {str(e)}'}), 500

@customers_bp.route('/<int:customer_id>', methods=['PUT'])
@token_required
def update_customer(current_user, customer_id):
    try:
        customer = Customer.query.filter_by(
            id=customer_id, 
            user_id=current_user.id
        ).first()
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update fields
        if 'name' in data:
            name = data['name'].strip()
            if not name:
                return jsonify({'error': 'Customer name is required'}), 400
            customer.name = name
        
        if 'email' in data:
            customer.email = data['email'].strip() or None
        if 'phone' in data:
            customer.phone = data['phone'].strip() or None
        if 'address' in data:
            customer.address = data['address'].strip() or None
        if 'city' in data:
            customer.city = data['city'].strip() or None
        if 'state' in data:
            customer.state = data['state'].strip() or None
        if 'zip_code' in data:
            customer.zip_code = data['zip_code'].strip() or None
        if 'notes' in data:
            customer.notes = data['notes'].strip() or None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer updated successfully',
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update customer: {str(e)}'}), 500

@customers_bp.route('/<int:customer_id>', methods=['DELETE'])
@token_required
def delete_customer(current_user, customer_id):
    try:
        customer = Customer.query.filter_by(
            id=customer_id, 
            user_id=current_user.id
        ).first()
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Check if customer has associated quotes, jobs, or invoices
        if customer.quotes or customer.jobs or customer.invoices:
            return jsonify({
                'error': 'Cannot delete customer with associated quotes, jobs, or invoices'
            }), 400
        
        db.session.delete(customer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Customer deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete customer: {str(e)}'}), 500

@customers_bp.route('/search', methods=['GET'])
@token_required
def search_customers(current_user):
    try:
        query = request.args.get('q', '', type=str)
        limit = request.args.get('limit', 10, type=int)
        
        if not query:
            return jsonify({
                'success': True,
                'customers': []
            }), 200
        
        customers = Customer.query.filter(
            Customer.user_id == current_user.id,
            db.or_(
                Customer.name.ilike(f'%{query}%'),
                Customer.email.ilike(f'%{query}%'),
                Customer.phone.ilike(f'%{query}%')
            )
        ).limit(limit).all()
        
        return jsonify({
            'success': True,
            'customers': [customer.to_dict() for customer in customers]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

