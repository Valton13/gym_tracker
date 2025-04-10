from flask import Flask, flash, render_template, redirect, request, url_for, jsonify, session, Response, send_file
from forms import LoginForm, SearchForm, RegistrationForm
from flask_migrate import Migrate
from config import Config
from models import User, db, bcrypt, Exercises, UserExercise, ExerciseUpload, ScheduledWorkout
from shoulder_press import gen_frames as gen_frames_shoulder_press
from bicep_curls import gen_frames as gen_frames_bicep_curls
from barbell_squats import gen_frames as gen_frames_barbell_squats
from deadlift import gen_frames as gen_frames_deadlift
from lateral_raises import gen_frames as gen_frames_lateral_raises
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps
import os
from werkzeug.utils import secure_filename
import cv2
import numpy as np

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)
quartz = dbc.themes.SKETCHY

# Configure upload folder
UPLOAD_FOLDER = 'uploads/exercises'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Decorator to ensure user is logged in before accessing certain routes
def login_required(f):
    @wraps(f)
    def chck(*args, **kwargs):
        if 'user_id' not in session:
            flash("You need to log in first.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return chck

# Dash application for interactive data visualisation
dash_app = Dash(__name__, server=app, external_stylesheets=[quartz], url_base_pathname='/dashboard/')

# Set up layout for the Dash application,
dash_app.layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.A("Go Back", href="/mainboard", className="btn btn-lg text-center text-white", style={
                "background-color": "#98ff98",  # Green mint
                "border-radius": "10px",
                "padding": "10px 20px",
                "display": "block",
                "margin": "0 auto",
                "text-decoration": "none",
                "font-size": "24px",
                "width": "200px",
                "box-shadow": "2px 2px 5px rgba(0, 0, 0, 0.3)"
            }),
            width=12
        )
    ),
    dcc.Tabs(id="tabs-example", value='tab-1', children=[
        dcc.Tab(label='Last Workout', value='tab-1'),
        dcc.Tab(label='Progress', value='tab-2'),
    ]),
    html.Div(id='tabs-content')
])

# Callback to dynamically update content based on selected tabs
@dash_app.callback(
    Output('tabs-content', 'children'),
    Input('tabs-example', 'value')
)
def render_content(tab):
    if tab == 'tab-1':
        return dbc.Container([
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id='exercise-dropdown',
                        options=[
                            {'label': 'Shoulder Press', 'value': 1},#edit
                            {'label': 'Bicep Curl', 'value': 2},
                            {'label': 'Barbell Squats', 'value': 3},
                            {'label': 'Deadlift', 'value': 4},
                            {'label': 'Lateral Raises', 'value': 5}

                        ],
                        value=1,
                        className='mx-auto',
                        style={'width': '50%'}
                    ),
                    width=6
                )
            ], justify="center"),
            html.Div(id='exercise-output', className="mt-4")
        ])
    elif tab == 'tab-2':
        return dbc.Container([
            dbc.Row(
                dbc.Col(html.H3("Overall Progress", className="text-center my-4"), width=12)
            ),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='overall-progress-graph'),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id='specific-exercise-dropdown',
                        options=[
                            {'label': 'Shoulder Press', 'value': 1},
                            {'label': 'Bicep Curl', 'value': 2},
                            {'label': 'Barbell Squats', 'value': 3},
                            {'label': 'Deadlift', 'value': 4},
                            {'label': 'Lateral Raises', 'value': 5}
                        ],
                        value=1,
                        className='mx-auto',
                        style={'width': '50%'}
                    ),
                    width=6
                )
            ], justify="center", className="mt-4"),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='specific-exercise-progress-graph'),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='muscles-hit-graph'),  # Later
                    width=12
                )
            ])
        ])


# Callback for the Last Workout Tab
@dash_app.callback(
    Output('exercise-output', 'children'),
    Input('exercise-dropdown', 'value')
)
def update_last_workout(exercise_id):
    last_workout = UserExercise.query.filter_by(user_id=session['user_id'], exercise_id=exercise_id).order_by(
        UserExercise.date.desc()).first()

    if last_workout:
        workout_data = {
            'Date': last_workout.date.strftime("%Y-%m-%d %H:%M:%S"),
            'ROM Score': last_workout.rom_score,
            'TUT Score': round(last_workout.tut_score / last_workout.total_reps, 1),
            'Total Reps': last_workout.total_reps,
            'rom_score': last_workout.rom_score,
            'Count': last_workout.count
        }

        pie_chart = go.Figure(data=[go.Pie(labels=['Efficient Reps', 'Missed Reps'],
                                           values=[workout_data['Total Reps'],
                                                   workout_data['Total Reps'] - workout_data['rom_score']])])
        pie_chart.update_layout(
            title={
                'text': 'Efficiency in Last Workout',
                'font': {
                    'color': 'black'
                }
            },
            legend={
                'font': {
                    'color': 'black'
                }
            },
            paper_bgcolor='rgba(0,0,0,0)'
        )

        return html.Div([
            html.H4(f"Last Workout: {workout_data['Date']}"),
            html.P(f"ROM Score: {workout_data['ROM Score']}"),
            html.P(f"TUT: {workout_data['TUT Score']} sec per rep"),
            html.P(f"Total Reps: {workout_data['Total Reps']}"),
            dcc.Graph(figure=pie_chart)
        ])
    else:
        return html.P("No workout data available.")


# Callback to the Progress Tab
@dash_app.callback(
    [Output('overall-progress-graph', 'figure'),
     Output('specific-exercise-progress-graph', 'figure'),
     Output('muscles-hit-graph', 'figure')],
    [Input('tabs-example', 'value'),
     Input('specific-exercise-dropdown', 'value')]
)
def update_progress(tab, exercise_id):
    if tab != 'tab-2':
        raise PreventUpdate

    # Overall Progress DataFrame
    overall_data = UserExercise.query.filter_by(user_id=session['user_id']).all()
    overall_df = pd.DataFrame([{
        'date': record.date,
        'rom_score': record.rom_score,
        'tut_score': record.tut_score,
        'rep_number': record.total_reps,
        'count': record.count,
    } for record in overall_data])

    if overall_df.empty:
        return go.Figure(), go.Figure(), go.Figure()

    overall_df['week'] = overall_df['date'].dt.strftime('%Y-%U')
    overall_df['efficiency'] = (overall_df['count'] / overall_df['rep_number']) * 100
    weekly_efficiency_df = overall_df.groupby('week').agg({'efficiency': 'mean'}).reset_index()
    weekly_efficiency_df['wow_improvement'] = weekly_efficiency_df['efficiency'].pct_change() * 100
    wow = f'{weekly_efficiency_df["wow_improvement"].iloc[-1]:.2f}% better than prev. week ⬆️'

    overall_df = overall_df.groupby('date').agg({
        'rom_score': 'mean',
        'tut_score': 'mean',
        'rep_number': 'sum',
        'count': 'sum'
    }).reset_index()

    overall_line_chart = go.Figure()
    overall_line_chart.add_trace(go.Scatter(x=overall_df['date'], y=overall_df['count'],
                                            mode='lines+markers', name='Efficient Reps'))
    overall_line_chart.add_trace(go.Scatter(x=overall_df['date'], y=overall_df['rep_number'],
                                            mode='lines+markers', name='Total Reps'))
    overall_line_chart.add_annotation(
        text=f"WoW Improvement: {wow}",
        xref="paper", yref="paper",
        x=0.5, y=1.1,
        showarrow=False,
        font=dict(
            size=14,
            color="black"
        ),
        align="center",
        bgcolor="white",
        opacity=0.8
    )
    overall_line_chart.update_layout(title='Overall Week-Over-Week Progress',
                                     xaxis_title='Date', yaxis_title='Efficiency')


    specific_data = UserExercise.query.filter_by(exercise_id=exercise_id, user_id=session['user_id']).all()
    specific_df = pd.DataFrame([{
        'date': record.date,
        'rom_score': record.rom_score,
        'tut_score': record.tut_score,
        'rep_number': record.total_reps,
        'count': record.count,
    } for record in specific_data])

    specific_line_chart = go.Figure()
    if not specific_df.empty:
        specific_df = specific_df.groupby('date').agg({
            'rom_score': 'mean',
            'tut_score': 'mean',
            'rep_number': 'sum',
            'count': 'sum'
        }).reset_index()

        specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['count'],
                                                 mode='lines+markers', name='Efficient Reps'))
        specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['rep_number'],
                                                 mode='lines+markers', name='Total Reps'))
        specific_line_chart.update_layout(title='Specific Exercise Progress',
                                          xaxis_title='Date', yaxis_title='Efficiency')


    muscle_data = db.session.query(Exercises.muscles_involved, db.func.sum(UserExercise.total_reps)).join(
        UserExercise, Exercises.id == UserExercise.exercise_id).filter(UserExercise.user_id == session['user_id']).group_by(
        Exercises.muscles_involved).all()

    muscle_df = pd.DataFrame(muscle_data, columns=['Muscles Involved', 'Total Reps'])
    muscle_dict = {}

    for muscles, reps in zip(muscle_df['Muscles Involved'], muscle_df['Total Reps']):

        muscle_list = muscles.split(',')

        for muscle in muscle_list:
            muscle = muscle.strip()
            if muscle in muscle_dict:
                muscle_dict[muscle] += reps
            else:
                muscle_dict[muscle] = reps

    muscle_ind_df = pd.DataFrame(list(muscle_dict.items()), columns=['muscle', 'Total Reps'] )
    muscle_ind_df = muscle_ind_df.sort_values(by='Total Reps', ascending=False)
    muscle_bar_chart = go.Figure(data=[
        go.Bar(x=muscle_ind_df['muscle'], y=muscle_ind_df['Total Reps'])
    ])
    muscle_bar_chart.update_layout(title='Muscles Worked', xaxis_title='Muscle Groups', yaxis_title='Total Reps')

    return overall_line_chart, specific_line_chart, muscle_bar_chart


# Flask route to render the Dash dashboard
@app.route("/dash/")
@login_required
def render_dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard', 'error')
        return redirect(url_for('login'))
    return dash_app.index()

# Function to generate frames for real-time video feedback
def gen_frames(exercise, user_id, rep_goal):
    if exercise == 'shoulder_press':
        print('s_press')
        return gen_frames_shoulder_press(user_id, rep_goal)
    elif exercise == 'dumbbell_curls':
        print('b_curls')
        return gen_frames_bicep_curls(user_id, rep_goal)
    elif exercise == 'barbell_squats':
        print('b_squats')
        return gen_frames_barbell_squats(user_id, rep_goal)
    elif exercise == 'deadlift':
        print('dlift')
        return gen_frames_deadlift(user_id, rep_goal)
    elif exercise == 'lateral_raises':
        print('l_raises')
        return gen_frames_lateral_raises(user_id, rep_goal)
    else:
        return None


# Flask routes for user authentication
@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    registration_form = RegistrationForm()

    if request.method == 'POST':
        if 'login_submit' in request.form:
            if login_form.validate_on_submit():
                user = User.query.filter_by(username=login_form.username.data).first()
                if user and user.check_password(login_form.password.data):
                    flash('Login successful!', 'success')
                    session['user_id'] = user.id
                    return redirect(url_for('mainboard'))
                else:
                    flash('Invalid username or password.', 'danger')
            else:
                for field, errors in login_form.errors.items():
                    for error in errors:
                        flash(f'{field.title()}: {error}', 'danger')

        elif 'register_submit' in request.form:
            if registration_form.validate_on_submit():
                # Create new user
                new_user = User(
                    username=registration_form.username.data,
                    email=registration_form.email.data
                )
                new_user.set_password(registration_form.password.data)
                db.session.add(new_user)
                db.session.commit()
                
                flash('Registration successful! You can now log in.', 'success')
                return render_template('enter.html', login_form=login_form, registration_form=registration_form)
            else:
                for field, errors in registration_form.errors.items():
                    for error in errors:
                        flash(f'{field.title()}: {error}', 'danger')

    return render_template('enter.html', login_form=login_form, registration_form=registration_form)


from datetime import datetime, timedelta

# Flask route for homepage
@app.route('/mainboard', methods=['GET', 'POST'])
@login_required
def mainboard():
    first_session = session.get('first_session')
    if not first_session:
        print('not first time')
        print(session['user_id'])
    else:
        print(first_session)
        session['first_session'] = False

    search_form = SearchForm()
    user_id = session.get('user_id')
    if not user_id:
        print('error no id')

    all_exercises = UserExercise.query.filter_by(user_id=user_id).all()

    total_rom_score = sum(exercise.rom_score for exercise in all_exercises)
    total_reps = sum(exercise.total_reps for exercise in all_exercises)

    if total_reps > 0:
        efficiency = round(((total_rom_score / total_reps) * 100), 2)
    else:
        efficiency = 0

    total_exercises = UserExercise.query.filter_by(user_id=user_id).count()
    total_reps = db.session.query(db.func.sum(UserExercise.total_reps)).filter_by(user_id=user_id).scalar()

    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())

    exercises_this_week = UserExercise.query.filter(
        UserExercise.user_id == user_id,
        UserExercise.date >= start_of_week
    ).count()

    exercise_goal = User.query.filter_by(id=user_id).one()
    print(exercise_goal.ex_goal)
    ex_goal = exercise_goal.ex_goal - exercises_this_week

    thirty_days_ago = today - timedelta(days=30)
    distinct_dates = db.session.query(UserExercise.date).filter(
        UserExercise.user_id == user_id,
        UserExercise.date >= thirty_days_ago
    ).distinct().all()
    workout_days = len(set(date[0].date() for date in distinct_dates))

    exercise_dates = db.session.query(UserExercise.date).filter_by(user_id=user_id).distinct().order_by(
        UserExercise.date).all()

    exercise_dates = [date[0].date() for date in exercise_dates]

    streak = 0
    for i in range(1, len(exercise_dates)):
        if exercise_dates[i] == exercise_dates[i - 1] + timedelta(days=1):
            streak += 1
        else:
            break

    import random


    most_performed_exercise = db.session.query(
        UserExercise.exercise_id, db.func.sum(UserExercise.total_reps).label('total_reps')
    ).filter_by(user_id=user_id).group_by(
        UserExercise.exercise_id
    ).order_by(
        db.func.sum(UserExercise.total_reps).desc()
    ).all()

    if most_performed_exercise:
        top_total_reps = most_performed_exercise[0][1]
        top_exercises = [exercise for exercise in most_performed_exercise if exercise[1] == top_total_reps]
        selected_exercise_id = random.choice(top_exercises)[0]

        selected_exercise = Exercises.query.get(selected_exercise_id)
        selected_exercise_name = selected_exercise.name if selected_exercise else "your most performed exercise"
        alternate_exercise = selected_exercise.alternate if selected_exercise else None

        if alternate_exercise:
            alternate_message = f"{alternate_exercise}"
        else:
            alternate_message = "No alternate exercise available."

    else:
        selected_exercise_name = "your most performed exercise"
        alternate_message = "No exercises found."

    return render_template('mainboard.html', search_form=search_form,
                           first_session=first_session, efficiency=efficiency, total_exercises=total_exercises,
                           total_reps=total_reps, exercises_this_week=exercises_this_week, streak=streak,
                           workout_days=workout_days, selected_exercise_name=selected_exercise_name,
                           alternate_message=alternate_message, ex_goal=ex_goal)



# Route for profile page
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    search_form = SearchForm()
    user_id = session.get('user_id')

    user_details = User.query.filter_by(id=user_id).first()

    if user_details:
        username = user_details.username
        ex_goal = user_details.ex_goal
        rep_goal = user_details.rep_goal

    if request.method == 'POST':
        if 'change_password' in request.form:
            new_password = request.form['new_password']
            user_details.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully!', 'success')

        elif 'increase_ex_goal' in request.form:
            user_details.ex_goal += 1
            db.session.commit()

        elif 'decrease_ex_goal' in request.form:
            if user_details.ex_goal > 0:
                user_details.ex_goal -= 1
                db.session.commit()

        elif 'increase_rep_goal' in request.form:
            user_details.rep_goal += 1
            db.session.commit()

        elif 'decrease_rep_goal' in request.form:
            if user_details.rep_goal > 0:
                user_details.rep_goal -= 1
                db.session.commit()

        elif 'delete_account' in request.form:
            db.session.delete(user_details)
            db.session.commit()
            flash('Account deleted successfully!', 'success')
            return redirect(url_for('logout'))

    return render_template('profile.html', search_form=search_form,
                           username=username, ex_goal=ex_goal, rep_goal=rep_goal)

#
'''@app.route('/search_exercises', methods=['GET'])
@login_required
def search_exercises():
    query = request.args.get('query', '').strip()
    if query:
        exercises = Exercises.query.filter(Exercises.name.ilike(f'%{query}%')).all()
        results = [{'name': exercise.name, 'link': exercise.link} for exercise in exercises]
        return jsonify(results)
    return jsonify([])'''

# Route to learn exercise
@app.route('/exercises', methods=['GET', 'POST'])
@login_required
def exercises():
    exercise = request.args.get('exercise', default=None)

    video_links = {
        'shoulder_press': 'https://www.youtube.com/embed/HzIiNhHhhtA',
        'dumbbell_curls': 'https://www.youtube.com/embed/JnLFSFurrqQ',
        'barbell_squats': 'https://www.youtube.com/embed/i7J5h7BJ07g',
        'deadlift': 'https://www.youtube.com/embed/AweC3UaM14o',
        'lateral_raises': 'https://www.youtube.com/embed/OuG1smZTsQQ'
    }

    video_link = video_links.get(exercise)

    return render_template('exercises.html', 
                         video_link=video_link, 
                         exercise=exercise)

# Route for leaderboard
@app.route('/leaderboard', methods=['GET', 'POST'])
@login_required
def leaderboard():
    search_form = SearchForm()
    view = request.form.get('view', 'total_exercises')


    highest_exercises = db.session.query(
        User.id,
        User.username,
        func.count(UserExercise.id).label('exercise_count')
    ).join(User, User.id == UserExercise.user_id).group_by(User.id).order_by(func.count(UserExercise.id).desc()).all()


    highest_reps = db.session.query(
        User.id,
        User.username,
        func.sum(UserExercise.count).label('total_reps')
    ).join(User, User.id == UserExercise.user_id).group_by(User.id).order_by(func.sum(UserExercise.count).desc()).all()

    return render_template('leaderboard.html', leaderboard_data=highest_exercises if view == 'total_exercises'
    else highest_reps, view=view, search_form=search_form)


@app.route('/workout')
@login_required
def workout():
    search_form = SearchForm()
    return render_template('exercises.html', search_form=search_form)

# Routes to start exercise
# Temp page to re-direct to exercise page
@app.route('/start/<exercise>')
@login_required
def start(exercise):
    search_form = SearchForm()
    user_id = session.get('user_id')
    rep_goal = db.session.query(User.rep_goal).filter_by(id=user_id).scalar()

    return render_template('instructions.html', search_form=search_form, exercise=exercise, user_id=user_id, rep_goal=rep_goal)

# Actual Exercise Page
@app.route('/start_page/<exercise>')
@login_required
def start_page(exercise):
    search_form = SearchForm()
    user_id = session.get('user_id')
    rep_goal = db.session.query(User.rep_goal).filter_by(id=user_id).scalar()



    video_feed_url = url_for('video_feed', exercise=exercise, user_id=user_id, rep_goal=rep_goal)

    return render_template('start.html', search_form=search_form, exercise=exercise, user_id=user_id, rep_goal=rep_goal, video_feed_url=video_feed_url)

# Video feed linked to start.html
@app.route('/video_feed/<exercise>/<int:user_id>/<int:rep_goal>')
def video_feed(exercise, user_id, rep_goal):
    return Response(gen_frames(exercise, user_id, rep_goal), mimetype='multipart/x-mixed-replace; boundary=frame')

# Route to logout
@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/upload-exercise', methods=['GET', 'POST'])
@login_required
def upload_exercise():
    analyzed_video = None
    
    if request.method == 'POST':
        if 'video' not in request.files:
            flash('No video file uploaded', 'error')
            return redirect(request.url)
        
        video = request.files['video']
        exercise_type = request.form.get('exercise_type')
        notes = request.form.get('notes')
        
        if video.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if video and allowed_file(video.filename):
            try:
                # Generate unique filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{session['user_id']}_{exercise_type}_{timestamp}_{secure_filename(video.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Save video file
                video.save(filepath)
                
                # Analyze the video (placeholder for AI analysis)
                feedback = analyze_exercise_video(filepath, exercise_type)
                
                # Store the analysis in database using SQLAlchemy
                new_upload = ExerciseUpload(
                    user_id=session['user_id'],
                    exercise_type=exercise_type,
                    video_path=filename,
                    notes=notes,
                    feedback=feedback,
                    created_at=datetime.now()
                )
                db.session.add(new_upload)
                db.session.commit()
                
                analyzed_video = new_upload
                flash('Exercise video uploaded and analyzed successfully!', 'success')
                
            except Exception as e:
                print(f"Error during upload: {str(e)}")  # For debugging
                db.session.rollback()  # Rollback any failed database transaction
                flash('Error analyzing video. Please try again.', 'error')
                return redirect(request.url)
        
        flash('Invalid file type. Please upload MP4, MOV, or AVI files only.', 'error')
        return redirect(request.url)
    
    # Get all analyzed videos for the current user
    analyzed_videos = ExerciseUpload.query.filter_by(user_id=session['user_id']).order_by(ExerciseUpload.created_at.desc()).all()
    
    return render_template('upload_exercise.html', analyzed_video=analyzed_video, analyzed_videos=analyzed_videos)

def analyze_exercise_video(video_path, exercise_type):
    """
    Placeholder function for AI-based exercise analysis
    In a real implementation, this would use computer vision and machine learning
    to analyze the exercise form and provide feedback
    """
    # This is a placeholder that returns basic feedback
    # In a real implementation, you would:
    # 1. Load the video using OpenCV
    # 2. Process frames to detect body keypoints
    # 3. Analyze movement patterns
    # 4. Compare with ideal form
    # 5. Generate detailed feedback
    
    feedback = {
        'squat': 'Your squat form looks good! Keep your back straight and knees aligned with toes.',
        'deadlift': 'Maintain a neutral spine throughout the movement. Keep the bar close to your body.',
        'pushup': 'Keep your elbows close to your body and maintain a straight line from head to heels.',
        'pullup': 'Focus on engaging your back muscles. Pull your chest to the bar.',
        'shoulder_press': 'Keep your core engaged and maintain proper wrist alignment.',
        'bicep_curl': 'Control the weight throughout the movement. Keep your elbows stationary.',
        'plank': 'Maintain a straight line from head to heels. Keep your core engaged.',
        'other': 'Exercise form looks good! Keep up the good work!'
    }
    
    return feedback.get(exercise_type, feedback['other'])

# Route to download analyzed video
@app.route('/download-analyzed-video/<int:upload_id>')
@login_required
def download_analyzed_video(upload_id):
    upload = ExerciseUpload.query.get_or_404(upload_id)
    
    # Ensure the user can only download their own videos
    if upload.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('exercises'))
    
    try:
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], upload.video_path)
        if not os.path.exists(video_path):
            flash('Video file not found', 'error')
            return redirect(url_for('exercises'))
            
        return send_file(
            video_path,
            as_attachment=True,
            download_name=f"analyzed_{upload.exercise_type}_{upload.created_at.strftime('%Y%m%d_%H%M%S')}.mp4"
        )
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        flash('Error downloading video', 'error')
        return redirect(url_for('exercises'))

@app.route('/delete-analyzed-video/<int:upload_id>', methods=['POST'])
@login_required
def delete_analyzed_video(upload_id):
    upload = ExerciseUpload.query.get_or_404(upload_id)
    
    # Ensure the user can only delete their own videos
    if upload.user_id != session['user_id']:
        flash('Unauthorized access', 'error')
        return redirect(url_for('upload_exercise'))
    
    try:
        # Delete the video file
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], upload.video_path)
        if os.path.exists(video_path):
            os.remove(video_path)
        
        # Delete the database record
        db.session.delete(upload)
        db.session.commit()
        
        flash('Video deleted successfully!', 'success')
    except Exception as e:
        print(f"Error deleting video: {str(e)}")
        db.session.rollback()
        flash('Error deleting video', 'error')
    
    return redirect(url_for('upload_exercise'))

@app.route('/schedule')
@login_required
def schedule():
    return render_template('schedule.html')

@app.route('/add-workout', methods=['POST'])
@login_required
def add_workout():
    data = request.json
    workout_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    workout_time = datetime.strptime(data['time'], '%H:%M').time()
    
    new_workout = ScheduledWorkout(
        user_id=session['user_id'],
        exercise_type=data['exercise'],
        workout_date=workout_date,
        workout_time=workout_time,
        notes=data.get('notes', '')
    )
    
    db.session.add(new_workout)
    db.session.commit()
    
    return jsonify({
        'id': new_workout.id,
        'date': workout_date.strftime('%Y-%m-%d'),
        'time': workout_time.strftime('%H:%M'),
        'exercise': new_workout.exercise_type,
        'notes': new_workout.notes
    })

@app.route('/delete-workout/<int:workout_id>', methods=['POST'])
@login_required
def delete_workout(workout_id):
    workout = ScheduledWorkout.query.get_or_404(workout_id)
    
    # Ensure the workout belongs to the current user
    if workout.user_id != session['user_id']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(workout)
    db.session.commit()
    
    return jsonify({'success': True})

if __name__ == "__main__":
    app.run()
