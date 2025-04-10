from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    rep_goal = db.Column(db.Integer, nullable=False, default=8)
    ex_goal = db.Column(db.Integer, nullable=False, default=5)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


class Exercises(db.Model):
    __tablename__ = 'exercises'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    link = db.Column(db.String(200), nullable=False)
    muscles_involved = db.Column(db.String(200), nullable=False)
    alternate = db.Column(db.String(80), nullable=True)


class UserExercise(db.Model):
    __tablename__ = 'user_exercise'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercises.id'), nullable=False)
    rom_score = db.Column(db.Integer, nullable=False)
    total_reps = db.Column(db.Integer, nullable=False)
    tut_score = db.Column(db.Float, nullable=False)
    count = db.Column(db.Integer, nullable=True, default=0)
    date = db.Column(db.DateTime, default=datetime.now())


class ExerciseUpload(db.Model):
    __tablename__ = 'exercise_uploads'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    exercise_type = db.Column(db.String(50), nullable=False)
    video_path = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    # Relationship with User model
    user = db.relationship('User', backref=db.backref('exercise_uploads', lazy=True))


class ScheduledWorkout(db.Model):
    __tablename__ = 'scheduled_workouts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    exercise_type = db.Column(db.String(50), nullable=False)
    workout_date = db.Column(db.Date, nullable=False)
    workout_time = db.Column(db.Time, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    
    # Relationship with User model
    user = db.relationship('User', backref=db.backref('scheduled_workouts', lazy=True))

