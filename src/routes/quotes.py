from flask import Blueprint, request, jsonify
from src.models.user import db, Quote, QuoteItem, Customer
from src.routes.auth import token_required
from datetime import datetime, timedelta
import uuid

quotes_bp = Blueprint('quotes', __name__)

def generate_quote_number():
    return f"QT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@quotes_bp.route('/', methods=['GET'])
@token_required
def get_quotes(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '', type=str)
        search = request.args.get('search', '', type=str)
        
        query = Quote.query.filter_by(user_id=current_user.id)
        
        if status:
            query = query.filter_by(status=status)
        
        if search:
            query = query.join(Customer).filter(
                db.or_(
                    Quote.title.ilike(f'%{search}%'),
                    Quote.quote_number.ilike(f'%{search}%'),
                    Customer.name.ilike(f'%{search}%')
                )
            )
        
        quotes = query.order_by(Quote.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'quotes': [quote.to_dict() for quote in quotes.items],
            'pagination': {
                'page': quotes.page,
                'pages': quotes.pages,
                'per_page': quotes.per_page,
                'total': quotes.total,
                'has_next': quotes.has_next,
                'has_prev': quotes.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch quotes: {str(e)}'}), 500

@quotes_bp.route('/', methods=['POST'])
@token_required
def create_quote(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        customer_id = data.get('customer_id')
        title = data.get('title', '').strip()
        
        if not customer_id or not title:
            return jsonify({'error': 'Customer ID and title are required'}), 400
        
        # Verify customer belongs to user
        customer = Customer.query.filter_by(
            id=customer_id, 
            user_id=current_user.id
        ).first()
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        quote = Quote(
            user_id=current_user.id,
            customer_id=customer_id,
            quote_number=generate_quote_number(),
            title=title,
            description=data.get('description', '').strip() or None,
            tax_rate=data.get('tax_rate', 0),
            valid_until=datetime.utcnow() + timedelta(days=30),  # Default 30 days
            notes=data.get('notes', '').strip() or None
        )
        
        db.session.add(quote)
        db.session.flush()  # Get the quote ID
        
        # Add quote items
        items_data = data.get('items', [])
        subtotal = 0
        
        for item_data in items_data:
            description = item_data.get('description', '').strip()
            quantity = float(item_data.get('quantity', 1))
            unit_price = float(item_data.get('unit_price', 0))
            total_price = quantity * unit_price
            
            if description:
                item = QuoteItem(
                    quote_id=quote.id,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price
                )
                db.session.add(item)
                subtotal += total_price
        
        # Calculate totals
        quote.subtotal = subtotal
        quote.tax_amount = subtotal * (quote.tax_rate / 100)
        quote.total = quote.subtotal + quote.tax_amount
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote created successfully',
            'quote': quote.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>', methods=['GET'])
@token_required
def get_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        quote_dict = quote.to_dict()
        quote_dict['items'] = [item.to_dict() for item in quote.items]
        
        return jsonify({
            'success': True,
            'quote': quote_dict
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>', methods=['PUT'])
@token_required
def update_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update quote fields
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({'error': 'Title is required'}), 400
            quote.title = title
        
        if 'description' in data:
            quote.description = data['description'].strip() or None
        if 'tax_rate' in data:
            quote.tax_rate = float(data['tax_rate'])
        if 'valid_until' in data and data['valid_until']:
            quote.valid_until = datetime.fromisoformat(data['valid_until'].replace('Z', '+00:00'))
        if 'notes' in data:
            quote.notes = data['notes'].strip() or None
        if 'status' in data:
            quote.status = data['status']
        
        # Update items if provided
        if 'items' in data:
            # Delete existing items
            QuoteItem.query.filter_by(quote_id=quote.id).delete()
            
            # Add new items
            items_data = data['items']
            subtotal = 0
            
            for item_data in items_data:
                description = item_data.get('description', '').strip()
                quantity = float(item_data.get('quantity', 1))
                unit_price = float(item_data.get('unit_price', 0))
                total_price = quantity * unit_price
                
                if description:
                    item = QuoteItem(
                        quote_id=quote.id,
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price
                    )
                    db.session.add(item)
                    subtotal += total_price
            
            # Recalculate totals
            quote.subtotal = subtotal
            quote.tax_amount = subtotal * (quote.tax_rate / 100)
            quote.total = quote.subtotal + quote.tax_amount
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote updated successfully',
            'quote': quote.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>', methods=['DELETE'])
@token_required
def delete_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        # Check if quote has associated jobs
        if quote.jobs:
            return jsonify({
                'error': 'Cannot delete quote with associated jobs'
            }), 400
        
        # Delete quote items first
        QuoteItem.query.filter_by(quote_id=quote.id).delete()
        
        # Delete quote
        db.session.delete(quote)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>/send', methods=['POST'])
@token_required
def send_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        if quote.status == 'draft':
            quote.status = 'sent'
            db.session.commit()
        
        # TODO: Implement email sending logic here
        
        return jsonify({
            'success': True,
            'message': 'Quote sent successfully',
            'quote': quote.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to send quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>/accept', methods=['POST'])
@token_required
def accept_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        quote.status = 'accepted'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote accepted successfully',
            'quote': quote.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to accept quote: {str(e)}'}), 500

@quotes_bp.route('/<int:quote_id>/reject', methods=['POST'])
@token_required
def reject_quote(current_user, quote_id):
    try:
        quote = Quote.query.filter_by(
            id=quote_id, 
            user_id=current_user.id
        ).first()
        
        if not quote:
            return jsonify({'error': 'Quote not found'}), 404
        
        quote.status = 'rejected'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Quote rejected',
            'quote': quote.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to reject quote: {str(e)}'}), 500

@quotes_bp.route('/stats', methods=['GET'])
@token_required
def get_quote_stats(current_user):
    try:
        total_quotes = Quote.query.filter_by(user_id=current_user.id).count()
        draft_quotes = Quote.query.filter_by(user_id=current_user.id, status='draft').count()
        sent_quotes = Quote.query.filter_by(user_id=current_user.id, status='sent').count()
        accepted_quotes = Quote.query.filter_by(user_id=current_user.id, status='accepted').count()
        rejected_quotes = Quote.query.filter_by(user_id=current_user.id, status='rejected').count()
        
        # Calculate total value
        total_value = db.session.query(db.func.sum(Quote.total)).filter_by(
            user_id=current_user.id
        ).scalar() or 0
        
        accepted_value = db.session.query(db.func.sum(Quote.total)).filter_by(
            user_id=current_user.id, status='accepted'
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_quotes': total_quotes,
                'draft_quotes': draft_quotes,
                'sent_quotes': sent_quotes,
                'accepted_quotes': accepted_quotes,
                'rejected_quotes': rejected_quotes,
                'total_value': float(total_value),
                'accepted_value': float(accepted_value),
                'acceptance_rate': (accepted_quotes / sent_quotes * 100) if sent_quotes > 0 else 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch quote stats: {str(e)}'}), 500

