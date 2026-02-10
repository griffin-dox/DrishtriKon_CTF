# Quick Reference: Database Resilience Implementation

## For Adding Database Error Handling to Routes

### Option 1: Decorator (Easiest)

```python
from flask import Blueprint, render_template
from core.db_health import require_db

my_bp = Blueprint('myroute', __name__)

@my_bp.route('/endpoint')
@require_db
def my_endpoint():
    # Any database error is automatically caught and handled
    data = MyModel.query.all()
    return render_template('template.html', data=data)
```

**When to use:** Simple routes with 1-2 database queries.

### Option 2: Manual Try-Catch (More Control)

```python
from flask import Blueprint, render_template
from core.db_health import render_db_error
import logging

my_bp = Blueprint('myroute', __name__)
logger = logging.getLogger(__name__)

@my_bp.route('/endpoint')
def my_endpoint():
    try:
        data = MyModel.query.all()
        return render_template('template.html', data=data)
    except Exception as e:
        logger.error(f"Failed to fetch data: {str(e)}")
        return render_db_error("Could not fetch data. Please try again.")
```

**When to use:** Routes with multiple queries or custom error handling.

### Option 3: Safe Query Helper

```python
from flask import Blueprint, render_template
from core.db_health import get_safe_db_result
from app import db

my_bp = Blueprint('myroute', __name__)

@my_bp.route('/endpoint')
def my_endpoint():
    # Returns None if query fails
    data = get_safe_db_result(
        lambda: MyModel.query.all(),
        default_value=[],
        timeout=5
    )

    return render_template('template.html', data=data if data else [])
```

**When to use:** Read-only queries where default values are acceptable.

---

## For Query Functions (Used by Routes)

### Pattern 1: Cache Decorator with Error Handling

```python
from core.production_cache import cache_db_query
from app import db
import logging

logger = logging.getLogger(__name__)

@cache_db_query(timeout=300)
def get_active_competitions():
    """Get active competitions with fallback"""
    try:
        return Competition.query.filter_by(is_active=True).all()
    except Exception as e:
        logger.warning(f"Failed to fetch competitions: {str(e)}")
        return []  # Return empty list on error
```

### Pattern 2: Statistics with Defaults

```python
@cache_db_query(timeout=600)
def get_platform_stats():
    """Get stats with safe defaults"""
    try:
        total_users = db.session.query(func.count(User.id)).scalar() or 0
        total_challenges = db.session.query(func.count(Challenge.id)).scalar() or 0

        return {
            'total_users': total_users,
            'total_challenges': total_challenges,
        }
    except Exception as e:
        logger.warning(f"Failed to fetch stats: {str(e)}")
        return {
            'total_users': 0,
            'total_challenges': 0,
        }
```

### Pattern 3: Optional Data

```python
def get_user_profile(user_id):
    """Safely fetch user with None fallback"""
    try:
        return User.query.get(user_id)
    except Exception as e:
        logger.warning(f"Failed to fetch user {user_id}: {str(e)}")
        return None  # Template handles None gracefully
```

---

## Common Patterns by Route Type

### Authentication Routes

```python
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('auth.login'))
        # ... rest of login logic
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return render_db_error("Could not verify credentials. Please try again.")
```

### List/Browse Routes

```python
@challenges_bp.route('/')
@require_db
def list_challenges():
    # Get with safe defaults
    challenges = get_challenges_safe()  # Returns [] on error
    page = request.args.get('page', 1, type=int)

    return render_template('challenges.html',
                          challenges=challenges or [])
```

### Detail/Read Routes

```python
@challenges_bp.route('/<int:challenge_id>')
@require_db
def view_challenge(challenge_id):
    challenge = Challenge.query.get_or_404(challenge_id)

    return render_template('challenge_detail.html',
                          challenge=challenge)
    # 404 if not found, 503 if DB error
```

### Create/Write Routes

```python
@admin_bp.route('/create', methods=['POST'])
@require_db
@login_required
def create_challenge():
    try:
        challenge = Challenge(
            title=request.form.get('title'),
            # ... other fields
        )
        db.session.add(challenge)
        db.session.commit()

        flash('Challenge created', 'success')
        return redirect(url_for('admin.challenges'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create challenge: {str(e)}")
        return render_db_error("Could not create challenge. Please try again.")
```

---

## Testing Your Implementation

### Quick Test

```python
# In app.py before_request or in a test script
from core.db_health import check_db_connection

if check_db_connection():
    print("✓ Database is active")
else:
    print("✗ Database is inactive")
```

### Manual Browser Test

1. Set `DATABASE_URL` to invalid value in `.env`
2. Restart Flask
3. Visit problematic route
4. Should see friendly error page (not 500)
5. Restore `DATABASE_URL` and refresh

### Check Logs

```bash
# See all database-related errors
grep -i "database\|failed to fetch\|connection" logs/app.log
```

---

## Checklist for Each Route

- [ ] Does route use database?
  - NO → Do nothing (route is safe)
  - YES → Continue

- [ ] Is it a simple single-query route?
  - YES → Use `@require_db` decorator
  - NO → Use manual try-catch

- [ ] Does route return data to user?
  - YES → Provide safe defaults (empty lists, None, etc.)
  - NO → Just log error and redirect

- [ ] Does query use cached decorator?
  - YES → Add try-catch inside query function
  - NO → Add try-catch at route level

- [ ] Tested with broken database?
  - YES → ✓ Ready to deploy
  - NO → Do it now before committing

---

## Import Statements Needed

```python
# Core imports
from core.db_health import (
    require_db,           # Decorator for routes
    render_db_error,      # Render friendly error page
    check_db_connection,  # Check if DB is alive
    get_safe_db_result    # Helper for safe queries
)

# Logging
import logging
logger = logging.getLogger(__name__)

# For try-catch in routes
from app import db
```

---

## Error Messages to Use

### Generic Database Down

```python
return render_db_error()  # Uses default message
```

### Custom Message (Feature-Specific)

```python
return render_db_error("Could not load challenges. The database is temporarily unavailable.")
```

### For API Endpoints

```python
return jsonify({
    'status': 'error',
    'message': 'Database temporarily unavailable',
    'details': 'Please try again in a few moments.'
}), 503
```

---

## Common Mistakes to Avoid

### ✗ No Error Handling

```python
# BAD - Will show 500 error
@my_bp.route('/')
def index():
    return db.session.query(Model).all()  # Crashes if DB down
```

### ✗ Silent Failures

```python
# BAD - User never knows what happened
@my_bp.route('/')
def index():
    try:
        return db.session.query(Model).all()
    except:
        pass  # Silent, user confused
```

### ✗ Incomplete Data

```python
# BAD - Template can't handle None
@my_bp.route('/')
def index():
    try:
        data = db.session.query(Model).all()
    except:
        data = None  # Template expects list
    return render_template('index.html', data=data)
```

### ✗ No Logging

```python
# BAD - Admin can't debug issues
try:
    # query
except Exception as e:
    return render_db_error()  # Where did the error come from?
```

### ✓ Best Practice

```python
# GOOD - Handles error, logs it, shows friendly message
try:
    data = db.session.query(Model).all() or []
except Exception as e:
    logger.error(f"Failed to fetch models: {str(e)}")
    return render_db_error("Could not load data")
```

---

## Performance Tips

1. **Cache queries** - Use `@cache_db_query(timeout=300)` for frequently accessed data
2. **Lazy load** - Use `lazy='select'` on relationships for better performance
3. **Batch errors** - Don't log every error, summarize
4. **Monitor logs** - Watch for patterns of database errors

---

## Useful Commands

```bash
# View database connection errors
grep -i "database\|connection\|operational" logs/app.log

# Count database errors
grep -c "database error" logs/app.log

# Real-time monitoring
tail -f logs/app.log | grep -i "database"

# Check if database is responsive (in Flask shell)
from app import db
from sqlalchemy import text
db.session.execute(text('SELECT 1'))
```

---

## When to Use Each Approach

| Situation           | Use This                      | Reason                    |
| ------------------- | ----------------------------- | ------------------------- |
| Simple single query | `@require_db`                 | Automatic handling        |
| Multiple queries    | Manual try-catch              | Better control            |
| Read-only query     | `get_safe_db_result()`        | Simple with defaults      |
| Write operation     | Manual try-catch              | Need rollback control     |
| Cached query        | Try-catch inside function     | Prevents cache corruption |
| API endpoint        | Manual try-catch + JSON       | Different response format |
| Template rendering  | Try-catch + render_db_error() | Consistent UX             |

---

## Implementation Timeline

**Phase 1 (Done):**

- ✓ Created `core/db_health.py`
- ✓ Created error template
- ✓ Updated app.py error handlers
- ✓ Updated routes/main.py

**Phase 2 (Next):**

- [ ] Add `@require_db` to all auth routes
- [ ] Add try-catch to all admin routes
- [ ] Test with broken database
- [ ] Update documentation in README

**Phase 3 (Optional):**

- [ ] Add database health check widget
- [ ] Implement async query loading
- [ ] Add connection pooling optimization
