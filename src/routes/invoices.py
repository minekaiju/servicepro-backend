from flask import Blueprint, request, jsonify
from src.models.user import db, Invoice, Customer, Job
from src.routes.auth import token_required
from datetime import datetime, timedelta
import uuid

invoices_bp = Blueprint('invoices', __name__)

def generate_invoice_number():
    return f"INV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@invoices_bp.route('/', methods=['GET'])
@token_required
def get_invoices(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '', type=str)
        search = request.args.get('search', '', type=str)
        
        query = Invoice.query.filter_by(user_id=current_user.id)
        
        if status:
            query = query.filter_by(status=status)
        
        if search:
            query = query.join(Customer).filter(
                db.or_(
                    Invoice.invoice_number.ilike(f'%{search}%'),
                    Customer.name.ilike(f'%{search}%')
                )
            )
        
        invoices = query.order_by(Invoice.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'invoices': [invoice.to_dict() for invoice in invoices.items],
            'pagination': {
                'page': invoices.page,
                'pages': invoices.pages,
                'per_page': invoices.per_page,
                'total': invoices.total,
                'has_next': invoices.has_next,
                'has_prev': invoices.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch invoices: {str(e)}'}), 500

@invoices_bp.route('/', methods=['POST'])
@token_required
def create_invoice(current_user):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        customer_id = data.get('customer_id')
        
        if not customer_id:
            return jsonify({'error': 'Customer ID is required'}), 400
        
        # Verify customer belongs to user
        customer = Customer.query.filter_by(
            id=customer_id, 
            user_id=current_user.id
        ).first()
        
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Verify job if provided
        job_id = data.get('job_id')
        if job_id:
            job = Job.query.filter_by(
                id=job_id, 
                user_id=current_user.id,
                customer_id=customer_id
            ).first()
            
            if not job:
                return jsonify({'error': 'Job not found'}), 404
        
        subtotal = float(data.get('subtotal', 0))
        tax_rate = float(data.get('tax_rate', 0))
        tax_amount = subtotal * (tax_rate / 100)
        total = subtotal + tax_amount
        
        invoice = Invoice(
            user_id=current_user.id,
            customer_id=customer_id,
            job_id=job_id,
            invoice_number=generate_invoice_number(),
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            due_date=datetime.utcnow() + timedelta(days=30),  # Default 30 days
            notes=data.get('notes', '').strip() or None
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice created successfully',
            'invoice': invoice.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create invoice: {str(e)}'}), 500

@invoices_bp.route('/<int:invoice_id>', methods=['GET'])
@token_required
def get_invoice(current_user, invoice_id):
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id, 
            user_id=current_user.id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        return jsonify({
            'success': True,
            'invoice': invoice.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch invoice: {str(e)}'}), 500

@invoices_bp.route('/<int:invoice_id>', methods=['PUT'])
@token_required
def update_invoice(current_user, invoice_id):
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id, 
            user_id=current_user.id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update invoice fields
        if 'subtotal' in data:
            invoice.subtotal = float(data['subtotal'])
        if 'tax_rate' in data:
            invoice.tax_rate = float(data['tax_rate'])
        if 'due_date' in data and data['due_date']:
            try:
                invoice.due_date = datetime.fromisoformat(
                    data['due_date'].replace('Z', '+00:00')
                )
            except ValueError:
                return jsonify({'error': 'Invalid due date format'}), 400
        if 'notes' in data:
            invoice.notes = data['notes'].strip() or None
        if 'status' in data:
            invoice.status = data['status']
            if data['status'] == 'paid' and not invoice.paid_date:
                invoice.paid_date = datetime.utcnow()
        
        # Recalculate totals
        invoice.tax_amount = invoice.subtotal * (invoice.tax_rate / 100)
        invoice.total = invoice.subtotal + invoice.tax_amount
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice updated successfully',
            'invoice': invoice.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update invoice: {str(e)}'}), 500

@invoices_bp.route('/<int:invoice_id>', methods=['DELETE'])
@token_required
def delete_invoice(current_user, invoice_id):
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id, 
            user_id=current_user.id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        if invoice.status == 'paid':
            return jsonify({'error': 'Cannot delete paid invoice'}), 400
        
        db.session.delete(invoice)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete invoice: {str(e)}'}), 500

@invoices_bp.route('/<int:invoice_id>/send', methods=['POST'])
@token_required
def send_invoice(current_user, invoice_id):
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id, 
            user_id=current_user.id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        if invoice.status == 'draft':
            invoice.status = 'sent'
            db.session.commit()
        
        # TODO: Implement email sending logic here
        
        return jsonify({
            'success': True,
            'message': 'Invoice sent successfully',
            'invoice': invoice.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to send invoice: {str(e)}'}), 500

@invoices_bp.route('/<int:invoice_id>/mark-paid', methods=['POST'])
@token_required
def mark_invoice_paid(current_user, invoice_id):
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id, 
            user_id=current_user.id
        ).first()
        
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        invoice.status = 'paid'
        invoice.paid_date = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Invoice marked as paid',
            'invoice': invoice.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to mark invoice as paid: {str(e)}'}), 500

@invoices_bp.route('/overdue', methods=['GET'])
@token_required
def get_overdue_invoices(current_user):
    try:
        overdue_invoices = Invoice.query.filter(
            Invoice.user_id == current_user.id,
            Invoice.status.in_(['sent']),
            Invoice.due_date < datetime.utcnow()
        ).all()
        
        # Update status to overdue
        for invoice in overdue_invoices:
            if invoice.status != 'overdue':
                invoice.status = 'overdue'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'invoices': [invoice.to_dict() for invoice in overdue_invoices]
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to fetch overdue invoices: {str(e)}'}), 500

@invoices_bp.route('/stats', methods=['GET'])
@token_required
def get_invoice_stats(current_user):
    try:
        total_invoices = Invoice.query.filter_by(user_id=current_user.id).count()
        draft_invoices = Invoice.query.filter_by(user_id=current_user.id, status='draft').count()
        sent_invoices = Invoice.query.filter_by(user_id=current_user.id, status='sent').count()
        paid_invoices = Invoice.query.filter_by(user_id=current_user.id, status='paid').count()
        overdue_invoices = Invoice.query.filter_by(user_id=current_user.id, status='overdue').count()
        
        # Calculate total amounts
        total_amount = db.session.query(db.func.sum(Invoice.total)).filter_by(
            user_id=current_user.id
        ).scalar() or 0
        
        paid_amount = db.session.query(db.func.sum(Invoice.total)).filter_by(
            user_id=current_user.id, status='paid'
        ).scalar() or 0
        
        outstanding_amount = db.session.query(db.func.sum(Invoice.total)).filter(
            Invoice.user_id == current_user.id,
            Invoice.status.in_(['sent', 'overdue'])
        ).scalar() or 0
        
        # This month's revenue
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_revenue = db.session.query(db.func.sum(Invoice.total)).filter(
            Invoice.user_id == current_user.id,
            Invoice.status == 'paid',
            Invoice.paid_date >= current_month_start
        ).scalar() or 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_invoices': total_invoices,
                'draft_invoices': draft_invoices,
                'sent_invoices': sent_invoices,
                'paid_invoices': paid_invoices,
                'overdue_invoices': overdue_invoices,
                'total_amount': float(total_amount),
                'paid_amount': float(paid_amount),
                'outstanding_amount': float(outstanding_amount),
                'monthly_revenue': float(monthly_revenue),
                'payment_rate': (paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch invoice stats: {str(e)}'}), 500

