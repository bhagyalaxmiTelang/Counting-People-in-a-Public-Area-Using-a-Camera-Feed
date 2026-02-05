"""
JWT-Based Authentication System
Complete implementation with token generation, refresh, and verification
"""

from flask import Flask, request, jsonify
from functools import wraps
import jwt
import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['JWT_ALGORITHM'] = 'HS256'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 3600       # 1 hour
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 2592000   # 30 days

# ==================== DATABASE ====================
class AuthDatabase:
    def __init__(self, db_path='auth.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME,
                failed_attempts INTEGER DEFAULT 0,
                locked_until DATETIME
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at DATETIME NOT NULL,
                revoked INTEGER DEFAULT 0
            )
        ''')

        conn.commit()

        # Create default admin
        cursor.execute("SELECT * FROM users WHERE username='admin'")
        if not cursor.fetchone():
            password_hash = generate_password_hash(
                'admin123', method='pbkdf2:sha256'
            )
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, role)
                VALUES (?, ?, ?, ?)
            ''', ('admin', password_hash, 'admin@example.com', 'admin'))
            conn.commit()
            print("✅ Default admin created: admin / admin123")

        conn.close()

    def get_user_by_username(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        user = cursor.fetchone()
        conn.close()
        return user

    def get_user_by_id(self, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id=?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user

    def create_user(self, username, password, email):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        password_hash = generate_password_hash(
            password, method='pbkdf2:sha256'
        )

        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, email)
                VALUES (?, ?, ?)
            ''', (username, password_hash, email))
            conn.commit()
            conn.close()
            return True, "User created successfully"
        except:
            conn.close()
            return False, "Username or email already exists"

    def verify_password(self, username, password):
        user = self.get_user_by_username(username)
        if not user:
            return False, "User not found"

        if check_password_hash(user[2], password):
            return True, user
        else:
            return False, "Invalid password"

# Initialize DB
auth_db = AuthDatabase()

# ==================== JWT FUNCTIONS ====================
def generate_access_token(user):
    payload = {
        'user_id': user[0],
        'username': user[1],
        'role': user[4],
        'exp': datetime.datetime.utcnow() +
               datetime.timedelta(seconds=app.config['JWT_ACCESS_TOKEN_EXPIRES']),
        'type': 'access'
    }
    return jwt.encode(payload, app.config['SECRET_KEY'],
                      algorithm=app.config['JWT_ALGORITHM'])

def generate_refresh_token(user):
    payload = {
        'user_id': user[0],
        'exp': datetime.datetime.utcnow() +
               datetime.timedelta(seconds=app.config['JWT_REFRESH_TOKEN_EXPIRES']),
        'type': 'refresh'
    }
    return jwt.encode(payload, app.config['SECRET_KEY'],
                      algorithm=app.config['JWT_ALGORITHM'])

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            try:
                token = request.headers['Authorization'].split()[1]
            except:
                return jsonify({'message': 'Invalid token format'}), 401

        if not token:
            return jsonify({'message': 'Token missing'}), 401

        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'],
                                 algorithms=[app.config['JWT_ALGORITHM']])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated

# ==================== API ROUTES ====================
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    success, message = auth_db.create_user(
        data['username'], data['password'], data['email']
    )
    return jsonify({'success': success, 'message': message})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    valid, result = auth_db.verify_password(
        data['username'], data['password']
    )

    if not valid:
        return jsonify({'success': False, 'message': result}), 401

    access = generate_access_token(result)
    refresh = generate_refresh_token(result)

    return jsonify({
        'success': True,
        'access_token': access,
        'refresh_token': refresh
    })

@app.route('/api/protected', methods=['GET'])
@token_required
def protected():
    return jsonify({
        'message': 'Protected route accessed',
        'user': request.current_user
    })

# ==================== MAIN ====================
if __name__ == '__main__':
    print("🔐 JWT Authentication System Running")
    app.run(debug=True, port=5002)
