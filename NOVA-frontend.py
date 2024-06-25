from flask import Flask, request, render_template, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import datetime
import sys
from werkzeug.security import generate_password_hash, check_password_hash
import pyttsx3

# Ensure the instance directory exists
os.makedirs('instance', exist_ok=True)

# Initialize the Flask application
app = Flask(__name__)
csrf = CSRFProtect(app)
talisman = Talisman(app)

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['WTF_CSRF_SECRET_KEY'] = 'a csrf secret key'
app.config['MAIL_SERVER'] = '127.0.0.1'
app.config['MAIL_PORT'] = 25
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_DEFAULT_SENDER'] = 'noreply@vibrationrobotics.com'
app.config['SECURITY_PASSWORD_SALT'] = 'my_precious_two'

db = SQLAlchemy(app)
mail = Mail(app)
limiter = Limiter(get_remote_address, app=app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Setup logging
log_file = 'logs/voiceme-server.log'
handler = RotatingFileHandler(log_file, maxBytes=1000000, backupCount=5)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(level=logging.DEBUG, handlers=[handler, console_handler], format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
try:
    with open('config.json') as config_file:
        config = json.load(config_file)
    logging.debug("Loaded configuration")
except Exception as e:
    logging.error(f"Error loading configuration: {e}")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    confirmed = db.Column(db.Boolean, default=False)
    confirmed_on = db.Column(db.DateTime, nullable=True)
    role = db.Column(db.String(80), default='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except:
            return None
        return User.query.get(user_id)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # Updated to use Session.get()

# Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered. Please choose a different one.')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('There is no account with that email. You must register first.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

# Email functions
def send_verification_email(user_email):
    token = generate_confirmation_token(user_email)
    confirm_url = url_for('confirm_email', token=token, _external=True)
    html = render_template('activate.html', confirm_url=confirm_url)
    subject = "Please confirm your email"
    send_email(user_email, subject, html)

def generate_confirmation_token(email):
    serializer = Serializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    serializer = Serializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return False
    return email

def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=app.config['MAIL_DEFAULT_SENDER']
    )
    mail.send(msg)

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)

# Routes
@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        send_verification_email(user.email)
        flash('Registration successful. Please check your email to confirm your account.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        logging.debug(f"Attempting login with username: {username}")

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            logging.debug("Password matches.")
            login_user(user)
            return redirect(url_for('index'))
        else:
            logging.debug("Invalid credentials.")
            flash('Invalid credentials')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', config=config)

@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = confirm_token(token)
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))
    user = User.query.filter_by(email=email).first_or_404()
    if user.confirmed:
        flash('Account already confirmed. Please login.', 'success')
    else:
        user.confirmed = True
        user.confirmed_on = datetime.datetime.now()
        db.session.add(user)
        db.session.commit()
        flash('You have confirmed your account. Thanks!', 'success')
    return redirect(url_for('login'))

@app.route('/reset', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_request():
    form = RequestResetForm()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        flash('If an account with that email exists, a reset email has been sent.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', form=form)

@app.route('/reset/<token>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def reset_token(token):
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        password = form.password.data
        user.set_password(password)
        db.session.commit()
        flash('Your password has been updated!', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', form=form)

@app.route('/update', methods=['POST'])
@login_required
def update():
    key = request.form['key']
    value = request.form['value']
    config[key] = value
    save_config()
    return redirect(url_for('index'))

@app.route('/update_program', methods=['POST'])
@login_required
def update_program():
    program = request.form['program']
    path = request.form['path']
    config["program_mapping"][program] = path
    save_config()
    return redirect(url_for('index'))

@app.route('/delete_program/<program>', methods=['POST'])
@login_required
def delete_program(program):
    if program in config["program_mapping"]:
        del config["program_mapping"][program]
        save_config()
    return redirect(url_for('index'))

@app.route('/edit_program/<program>', methods=['GET', 'POST'])
@login_required
def edit_program(program):
    if request.method == 'POST':
        path = request.form['path']
        config["program_mapping"][program] = path
        save_config()
        return redirect(url_for('index'))
    return render_template('edit_program.html', program=program, path=config["program_mapping"].get(program, ''))

@app.route('/custom_commands', methods=['GET', 'POST'])
@login_required
def custom_commands():
    if request.method == 'POST':
        command = request.form['command']
        action = request.form['action']
        config['custom_commands'][command] = action
        save_config()
        flash('Custom command added successfully.', 'success')
        return redirect(url_for('custom_commands'))
    return render_template('custom_commands.html', custom_commands=config.get('custom_commands', {}))

def save_config():
    try:
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)
        logging.debug("Configuration saved")
    except Exception as e:
        logging.error(f"Error saving configuration: {e}")

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
@login_required
def set_config():
    data = request.json
    for key, value in data.items():
        config[key] = value
    save_config()
    return jsonify(config), 200

@app.route('/api/config/program', methods=['POST'])
@login_required
def add_program_mapping():
    data = request.json
    program = data.get('program')
    path = data.get('path')
    if program and path:
        config["program_mapping"][program] = path
        save_config()
        return jsonify(config["program_mapping"]), 200
    return jsonify({'error': 'Invalid data'}), 400

@app.route('/api/config/program/<program>', methods=['DELETE'])
@login_required
def remove_program_mapping(program):
    if program in config["program_mapping"]:
        del config["program_mapping"][program]
        save_config()
        return jsonify(config["program_mapping"]), 200
    return jsonify({'error': 'Program not found'}), 404

@app.route('/dashboard')
@login_required
def dashboard():
    logs = []
    with open('logs/voiceme.log') as log_file:
        logs = log_file.readlines()
    
    # Parse logs for levels and counts
    parsed_logs = []
    log_levels = ['INFO', 'WARNING', 'ERROR', 'DEBUG']
    log_counts = Counter({level: 0 for level in log_levels})
    
    for log in logs:
        parts = log.split(' - ')
        if len(parts) > 2:
            timestamp = parts[0]
            level = parts[1]
            message = ' - '.join(parts[2:])
            if level in log_levels:
                log_counts[level] += 1
                parsed_logs.append({'timestamp': timestamp, 'level': level, 'message': message})
    
    return render_template('dashboard.html', logs=parsed_logs, log_counts=log_counts)

@app.route('/admin/restart', methods=['POST'])
@login_required
def restart():
    if current_user.username != 'admin':
        return 'Unauthorized', 403
    logging.info("Restarting application...")
    os.execv(sys.executable, ['"{}"'.format(sys.executable)] + sys.argv)
    return redirect(url_for('index'))

@app.route('/customize_voice', methods=['GET', 'POST'])
@login_required
def customize_voice():
    if request.method == 'POST':
        voice_id = request.form['voice_id']
        config['voice_id'] = voice_id
        save_config()
        flash('Voice settings updated.', 'success')
        return redirect(url_for('index'))
    return render_template('customize_voice.html', voices=get_available_voices())

def get_available_voices():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    available_voices = [{'id': voice.id, 'name': voice.name} for voice in voices]
    return available_voices

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    logging.error(f"404 error: {e}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"500 error: {e}")
    return render_template('500.html'), 500

if __name__ == "__main__":
    logging.debug("Application starting")
    with app.app_context():
        db.create_all()
        logging.debug("Database tables created")
    try:
        from waitress import serve
        logging.info("Starting server on 127.0.0.1:8000")
        serve(app, host="127.0.0.1", port=8000)
    except Exception as e:
        logging.error(f"Error starting server: {e}")
