from app import app, db
import core.models as models

with app.app_context():
    db.create_all()
    print("Database updated")

