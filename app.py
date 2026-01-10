from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE = 'reports.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            reporter_name TEXT NOT NULL,
            reporter_phone TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            image_path TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Initialize database on startup
init_db()

@app.route('/api/reports', methods=['GET'])
def get_reports():
    """Get all reports (without personal info for privacy)"""
    only_open = request.args.get('onlyOpen', 'false').lower() == 'true'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if only_open:
        cursor.execute('''
            SELECT id, description, latitude, longitude, image_path, status, created_at
            FROM reports
            WHERE status != 'RESOLVED'
            ORDER BY created_at DESC
        ''')
    else:
        cursor.execute('''
            SELECT id, description, latitude, longitude, image_path, status, created_at
            FROM reports
            ORDER BY created_at DESC
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    reports = []
    for row in rows:
        reports.append({
            'id': row[0],
            'description': row[1],
            'latitude': row[2],
            'longitude': row[3],
            'image_path': row[4],
            'status': row[5],
            'created_at': row[6]
            # REMOVED: reporter_name and reporter_phone for privacy
        })
    
    return jsonify(reports)

@app.route('/api/reports/<int:report_id>/details', methods=['GET'])
def get_report_details(report_id):
    """Get full report details including personal info (for NGO use only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, description, reporter_name, reporter_phone, 
               latitude, longitude, image_path, status, created_at
        FROM reports
        WHERE id = ?
    ''', (report_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Report not found'}), 404
    
    report = {
        'id': row[0],
        'description': row[1],
        'reporter_name': row[2],
        'reporter_phone': row[3],
        'latitude': row[4],
        'longitude': row[5],
        'image_path': row[6],
        'status': row[7],
        'created_at': row[8]
    }
    
    return jsonify(report)

@app.route('/api/reports', methods=['POST'])
def create_report():
    """Create a new report"""
    try:
        description = request.form.get('description')
        reporter_name = request.form.get('reporter_name')
        reporter_phone = request.form.get('reporter_phone')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        if not description or not reporter_name or not reporter_phone:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Handle image upload
        image_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = str(int(os.time.time() * 1000))
                unique_filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                image_path = f"/uploads/{unique_filename}"
        
        # Insert into database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reports (description, reporter_name, reporter_phone, latitude, longitude, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (description, reporter_name, reporter_phone, latitude, longitude, image_path))
        
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Report created successfully',
            'id': report_id,
            'status': 'PENDING'
        }), 201
        
    except Exception as e:
        print(f"Error creating report: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/<int:report_id>/status', methods=['PATCH'])
def update_status(report_id):
    """Update report status"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if not new_status or new_status not in ['PENDING', 'ON_THE_WAY', 'RESOLVED']:
            return jsonify({'error': 'Invalid status'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE reports
            SET status = ?
            WHERE id = ?
        ''', (new_status, report_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Status updated successfully',
            'id': report_id,
            'status': new_status
        })
        
    except Exception as e:
        print(f"Error updating status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    from flask import send_from_directory
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def index():
    return jsonify({
        'message': 'Animal Rescue API',
        'version': '1.0',
        'endpoints': {
            'GET /api/reports': 'Get all reports',
            'GET /api/reports/<id>/details': 'Get full report details',
            'POST /api/reports': 'Create new report',
            'PATCH /api/reports/<id>/status': 'Update report status'
        }
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
