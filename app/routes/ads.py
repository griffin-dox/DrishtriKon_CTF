from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import login_required, current_user
import os
from werkzeug.utils import secure_filename
from datetime import datetime

from app.extensions import db
from app.models import User, UserRole, AdImage, AdPlacement, AdConfiguration, AdLocation
from app.forms import AdConfigurationForm, AdImageForm, AdPlacementForm
from app.routes.admin import admin_required
from app.services.utils import save_file
from app.security.rate_limit_policies import rate_limit_route, user_or_ip_identifier

ads_bp = Blueprint('ads', __name__)

ADS_IMAGE_MAX_BYTES = 2 * 1024 * 1024

@ads_bp.route('/admin/manage-ads')
@login_required
@admin_required
def manage_ads():
    # Get the current ad configuration
    config = AdConfiguration.query.first()
    if not config:
        config = AdConfiguration()
        config.use_google_ads = True
        db.session.add(config)
        db.session.commit()
        
    # Get all ad images
    images = AdImage.query.order_by(AdImage.created_at.desc()).all()
    
    # Get placements grouped by location
    placements = {}
    for location in AdLocation:
        placements[location.name] = AdPlacement.query.filter_by(location=location).all()
    
    # Get free (no exclusive ad) locations
    free_locations = []
    for location in AdLocation:
        exclusive = AdPlacement.query.filter_by(location=location, is_exclusive=True).first()
        if not exclusive:
            free_locations.append(location.name)
    
    # Forms
    config_form = AdConfigurationForm(obj=config)
    image_form = AdImageForm()
    placement_form = AdPlacementForm()
    
    # Populate the ad image dropdown
    placement_form.ad_image_id.choices = [(img.id, img.title) for img in images]
    
    return render_template(
        'admin/manage_ads.html',
        config=config,
        images=images,
        placements=placements,
        free_locations=free_locations,
        config_form=config_form,
        image_form=image_form,
        placement_form=placement_form
    )

@ads_bp.route('/admin/update-ad-config', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "ads_update_config",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many ad configuration updates.",
    methods={"POST"},
)
def update_ad_config():
    form = AdConfigurationForm()
    if form.validate_on_submit():
        config = AdConfiguration.query.first()
        if not config:
            config = AdConfiguration()
            db.session.add(config)
        
        config.use_google_ads = form.use_google_ads.data
        db.session.commit()
        flash('Ad configuration has been updated.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "danger")
                
    return redirect(url_for('ads.manage_ads'))

@ads_bp.route('/admin/upload-ad-image', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "ads_upload_image",
    10,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many ad image uploads.",
    methods={"POST"},
)
def upload_ad_image():
    form = AdImageForm()
    if form.validate_on_submit():
        # Handle file upload
        uploaded_file = form.image.data
        if request.content_length and request.content_length > ADS_IMAGE_MAX_BYTES:
            flash('File is too large. Max size is 2 MB.', 'danger')
            return redirect(url_for('ads.manage_ads'))

        uploaded_file.stream.seek(0, os.SEEK_END)
        file_size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)
        if file_size > ADS_IMAGE_MAX_BYTES:
            flash('File is too large. Max size is 2 MB.', 'danger')
            return redirect(url_for('ads.manage_ads'))

        filename = secure_filename(uploaded_file.filename)
        file_path = os.path.join('static', 'uploads', 'ads', filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save the file
        uploaded_file.save(file_path)
        
        # Create new ad image record
        ad_image = AdImage()
        ad_image.title = form.title.data
        ad_image.description = form.description.data
        ad_image.image_path = file_path
        ad_image.link_url = form.link_url.data
        ad_image.is_active = form.is_active.data
        
        db.session.add(ad_image)
        db.session.commit()
        
        flash('Ad image has been uploaded successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "danger")
    
    return redirect(url_for('ads.manage_ads'))

@ads_bp.route('/admin/delete-ad-image/<int:image_id>', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "ads_delete_image",
    30,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many ad image deletions.",
    methods={"POST"},
)
def delete_ad_image(image_id):
    ad_image = AdImage.query.get_or_404(image_id)
    
    # Delete file from disk if it exists
    try:
        if os.path.exists(ad_image.image_path):
            os.remove(ad_image.image_path)
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}")
    
    # Delete associated placements
    AdPlacement.query.filter_by(ad_image_id=ad_image.id).delete()
    
    # Delete ad image record
    db.session.delete(ad_image)
    db.session.commit()
    
    flash('Ad image and associated placements have been deleted.', 'success')
    return redirect(url_for('ads.manage_ads'))

@ads_bp.route('/admin/create-ad-placement', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "ads_create_placement",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many ad placement creations.",
    methods={"POST"},
)
def create_ad_placement():
    form = AdPlacementForm()
    
    # Dynamically set the choices for ad_image_id
    images = AdImage.query.all()
    form.ad_image_id.choices = [(img.id, img.title) for img in images]
    
    if form.validate_on_submit():
        location = AdLocation[form.location.data]
        
        # If this is an exclusive placement, remove any existing exclusive placements for this location
        if form.is_exclusive.data:
            AdPlacement.query.filter_by(location=location, is_exclusive=True).delete()
        
        # Create new placement
        placement = AdPlacement()
        placement.ad_image_id = form.ad_image_id.data
        placement.location = location
        placement.is_exclusive = form.is_exclusive.data
        placement.start_date = form.start_date.data
        placement.end_date = form.end_date.data
        
        db.session.add(placement)
        db.session.commit()
        
        flash('Ad placement has been created successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "danger")
    
    return redirect(url_for('ads.manage_ads'))

@ads_bp.route('/admin/delete-ad-placement/<int:placement_id>', methods=['POST'])
@login_required
@admin_required
@rate_limit_route(
    "ads_delete_placement",
    60,
    3600,
    identifier_func=user_or_ip_identifier,
    message="Too many ad placement deletions.",
    methods={"POST"},
)
def delete_ad_placement(placement_id):
    placement = AdPlacement.query.get_or_404(placement_id)
    db.session.delete(placement)
    db.session.commit()
    
    flash('Ad placement has been deleted.', 'success')
    return redirect(url_for('ads.manage_ads'))

# API endpoints for the frontend to fetch ads
@ads_bp.route('/api/get-ad/<location>')
def get_ad(location):
    try:
        # Convert the location string to enum, handling both formats
        # This allows both formats: left_sidebar OR LEFT_SIDEBAR
        location_upper = location.upper()
        ad_location = None
        
        # First try with the string as-is
        try:
            ad_location = AdLocation[location_upper]
        except KeyError:
            # Try with common transformations
            if location_upper == "LEFT_SIDEBAR":
                ad_location = AdLocation.LEFT_SIDEBAR
            elif location_upper == "RIGHT_SIDEBAR":
                ad_location = AdLocation.RIGHT_SIDEBAR
            elif location_upper == "HORIZONTAL_TOP":
                ad_location = AdLocation.HORIZONTAL_TOP
            elif location_upper == "HORIZONTAL_BOTTOM":
                ad_location = AdLocation.HORIZONTAL_BOTTOM
            elif location_upper == "HOME_HORIZONTAL":
                ad_location = AdLocation.HOME_HORIZONTAL
                
        if ad_location is None:
            return jsonify({'error': 'Invalid location'}), 400
    except Exception:
        return jsonify({'error': 'Invalid location'}), 400
    
    # Get the ad configuration
    config = AdConfiguration.query.first()
    if not config:
        config = AdConfiguration()
        config.use_google_ads = True
        db.session.add(config)
        db.session.commit()
    
    # If Google Ads is enabled, return that info
    if config.use_google_ads:
        return jsonify({
            'use_google_ads': True
        })
    
    # Check for exclusive placement
    exclusive = AdPlacement.query.filter(
        AdPlacement.location == ad_location,
        AdPlacement.is_exclusive == True,
        (AdPlacement.start_date == None) | (AdPlacement.start_date <= datetime.utcnow()),
        (AdPlacement.end_date == None) | (AdPlacement.end_date >= datetime.utcnow())
    ).join(AdImage).filter(AdImage.is_active == True).first()
    
    if exclusive:
        return jsonify({
            'use_google_ads': False,
            'ad': {
                'id': exclusive.ad_image.id,
                'title': exclusive.ad_image.title,
                'description': exclusive.ad_image.description,
                'image_path': exclusive.ad_image.image_path,
                'link_url': exclusive.ad_image.link_url
            }
        })
    
    # Get all non-exclusive placements for this location
    placements = AdPlacement.query.filter(
        AdPlacement.location == ad_location,
        AdPlacement.is_exclusive == False,
        (AdPlacement.start_date == None) | (AdPlacement.start_date <= datetime.utcnow()),
        (AdPlacement.end_date == None) | (AdPlacement.end_date >= datetime.utcnow())
    ).join(AdImage).filter(AdImage.is_active == True).all()
    
    if placements:
        # For this simple implementation, just return the first available placement
        # In a real-world implementation, you'd implement rotation, weighted distribution, etc.
        placement = placements[0]
        return jsonify({
            'use_google_ads': False,
            'ad': {
                'id': placement.ad_image.id,
                'title': placement.ad_image.title,
                'description': placement.ad_image.description,
                'image_path': placement.ad_image.image_path,
                'link_url': placement.ad_image.link_url
            }
        })
    
    # If no custom ads are available, fallback to Google Ads
    return jsonify({
        'use_google_ads': True
    })