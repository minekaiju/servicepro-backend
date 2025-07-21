from flask import Blueprint, request, jsonify
from src.models.user import db, User, Customer, Quote, Job, Invoice
from src.routes.auth import token_required
from datetime import datetime, timedelta
from sqlalchemy import func, extract

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    try:
        # Basic counts
        total_customers = Customer.query.filter_by(user_id=current_user.id).count()
        total_quotes = Quote.query.filter_by(user_id=current_user.id).count()
        total_jobs = Job.query.filter_by(user_id=current_user.id).count()
        total_invoices = Invoice.query.filter_by(user_id=current_user.id).count()
        
        # Revenue calculations
        total_revenue = db.session.query(func.sum(Invoice.total)).filter(
            Invoice.user_id == current_user.id,
            Invoice.status == 'paid'
        ).scalar() or 0
        
        outstanding_amount = db.session.query(func.sum(Invoice.total)).filter(
            Invoice.user_id == current_user.id,
            Invoice.status.in_(['sent', 'overdue'])
        ).scalar() or 0
        
        # This month's stats
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        monthly_revenue = db.session.query(func.sum(Invoice.total)).filter(
            Invoice.user_id == current_user.id,
            Invoice.status == 'paid',
            Invoice.paid_date >= current_month_start
        ).scalar() or 0
        
        monthly_jobs = Job.query.filter(
            Job.user_id == current_user.id,
            Job.created_at >= current_month_start
        ).count()
        
        monthly_quotes = Quote.query.filter(
            Quote.user_id == current_user.id,
            Quote.created_at >= current_month_start
        ).count()
        
        # Recent activity
        recent_quotes = Quote.query.filter_by(user_id=current_user.id).order_by(
            Quote.created_at.desc()
        ).limit(5).all()
        
        recent_jobs = Job.query.filter_by(user_id=current_user.id).order_by(
            Job.created_at.desc()
        ).limit(5).all()
        
        # Upcoming jobs
        upcoming_jobs = Job.query.filter(
            Job.user_id == current_user.id,
            Job.scheduled_date >= datetime.now(),
            Job.status.in_(['scheduled', 'in_progress'])
        ).order_by(Job.scheduled_date.asc()).limit(5).all()
        
        # Overdue invoices
        overdue_invoices = Invoice.query.filter(
            Invoice.user_id == current_user.id,
            Invoice.status.in_(['sent']),
            Invoice.due_date < datetime.utcnow()
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'totals': {
                    'customers': total_customers,
                    'quotes': total_quotes,
                    'jobs': total_jobs,
                    'invoices': total_invoices
                },
                'revenue': {
                    'total': float(total_revenue),
                    'outstanding': float(outstanding_amount),
                    'monthly': float(monthly_revenue)
                },
                'monthly': {
                    'revenue': float(monthly_revenue),
                    'jobs': monthly_jobs,
                    'quotes': monthly_quotes
                },
                'alerts': {
                    'overdue_invoices': overdue_invoices,
                    'upcoming_jobs': len(upcoming_jobs)
                }
            },
            'recent_activity': {
                'quotes': [quote.to_dict() for quote in recent_quotes],
                'jobs': [job.to_dict() for job in recent_jobs]
            },
            'upcoming_jobs': [job.to_dict() for job in upcoming_jobs]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch dashboard stats: {str(e)}'}), 500

@dashboard_bp.route('/revenue-chart', methods=['GET'])
@token_required
def get_revenue_chart(current_user):
    try:
        period = request.args.get('period', 'month')  # month, quarter, year
        
        if period == 'month':
            # Last 12 months
            months_data = []
            for i in range(12):
                month_start = (datetime.now().replace(day=1) - timedelta(days=32*i)).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                revenue = db.session.query(func.sum(Invoice.total)).filter(
                    Invoice.user_id == current_user.id,
                    Invoice.status == 'paid',
                    Invoice.paid_date >= month_start,
                    Invoice.paid_date <= month_end
                ).scalar() or 0
                
                months_data.append({
                    'period': month_start.strftime('%Y-%m'),
                    'label': month_start.strftime('%b %Y'),
                    'revenue': float(revenue)
                })
            
            months_data.reverse()
            return jsonify({
                'success': True,
                'data': months_data
            }), 200
            
        elif period == 'quarter':
            # Last 4 quarters
            quarters_data = []
            current_date = datetime.now()
            
            for i in range(4):
                quarter_start = datetime(current_date.year, ((current_date.month - 1) // 3) * 3 + 1 - i*3, 1)
                if quarter_start.month <= 0:
                    quarter_start = quarter_start.replace(year=quarter_start.year - 1, month=quarter_start.month + 12)
                
                quarter_end = (quarter_start + timedelta(days=95)).replace(day=1) - timedelta(days=1)
                
                revenue = db.session.query(func.sum(Invoice.total)).filter(
                    Invoice.user_id == current_user.id,
                    Invoice.status == 'paid',
                    Invoice.paid_date >= quarter_start,
                    Invoice.paid_date <= quarter_end
                ).scalar() or 0
                
                quarters_data.append({
                    'period': f"{quarter_start.year}-Q{((quarter_start.month - 1) // 3) + 1}",
                    'label': f"Q{((quarter_start.month - 1) // 3) + 1} {quarter_start.year}",
                    'revenue': float(revenue)
                })
            
            quarters_data.reverse()
            return jsonify({
                'success': True,
                'data': quarters_data
            }), 200
        
        else:  # year
            # Last 3 years
            years_data = []
            current_year = datetime.now().year
            
            for i in range(3):
                year = current_year - i
                year_start = datetime(year, 1, 1)
                year_end = datetime(year, 12, 31)
                
                revenue = db.session.query(func.sum(Invoice.total)).filter(
                    Invoice.user_id == current_user.id,
                    Invoice.status == 'paid',
                    Invoice.paid_date >= year_start,
                    Invoice.paid_date <= year_end
                ).scalar() or 0
                
                years_data.append({
                    'period': str(year),
                    'label': str(year),
                    'revenue': float(revenue)
                })
            
            years_data.reverse()
            return jsonify({
                'success': True,
                'data': years_data
            }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch revenue chart: {str(e)}'}), 500

@dashboard_bp.route('/job-status-chart', methods=['GET'])
@token_required
def get_job_status_chart(current_user):
    try:
        # Get job counts by status
        job_stats = db.session.query(
            Job.status,
            func.count(Job.id).label('count')
        ).filter_by(user_id=current_user.id).group_by(Job.status).all()
        
        status_data = []
        status_colors = {
            'scheduled': '#3b82f6',
            'in_progress': '#f59e0b',
            'completed': '#10b981',
            'cancelled': '#ef4444'
        }
        
        for status, count in job_stats:
            status_data.append({
                'status': status,
                'count': count,
                'color': status_colors.get(status, '#6b7280')
            })
        
        return jsonify({
            'success': True,
            'data': status_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch job status chart: {str(e)}'}), 500

@dashboard_bp.route('/quote-conversion-chart', methods=['GET'])
@token_required
def get_quote_conversion_chart(current_user):
    try:
        # Get quote counts by status
        quote_stats = db.session.query(
            Quote.status,
            func.count(Quote.id).label('count')
        ).filter_by(user_id=current_user.id).group_by(Quote.status).all()
        
        status_data = []
        status_colors = {
            'draft': '#6b7280',
            'sent': '#3b82f6',
            'accepted': '#10b981',
            'rejected': '#ef4444',
            'expired': '#f59e0b'
        }
        
        for status, count in quote_stats:
            status_data.append({
                'status': status,
                'count': count,
                'color': status_colors.get(status, '#6b7280')
            })
        
        return jsonify({
            'success': True,
            'data': status_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch quote conversion chart: {str(e)}'}), 500

@dashboard_bp.route('/top-customers', methods=['GET'])
@token_required
def get_top_customers(current_user):
    try:
        limit = request.args.get('limit', 5, type=int)
        
        # Get customers with most revenue
        top_customers = db.session.query(
            Customer,
            func.sum(Invoice.total).label('total_revenue'),
            func.count(Job.id).label('total_jobs')
        ).join(
            Invoice, Customer.id == Invoice.customer_id
        ).outerjoin(
            Job, Customer.id == Job.customer_id
        ).filter(
            Customer.user_id == current_user.id,
            Invoice.status == 'paid'
        ).group_by(Customer.id).order_by(
            func.sum(Invoice.total).desc()
        ).limit(limit).all()
        
        customers_data = []
        for customer, revenue, jobs in top_customers:
            customer_dict = customer.to_dict()
            customer_dict['total_revenue'] = float(revenue or 0)
            customer_dict['total_jobs'] = jobs or 0
            customers_data.append(customer_dict)
        
        return jsonify({
            'success': True,
            'customers': customers_data
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch top customers: {str(e)}'}), 500

@dashboard_bp.route('/recent-activity', methods=['GET'])
@token_required
def get_recent_activity(current_user):
    try:
        limit = request.args.get('limit', 10, type=int)
        
        # Get recent quotes
        recent_quotes = Quote.query.filter_by(user_id=current_user.id).order_by(
            Quote.created_at.desc()
        ).limit(limit//2).all()
        
        # Get recent jobs
        recent_jobs = Job.query.filter_by(user_id=current_user.id).order_by(
            Job.created_at.desc()
        ).limit(limit//2).all()
        
        # Get recent invoices
        recent_invoices = Invoice.query.filter_by(user_id=current_user.id).order_by(
            Invoice.created_at.desc()
        ).limit(limit//2).all()
        
        # Combine and sort by date
        activities = []
        
        for quote in recent_quotes:
            activities.append({
                'type': 'quote',
                'id': quote.id,
                'title': f"Quote {quote.quote_number} created",
                'description': f"Quote for {quote.customer.name}: {quote.title}",
                'date': quote.created_at.isoformat(),
                'status': quote.status,
                'amount': float(quote.total)
            })
        
        for job in recent_jobs:
            activities.append({
                'type': 'job',
                'id': job.id,
                'title': f"Job {job.job_number} created",
                'description': f"Job for {job.customer.name}: {job.title}",
                'date': job.created_at.isoformat(),
                'status': job.status,
                'amount': float(job.total_amount)
            })
        
        for invoice in recent_invoices:
            activities.append({
                'type': 'invoice',
                'id': invoice.id,
                'title': f"Invoice {invoice.invoice_number} created",
                'description': f"Invoice for {invoice.customer.name}",
                'date': invoice.created_at.isoformat(),
                'status': invoice.status,
                'amount': float(invoice.total)
            })
        
        # Sort by date (newest first)
        activities.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({
            'success': True,
            'activities': activities[:limit]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch recent activity: {str(e)}'}), 500

