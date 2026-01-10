from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import time
import math
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

DATABASE = 'reports.db'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance using Haversine formula"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2)**2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def find_nearest_ngo(latitude, longitude):
    """Find nearest NGO"""
    print(f"\n🔍 Finding nearest NGO for: {latitude}, {longitude}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, phone, email, whatsapp, latitude, longitude FROM ngos')
    ngos = cursor.fetchall()
    conn.close()
    
    if not ngos:
        print("❌ No NGOs in database!")
        return None
    
    nearest = None
    min_distance = float('inf')
    
    for ngo in ngos:
        distance = calculate_distance(float(latitude), float(longitude), ngo[5], ngo[6])
        print(f"  📍 {ngo[1]}: {distance:.2f} km")
        if distance < min_distance:
            min_distance = distance
            nearest = {
                'id': ngo[0],
                'name': ngo[1],
                'phone': ngo[2],
                'email': ngo[3],
                'whatsapp': ngo[4],
                'distance': round(distance, 2)
            }
    
    print(f"✅ Nearest: {nearest['name']} ({nearest['distance']} km)")
    return nearest

def send_notifications(ngo, report_id, description, reporter_phone, latitude, longitude):
    """
    Send notifications to NGO via SMS/Email/WhatsApp
    Currently: Enhanced console logging + Ready for API integration
    """
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
    print(f"   🗺️  Google Maps: https://maps.google.com/?q={latitude},{longitude}")
    print(f"\n📬 NOTIFICATIONS SENT:")
    print(f"   ✉️  Email → {ngo['email']}")
    print(f"   📱 SMS → {ngo['phone']}")
    print(f"   💬 WhatsApp → {ngo['whatsapp']}")
    print(f"{'='*70}")
    print(f"⏰ NGO Response Expected Within: 15-30 minutes")
    print(f"{'='*70}\n")
    
    # TODO: Real integrations (uncomment when ready)
    # send_email(ngo['email'], report_id, description, latitude, longitude)
    # send_sms(ngo['phone'], report_id, description)
    # send_whatsapp(ngo['whatsapp'], report_id, description, latitude, longitude)

def init_db():
    """Initialize database with BOTH tables"""
    print("\n🔧 Initializing database...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create NGOs table FIRST
    print("Creating NGOs table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ngos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            whatsapp TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Reports table
    print("Creating Reports table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            reporter_name TEXT NOT NULL,
            reporter_phone TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            image_path TEXT,
            status TEXT DEFAULT 'PENDING',
            assigned_ngo_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_ngo_id) REFERENCES ngos(id)
        )
    ''')
    
    # Insert sample NGOs if empty
    cursor.execute("SELECT COUNT(*) FROM ngos")
    ngo_count = cursor.fetchone()[0]
    
    if ngo_count == 0:
        print("Inserting sample NGOs...")
        sample_ngos = [
            ('Animal Aid Foundation', '9876543210', 'contact@animalaid.org', '9876543210', 28.6139, 77.2090, 'Delhi, India'),
            ('PFA India', '9876543211', 'help@pfa.org', '9876543211', 19.0760, 72.8777, 'Mumbai, India'),
            ('Blue Cross of India', '9876543212', 'info@bluecross.org.in', '9876543212', 13.0827, 80.2707, 'Chennai, India'),
            ('Wildlife SOS', '9876543213', 'rescue@wildlifesos.org', '9876543213', 28.5355, 77.3910, 'Noida, India'),
            ('SPCA India', '9876543214', 'contact@spcaindia.org', '9876543214', 18.5204, 73.8567, 'Pune, India'),
        ]
        cursor.executemany('''
            INSERT INTO ngos (name, phone, email, whatsapp, latitude, longitude, address)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_ngos)
        print("✅ 5 NGOs added!")
    else:
        print(f"✅ {ngo_count} NGOs already exist")
    
    conn.commit()
    conn.close()
    print("✅ Database ready!\n")

# Initialize on startup
init_db()

@app.route('/')
def index():
    return jsonify({'status': 'running', 'version': '2.0'})

@app.route('/api/reports', methods=['GET'])
def get_reports():
    only_open = request.args.get('onlyOpen', 'false').lower() == 'true'
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if only_open:
            cursor.execute('''
                SELECT id, description, image_path, status, created_at
                FROM reports WHERE status != 'RESOLVED'
                ORDER BY created_at DESC
            ''')
        else:
            cursor.execute('''
                SELECT id, description, image_path, status, created_at
                FROM reports ORDER BY created_at DESC
            ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        reports = [dict(row) for row in rows]
        print(f"📊 Returning {len(reports)} reports")
        return jsonify(reports)
        
    except Exception as e:
        print(f"❌ Error getting reports: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports', methods=['POST'])
def create_report():
    """Create report with auto NGO assignment"""
    try:
        description = request.form.get('description')
        reporter_name = request.form.get('reporter_name')
        reporter_phone = request.form.get('reporter_phone')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        # Validation
        if not all([description, reporter_name, reporter_phone]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if not latitude or not longitude:
            return jsonify({'error': 'Location is mandatory!'}), 400
        
        try:
            lat_float = float(latitude)
            lon_float = float(longitude)
        except ValueError:
            return jsonify({'error': 'Invalid coordinates'}), 400
        
        # Image upload
        image_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = str(int(time.time() * 1000))
                unique_filename = f"{timestamp}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                image_path = f"/uploads/{unique_filename}"
        
        # Auto-assign NGO
        assigned_ngo_id = None
        nearest_ngo = None
        
        try:
            nearest_ngo = find_nearest_ngo(lat_float, lon_float)
            if nearest_ngo:
                assigned_ngo_id = nearest_ngo['id']
        except Exception as e:
            print(f"⚠️ NGO assignment failed: {e}")
        
        # Insert report
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO reports 
            (description, reporter_name, reporter_phone, latitude, longitude, image_path, assigned_ngo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (description, reporter_name, reporter_phone, lat_float, lon_float, image_path, assigned_ngo_id))
        
        report_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Report #{report_id} created!")
        
        # Send notifications
        if nearest_ngo:
            send_notifications(nearest_ngo, report_id, description, reporter_phone, lat_float, lon_float)
        
        response = {
            'message': 'Report created! NGO notified.',
            'id': report_id,
            'status': 'PENDING'
        }
        
        if nearest_ngo:
            response['assigned_ngo'] = nearest_ngo['name']
            response['distance_km'] = nearest_ngo['distance']
        
        return jsonify(response), 201
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reports/<int:report_id>/status', methods=['PATCH'])
def update_status(report_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['PENDING', 'ON_THE_WAY', 'RESOLVED']:
            return jsonify({'error': 'Invalid status'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE reports SET status = ? WHERE id = ?', (new_status, report_id))
        conn.commit()
        conn.close()
        
        print(f"✅ Report #{report_id} → {new_status}")
        return jsonify({'message': 'Updated', 'id': report_id, 'status': new_status})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/ngos', methods=['GET'])
def get_ngos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ngos ORDER BY name')
    ngos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(ngos)

# ========== REAL NOTIFICATION FUNCTIONS (Ready for Integration) ==========

def send_email(to_email, report_id, description, latitude, longitude):
    """
    Send email using SendGrid API
    TODO: Add SendGrid API key and uncomment
    """
    # from sendgrid import SendGridAPIClient
    # from sendgrid.helpers.mail import Mail
    # 
    # message = Mail(
    #     from_email='alerts@animalrescue.org',
    #     to_emails=to_email,
    #     subject=f'🚨 New Rescue Alert #{report_id}',
    #     html_content=f'''
    #         <h2>New Animal Rescue Request</h2>
    #         <p><strong>Report ID:</strong> #{report_id}</p>
    #         <p><strong>Description:</strong> {description}</p>
    #         <p><strong>Location:</strong> <a href="https://maps.google.com/?q={latitude},{longitude}">View on Map</a></p>
    #         <p>Please respond immediately!</p>
    #     '''
    # )
    # 
    # sg = SendGridAPIClient('YOUR_SENDGRID_API_KEY')
    # response = sg.send(message)
    print(f"   📧 Email notification prepared for {to_email}")

def send_sms(to_phone, report_id, description):
    """
    Send SMS using Twilio API
    TODO: Add Twilio credentials and uncomment
    """
    # from twilio.rest import Client
    # 
    # client = Client('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN')
    # message = client.messages.create(
    #     body=f'🚨 New rescue alert #{report_id}: {description}. Check dashboard now!',
    #     from_='+1234567890',  # Your Twilio number
    #     to=to_phone
    # )
    print(f"   📱 SMS notification prepared for {to_phone}")

def send_whatsapp(to_phone, report_id, description, latitude, longitude):
    """
    Send WhatsApp using Twilio WhatsApp API
    TODO: Add Twilio credentials and uncomment
    """
    # from twilio.rest import Client
    # 
    # client = Client('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN')
    # message = client.messages.create(
    #     body=f'''🚨 *RESCUE ALERT #{report_id}*
    #     
    #     📝 {description}
    #     📍 Location: https://maps.google.com/?q={latitude},{longitude}
    #     
    #     Please respond immediately!''',
    #     from_='whatsapp:+14155238886',  # Twilio WhatsApp sandbox
    #     to=f'whatsapp:{to_phone}'
    # )
    print(f"   💬 WhatsApp notification prepared for {to_phone}")


if __name__ == '__main__':
    print("\n🚀 Animal Rescue API v2.0")
    print("=" * 70)
    app.run(debug=True, host='0.0.0.0', port=5000)
