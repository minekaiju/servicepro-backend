from flask import Blueprint, request, jsonify
from src.models.user import db, Job, Customer, Quote
from src.routes.auth import token_required
from datetime import datetime, timedelta
import uuid

jobs_bp = Blueprint('jobs', __name__)

def generate_job_number():
    return f"JB-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@jobs_bp.route('/', methods=['GET'])
@token_required
def get_jobs(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '', type=str)
        search = request.args.get('search', '', type=str)
        date_from = request.args.get('date_from', '', type=str)
        date_to = request.args.get('date_to', '', type=str)
        
        query = Job.query.filter_by(user_id=current_user.id)
        
        if status:
            query = query.filter_by(status=status)
        
        if search:
            query = query.join(Customer).filter(
                db.or_(
                    Job.title.ilike(f'%{search}%'),
                    Job.job_number.ilike(f'%{search}%'),
                    Customer.name.ilike(f'%{search}%')
                )
            )
        
        if date_from:
            try:
                from_date = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_date >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_date <= to_date)
            except ValueError:
                pass
        
        jobs = query.order_by(Job.scheduled_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'jobs': [job.to_dict() for job in jobs.items],
            'pagination': {
                'page': jobs.page,
                'pages': jobs.pages,
                'per_page': jobs.per_page,
                'total': jobs.total,
                'has_next': jobs.has_next,
                'has_prev': jobs.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch jobs: {str(e)}'}), 500

@jobs_bp.route('/', methods=['POST'])
@token_required
def create_job(current_user):
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
        
        # Verify quote if provided
        quote_id = data.get('quote_id')
        if quote_id:
            quote = Quote.query.filter_by(
                id=quote_id, 
                user_id=current_user.id,
                customer_id=customer_id
            ).first()
            
            if not quote:
                return jsonify({'error': 'Quote not found'}), 404
        
        job = Job(
            user_id=current_user.id,
            customer_id=customer_id,
            quote_id=quote_id,
            job_number=generate_job_number(),
            title=title,
            description=data.get('description', '').strip() or None,
            total_amount=data.get('total_amount', 0),
            notes=data.get('notes', '').strip() or None
        )
        
        # Set scheduling info
        if data.get('scheduled_date'):
            try:
                job.scheduled_date = datetime.fromisoformat(
                    data['scheduled_date'].replace('Z', '+00:00')
                )
            except ValueError:
                return jsonify({'error': 'Invalid scheduled date format'}), 400
        
        if data.get('scheduled_time'):
            job.scheduled_time = data['scheduled_time']
        
        if data.get('duration_hours'):
            job.duration_hours = float(data['duration_hours'])
        
        db.session.add(job)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job created successfully',
            'job': job.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>', methods=['GET'])
@token_required
def get_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'success': True,
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@token_required
def update_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update job fields
        if 'title' in data:
            title = data['title'].strip()
            if not title:
                return jsonify({'error': 'Title is required'}), 400
            job.title = title
        
        if 'description' in data:
            job.description = data['description'].strip() or None
        if 'total_amount' in data:
            job.total_amount = float(data['total_amount'])
        if 'notes' in data:
            job.notes = data['notes'].strip() or None
        if 'status' in data:
            job.status = data['status']
        
        # Update scheduling info
        if 'scheduled_date' in data:
            if data['scheduled_date']:
                try:
                    job.scheduled_date = datetime.fromisoformat(
                        data['scheduled_date'].replace('Z', '+00:00')
                    )
                except ValueError:
                    return jsonify({'error': 'Invalid scheduled date format'}), 400
            else:
                job.scheduled_date = None
        
        if 'scheduled_time' in data:
            job.scheduled_time = data['scheduled_time'] or None
        
        if 'duration_hours' in data:
            job.duration_hours = float(data['duration_hours']) if data['duration_hours'] else None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job updated successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to update job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
@token_required
def delete_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        # Check if job has associated invoices
        if job.invoices:
            return jsonify({
                'error': 'Cannot delete job with associated invoices'
            }), 400
        
        db.session.delete(job)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>/start', methods=['POST'])
@token_required
def start_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job.status != 'scheduled':
            return jsonify({'error': 'Job must be scheduled to start'}), 400
        
        job.status = 'in_progress'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job started successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to start job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>/complete', methods=['POST'])
@token_required
def complete_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job.status not in ['scheduled', 'in_progress']:
            return jsonify({'error': 'Job must be scheduled or in progress to complete'}), 400
        
        job.status = 'completed'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job completed successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to complete job: {str(e)}'}), 500

@jobs_bp.route('/<int:job_id>/cancel', methods=['POST'])
@token_required
def cancel_job(current_user, job_id):
    try:
        job = Job.query.filter_by(
            id=job_id, 
            user_id=current_user.id
        ).first()
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        if job.status == 'completed':
            return jsonify({'error': 'Cannot cancel completed job'}), 400
        
        job.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Job cancelled successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to cancel job: {str(e)}'}), 500

@jobs_bp.route('/calendar', methods=['GET'])
@token_required
def get_calendar_jobs(current_user):
    try:
        start_date = request.args.get('start', '', type=str)
        end_date = request.args.get('end', '', type=str)
        
        query = Job.query.filter_by(user_id=current_user.id)
        
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_date >= start)
            except ValueError:
                pass
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Job.scheduled_date <= end)
            except ValueError:
                pass
        
        jobs = query.filter(Job.scheduled_date.isnot(None)).all()
        
        # Format for calendar
        calendar_events = []
        for job in jobs:
            event = {
                'id': job.id,
                'title': f"{job.customer.name} - {job.title}",
                'start': job.scheduled_date.isoformat() if job.scheduled_date else None,
                'end': None,
                'allDay': not job.scheduled_time,
                'backgroundColor': {
                    'scheduled': '#3b82f6',
                    'in_progress': '#f59e0b',
                    'completed': '#10b981',
                    'cancelled': '#ef4444'
                }.get(job.status, '#6b7280'),
                'extendedProps': {
                    'job': job.to_dict()
                }
            }
            
            # Calculate end time if duration is provided
            if job.scheduled_date and job.duration_hours:
                end_time = job.scheduled_date + timedelta(hours=float(job.duration_hours))
                event['end'] = end_time.isoformat()
            
            calendar_events.append(event)
        
        return jsonify({
            'success': True,
            'events': calendar_events
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch calendar jobs: {str(e)}'}), 500

@jobs_bp.route('/stats', methods=['GET'])
@token_required
def get_job_stats(current_user):
    try:
        total_jobs = Job.query.filter_by(user_id=current_user.id).count()
        scheduled_jobs = Job.query.filter_by(user_id=current_user.id, status='scheduled').count()
        in_progress_jobs = Job.query.filter_by(user_id=current_user.id, status='in_progress').count()
        completed_jobs = Job.query.filter_by(user_id=current_user.id, status='completed').count()
        cancelled_jobs = Job.query.filter_by(user_id=current_user.id, status='cancelled').count()
        
        # Calculate total revenue
        total_revenue = db.session.query(db.func.sum(Job.total_amount)).filter_by(
            user_id=current_user.id, status='completed'
        ).scalar() or 0
        
        # Jobs this month
        current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        jobs_this_month = Job.query.filter(
            Job.user_id == current_user.id,
            Job.created_at >= current_month_start
        ).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_jobs': total_jobs,
                'scheduled_jobs': scheduled_jobs,
                'in_progress_jobs': in_progress_jobs,
                'completed_jobs': completed_jobs,
                'cancelled_jobs': cancelled_jobs,
                'total_revenue': float(total_revenue),
                'jobs_this_month': jobs_this_month,
                'completion_rate': (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch job stats: {str(e)}'}), 500

