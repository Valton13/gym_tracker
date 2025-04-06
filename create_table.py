from app import app, db
from models import ExerciseUpload

def create_exercise_uploads_table():
    with app.app_context():
        db.create_all()
        print("Table created successfully!")

if __name__ == "__main__":
    create_exercise_uploads_table() 