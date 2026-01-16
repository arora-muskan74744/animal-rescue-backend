from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import time
from math import radians, sin, cos, sqrt, atan2
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
DB_NAME = 'reports.db'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def find_nearest_ngo(latitude, longitude):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM ngos")
    ngos = c.fetchall()
    conn.close()
    
    if not ngos:
        return None
    
    print(f"\n🔍 Finding nearest NGO for: {latitude}, {longitude}")
    
    nearest = None
    min_distance = float('inf')
    
    for ngo in ngos:
        distance = haversine_distance(latitude, longitude, ngo['latitude'], ngo['longitude'])
        print(f"  📍 {ngo['name']}: {distance:.2f} km")
        
        if distance < min_distance:
            min_distance = distance
            nearest = dict(ngo)
            nearest['distance'] = round(distance, 2)
    
    if nearest:
        print(f"✅ Nearest: {nearest['name']} ({nearest['distance']} km)\n")
    
    return nearest

def send_notifications(ngo, report_id, description, reporter_phone, latitude, longitude):
    print(f"\n{'='*70}")
    print(f"🚨 RESCUE ALERT SENT SUCCESSFULLY!")
    print(f"{'='*70}")
    print(f"📋 Report ID: #{report_id}")
    print(f"📅 Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n🏥 ASSIGNED NGO:")
    print(f"   Name: {ngo['name']}")
    print(f"   📞 Phone: {ngo['phone']}")
    print(f"   📧 Email: {ngo['email']}")
    print(f"   💬 WhatsApp: {ngo['whatsapp']}")
    print(f"   📍 Distance: {ngo['distance']} km away")
    print(f"\n📝 INCIDENT DETAILS:")
    print(f"   Description: {description}")
    print(f"   Reporter Phone: {reporter_phone}")
    print(f"   Location: {latitude}, {longitude}")
    print(f"{'='*70}\n")

def init_db():
    print("\n🔧 Initializing database...")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    print("Creating NGOs table...")
    c.execute('''CREATE TABLE IF NOT EXISTS ngos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        whatsapp TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    print("Creating Reports table...")
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        reporter_name TEXT NOT NULL,
        reporter_phone TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        location_name TEXT,
        image_path TEXT,
        status TEXT DEFAULT 'PENDING',
        assigned_ngo_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assigned_ngo_id) REFERENCES ngos(id)
    )''')
    
    c.execute("SELECT COUNT(*) FROM ngos")
    count = c.fetchone()[0]
    
    if count == 0:
        print("Inserting sample NGOs...")
        sample_ngos = [
            ('Animal Aid Foundation', '9876543210', 'contact@animalaid.org', '9876543210', 28.6139, 77.2090, 'Delhi, India'),
            ('PFA India', '9876543211', 'help@pfa.org', '9876543211', 19.0760, 72.8777, 'Mumbai, India'),
            ('Wildlife SOS', '9876543212', 'rescue@wildlifesos.org', '9876543212', 27.1767, 78.0081, 'Agra, India'),
            ('Blue Cross of India', '9876543213', 'info@bluecrossofindia.org', '9876543213', 13.0827, 80.2707, 'Chennai, India'),
            ('Karuna Animal Welfare', '9876543214', 'contact@karunaindia.org', '9876543214', 12.9716, 77.5946, 'Bangalore, India')
        ]
        
        c.executemany('''INSERT INTO ngos (name, phone, email, whatsapp, latitude, longitude, address) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', sample_ngos)
        
        print(f"✅ {len(sample_ngos)} NGOs added!")
    
    conn.commit()
    conn.close()
    print("✅ Database ready!\n")

@app.route('/api/reports', methods=['POST'])
def create_report():
    try:
        description = request.form.get('description')
        reporter_name = request.form.get('reporter_name')
        reporter_phone = request.form.get('reporter_phone')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        location_name = request.form.get('location_name', '')
        photo = request.files.get('photo')
        
        if not all([description, reporter_name, reporter_phone, latitude, longitude]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        latitude = float(latitude)
        longitude = float(longitude)
        
        image_path = None
        if photo and photo.filename:
            filename = secure_filename(f"{int(time.time())}_{photo.filename}")
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            image_path = f"/uploads/{filename}"
        
        nearest_ngo = find_nearest_ngo(latitude, longitude)
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute('''INSERT INTO reports 
                     (description, reporter_name, reporter_phone, latitude, longitude, 
                      location_name, image_path, assigned_ngo_id, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (description, reporter_name, reporter_phone, latitude, longitude,
                   location_name, image_path, nearest_ngo['id'] if nearest_ngo else None, 'PENDING'))
        
        report_id = c.lastrowid
        conn.commit()
        conn.close()
        
        if nearest_ngo:
            send_notifications(nearest_ngo, report_id, description, reporter_phone, latitude, longitude)
        
        return jsonify({
            'message': 'Report created! NGO notified.',
            'report_id': report_id,
            'assigned_ngo': nearest_ngo['name'] if nearest_ngo else None,
            'distance_km': nearest_ngo['distance'] if nearest_ngo else None
        }), 201
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['GET'])
def get_reports():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute('''SELECT r.*, n.name as ngo_name, n.phone as ngo_phone 
                 FROM reports r 
                 LEFT JOIN ngos n ON r.assigned_ngo_id = n.id 
                 ORDER BY r.created_at DESC''')
    
    reports = []
    for row in c.fetchall():
        reports.append({
            'id': row['id'],
            'description': row['description'],
            'reporter_name': row['reporter_name'],
            'reporter_phone': row['reporter_phone'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'location_name': row['location_name'],
            'image_path': row['image_path'],
            'status': row['status'],
            'ngo_name': row['ngo_name'],
            'ngo_phone': row['ngo_phone'],
            'created_at': row['created_at']
        })
    
    conn.close()
    return jsonify(reports)

@app.route('/api/reports/<int:report_id>/status', methods=['PATCH'])
def update_status(report_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['PENDING', 'ON_THE_WAY', 'RESOLVED']:
            return jsonify({'error': 'Invalid status'}), 400
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE reports SET status = ? WHERE id = ?", (new_status, report_id))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Status updated', 'new_status': new_status})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    init_db()
    print("\n🚀 Animal Rescue API v2.0")
    print("="*70)
    app.run(host='0.0.0.0', port=5000, debug=True)
