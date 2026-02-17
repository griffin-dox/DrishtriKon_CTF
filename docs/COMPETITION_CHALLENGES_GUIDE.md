# Competition and Challenges Management Guide

## Overview

This guide explains how to:

1. Create challenges
2. Add/bind challenges to competitions
3. Show/hide specific challenges
4. Delete competitions
5. Manage competition status

---

## 1. Creating Challenges for a Competition

### Step-by-Step Process

1. **Navigate to Host Dashboard**
   - Log in as a HOST or ADMIN user
   - Click "Host Dashboard" or go to `/host/`

2. **Select a Competition**
   - Find the competition you want to add challenges to
   - Click "Manage" or go to `/host/competitions/manage/<competition_id>`

3. **Create a Challenge**
   - In the Manage Competition page, click "Add Challenge" or the button to create a new challenge
   - Go to `/host/create_challenge/<competition_id>` (directly accessible)

4. **Fill in Challenge Details**

   ```text
   - Title: Name of the challenge
   - Description: Detailed description of what players need to do
   - Flag: The correct answer/flag that players must submit
   - Points: Points awarded for solving (default recommended: 100, 200, 500, 1000)
   - Type: Challenge type (e.g., "Web", "Crypto", "Reverse", "Forensics", "Programming")
   - Difficulty: 1-5 (1=Easy, 5=Very Hard)
   - Hint: Optional hint for players
   - Is Lab: Mark as true if it's a lab challenge
   - File Upload: Upload related files (allowed: zip, txt, pdf, png, jpg, jpeg)
   - Visibility:
     - PUBLIC: Visible to all users
     - COMPETITION: Only visible within this competition
   ```

5. **Submit**
   - Click "Create Challenge"
   - Challenge is automatically added to the competition and linked via `CompetitionChallenge` junction table

### Technical Details

When you create a challenge:

- A `Challenge` record is created with the details you provide
- A `CompetitionChallenge` record is created linking the challenge to the competition
- If a file is uploaded, it's stored in S3 (using the configured S3 buckets)
- The challenge gets `visibility_scope = COMPETITION` by default (or PUBLIC if marked public)
- The challenge is associated with the creator's user ID

---

## 2. Binding Existing Challenges to a Competition

### Method 1: From Manage Competition Page

**NOTE:** This feature may need to be implemented if not already available. Currently, you can only:

- Create new challenges directly in a competition
- Edit existing challenges within a competition
- Delete challenges from a competition

### Method 2: Direct Database (Admin Only)

If you need to link existing challenges manually:

```sql
-- Add existing challenge to competition
INSERT INTO competition_challenges (competition_id, challenge_id, is_active)
VALUES (
  <competition_id>,
  <challenge_id>,
  TRUE
);
```

### API Approach

Create a new host route (if needed):

```python
@host_bp.route('/add_existing_challenge/<int:competition_id>', methods=['GET', 'POST'])
@login_required
@host_required
def add_existing_challenge(competition_id):
    """Add an existing challenge to a competition"""
    competition = Competition.query.get_or_404(competition_id)

    # Get available challenges (created by this user, not PUBLIC competitors' challenges)
    available_challenges = Challenge.query.filter(
        Challenge.creator_id == current_user.id,
        ~Challenge.challenges.any(
            CompetitionChallenge.competition_id == competition_id
        )
    ).all()

    # Create association
    if request.method == 'POST':
        challenge_id = request.form.get('challenge_id')
        challenge = Challenge.query.get_or_404(challenge_id)

        competition_challenge = CompetitionChallenge(
            competition_id=competition_id,
            challenge_id=challenge_id,
            is_active=True
        )
        db.session.add(competition_challenge)
        db.session.commit()
        flash('Challenge added to competition', 'success')
        return redirect(url_for('host.manage_competition', competition_id=competition_id))

    return render_template('host/add_challenge.html',
                          competition=competition,
                          available_challenges=available_challenges)
```

---

## 3. Show/Hide Specific Challenges

### Hide a Challenge from a Competition

A challenge can be hidden without deleting by using the `is_active` field in `CompetitionChallenge`:

**In Template (Jinja2):**

```html
{% for comp_challenge in competition_challenges %} {% if
comp_challenge.is_active %}
<!-- Challenge is visible -->
{% endif %} {% endfor %}
```

**Deactivate a Challenge (Hidden but Not Deleted):**

```python
@host_bp.route('/challenge/deactivate/<int:challenge_id>', methods=['POST'])
def deactivate_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    # Find the CompetitionChallenge link
    comp_challenge = CompetitionChallenge.query.filter_by(
        challenge_id=challenge_id
    ).first()

    if comp_challenge:
        comp_challenge.is_active = False
        db.session.commit()
        flash('Challenge hidden from competition', 'success')

    return redirect(url_for('host.manage_competition',
                          competition_id=comp_challenge.competition_id))
```

**Reactivate a Challenge:**

```python
comp_challenge.is_active = True
db.session.commit()
```

### Make Challenge Public/Private

**Change Visibility Scope:**

```python
challenge.visibility_scope = ChallengeVisibilityScope.PUBLIC  # Visible to all
challenge.visibility_scope = ChallengeVisibilityScope.COMPETITION  # Only in competition
challenge.visibility_scope = ChallengeVisibilityScope.PRIVATE  # Only to creator & admins
db.session.commit()
```

---

## 4. Deleting Competitions

### Admin Panel (Recommended)

1. Go to Admin Dashboard → Competitions
2. Find the competition
3. Click "Delete"
4. Choose what to do with associated challenges:
   - **Delete**: Remove challenges permanently
   - **Make Public**: Convert challenges to public library challenges

### Code Reference

```python
@admin_bp.route('/competitions/delete/<int:competition_id>', methods=['POST'])
def delete_competition(competition_id):
    """
    Delete a competition and handle its challenges

    Form Parameters:
    - challenge_action: 'delete' or 'make_public'
    """
    competition = Competition.query.get_or_404(competition_id)
    action = request.form.get('challenge_action')

    # All challenges linked via CompetitionChallenge are handled
    # Additional hosts (via CompetitionHost) are cleaned up
    # Then competition is deleted
```

### What Gets Deleted

When you delete a competition:

1. ✓ All `CompetitionChallenge` associations
2. ✓ All `UserCompetition` associations (participants)
3. ✓ All submissions made during the competition
4. ✓ All `CompetitionHost` additional host assignments
5. ✓ The competition record itself

**Optionally:**

- Challenges themselves (if action = 'delete')
- OR Convert challenges to public (if action = 'make_public')

---

## 5. Understanding Competition Status

### Status Calculation

Competitions have a hybrid `status` property that's calculated:

```python
@hybrid_property
def status(self):
    # 1. If manually overridden, use that
    if self.manual_status_override is not None:
        return self.manual_status_override

    # 2. Otherwise, calculate based on times
    now = datetime.utcnow()
    if self.start_time > now:
        return CompetitionStatus.UPCOMING
    elif self.end_time < now:
        return CompetitionStatus.ENDED
    else:
        return CompetitionStatus.ACTIVE
```

### Status Values

- **UPCOMING**: Competition hasn't started yet (`start_time > now`)
- **ACTIVE**: Competition is currently running (`start_time <= now <= end_time`)
- **ENDED**: Competition has finished (`end_time < now`)

### Manual Status Override

Hosts can manually override the calculated status:

1. Go to Manage Competition
2. Look for "Manual Status Override" section
3. Select desired status: UPCOMING, ACTIVE, ENDED
4. Click "Update Status"

The form is located at:

```html
<form method="POST">
  {{ status_form.hidden_tag() }} {{ status_form.status(class="form-select") }}
  {{ status_form.submit() }}
</form>
```

The selected status overrides the time-based calculation until changed.

---

## 6. Competition Data Structure

### Related Models

```
Competition (main table)
├── host_id → User (primary host)
├── challenges → [CompetitionChallenge] (linked challenges)
├── participants → [UserCompetition] (participants)
└── manual_status_override → CompetitionStatus (optional)

CompetitionChallenge (junction table)
├── competition_id → Competition
├── challenge_id → Challenge
└── is_active → Boolean (show/hide)

CompetitionHost (co-hosts table)
├── competition_id → Competition
└── host_id → User (additional hosts)

UserCompetition (participants table)
├── user_id → User
└── competition_id → Competition
```

### Key Fields

```python
Competition:
  - id: Primary key
  - title: Competition name
  - description: Full description
  - start_time: When competition begins
  - end_time: When competition ends
  - max_participants: Optional maximum participants
  - show_leaderboard: If True, leaderboard is visible
  - is_public: If True, competition is listed publicly
  - manual_status_override: Force a specific status (optional)
  - hosting_type: IN_PLATFORM or THIRD_PARTY
  - created_at, updated_at: Timestamps
```

---

## 7. Common Issues & Solutions

### Issue: "Host User Gets Database Unavailable Error"

**Cause**: Corrupted transaction or schema issues
**Solution**:

- Run migrations: `flask db upgrade`
- Check database connection: `flask db current`
- Verify `CompetitionHost` table exists

### Issue: "Can't Delete Competition"

**Cause**: Foreign key constraint or NOT NULL constraint
**Solution**:

- Ensure all linked `CompetitionHost` entries are deleted first
- Ensure no missing `host_id`
- Use the admin panel which handles cleanup automatically

### Issue: "Challenge Status Shows Incorrectly"

**Cause**: Using `.status` in database filters
**Solution**:

- Use `manual_status_override` for database queries
- Use the hybrid property `.status` only for Python code
- Don't filter by `.status` directly in SQLAlchemy queries

### Issue: "Can't Add Challenge Created by Another User"

**By Design**: Challenges are isolated by creator
**Solution**:

- Create new challenges directly in the competition
- OR set visibility to PUBLIC first, then link (via code)
- OR admin can directly link in database

---

## Quick Reference Commands

```bash
# Create a new challenge programmatically
python flask shell
>>> from app.models import Challenge, Competition, CompetitionChallenge
>>> # Create challenge
>>> c = Challenge(title="My Challenge", description="...", flag="flag{...}")
>>> db.session.add(c)
>>> db.session.commit()
>>> # Link to competition
>>> link = CompetitionChallenge(competition_id=1, challenge_id=c.id)
>>> db.session.add(link)
>>> db.session.commit()

# View competition challenges
>>> comp = Competition.query.get(1)
>>> for cc in comp.challenges:
>>>     print(f"{cc.challenge.title} (active: {cc.is_active})")

# Deactivate challenge
>>> cc = CompetitionChallenge.query.filter_by(competition_id=1, challenge_id=5).first()
>>> cc.is_active = False
>>> db.session.commit()
```
