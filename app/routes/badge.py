from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.models import Badge, User, UserBadge
from app.extensions import db
from app.security.rate_limit_policies import rate_limit_route, user_or_ip_identifier

badge_bp = Blueprint('badge_api', __name__)

@badge_bp.route('/api/badges', methods=['GET'])
def get_badges():
    badges = Badge.query.all()
    return jsonify([badge.to_dict() for badge in badges])

@badge_bp.route('/api/users/<int:user_id>/badges', methods=['GET'])
def get_user_badges(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify([ub.badge.to_dict() for ub in user.badges])

@badge_bp.route('/api/assign_badge', methods=['POST'])
@login_required
@rate_limit_route(
    "api_badge_assign",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many badge assignments.",
    methods={"POST"},
)
def assign_badge_api():
    if not getattr(current_user, 'is_admin', False) and not getattr(current_user, 'is_host', False):
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    # --- Bulk assignment support ---
    user_ids = data.get('user_ids')
    badge_id = data.get('badge_id')
    if not badge_id or not user_ids:
        return jsonify({'error': 'Missing user_ids or badge_id'}), 400
    badge = Badge.query.get_or_404(badge_id)
    assigned = []
    already = []
    for user_id in user_ids:
        user = User.query.get(user_id)
        if not user:
            continue
        if any(ub.badge_id == badge.id for ub in user.badges):
            already.append(user_id)
            continue
        user_badge = UserBadge()
        user_badge.user_id = user.id
        user_badge.badge_id = badge.id
        db.session.add(user_badge)
        assigned.append(user_id)
    db.session.commit()
    return jsonify({
        'message': f'Badge assigned to {len(assigned)} user(s).',
        'assigned': assigned,
        'already': already
    })

# You must implement this utility in core/badge_utils.py
from app.services.utils import auto_assign_badges

@badge_bp.route('/api/auto_assign_badges', methods=['POST'])
@login_required
@rate_limit_route(
    "api_badge_auto_assign",
    10,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many auto-assign requests.",
    methods={"POST"},
)
def auto_assign_badges_api():
    if not getattr(current_user, 'is_admin', False) and not getattr(current_user, 'is_host', False):
        return jsonify({'error': 'Unauthorized'}), 403
    auto_assign_badges()
    return jsonify({'message': 'Auto-assignment triggered'})