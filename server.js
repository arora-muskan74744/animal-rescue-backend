const express = require('express');
const cors = require('cors');
const multer = require('multer');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(express.json());

// Create uploads directory if it doesn't exist
if (!fs.existsSync('uploads')) {
  fs.mkdirSync('uploads');
}

app.use('/uploads', express.static('uploads'));

// SQLite database with CORRECT column names
const db = new sqlite3.Database('reports.db');

// DROP old table and CREATE with correct schema
db.serialize(() => {
  // Create table with correct column names
  db.run(`CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    reporter_name TEXT NOT NULL,
    reporter_phone TEXT NOT NULL,
    image_path TEXT,
    latitude REAL,
    longitude REAL,
    status TEXT DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`, (err) => {
    if (err) {
      console.error('Error creating table:', err);
    } else {
      console.log('✅ Database table created successfully');
    }
  });
});

// Multer configuration
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/');
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9);
    const ext = path.extname(file.originalname);
    cb(null, uniqueSuffix + ext);
  }
});

const upload = multer({ 
  storage,
  limits: { fileSize: 5 * 1024 * 1024 }, // 5MB limit
  fileFilter: (req, file, cb) => {
    const allowedTypes = /jpeg|jpg|png|gif|webp/;
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
    const mimetype = allowedTypes.test(file.mimetype);
    
    if (mimetype && extname) {
      return cb(null, true);
    } else {
      cb(new Error('Only images are allowed'));
    }
  }
});

// Test route
app.get('/', (req, res) => {
  res.send('Animal Rescue API is working ✅');
});

// GET all reports
app.get('/api/reports', (req, res) => {
  const onlyOpen = req.query.onlyOpen === 'true';
  
  let sql = 'SELECT * FROM reports';
  if (onlyOpen) {
    sql += " WHERE status != 'RESOLVED'";
  }
  sql += ' ORDER BY created_at DESC';
  
  db.all(sql, [], (err, rows) => {
    if (err) {
      console.error('DB error:', err);
      return res.status(500).json({ error: err.message });
    }
    console.log(`✅ Fetched ${rows.length} reports`);
    res.json(rows);
  });
});

// POST new report
app.post('/api/reports', upload.single('photo'), (req, res) => {
  const { description, reporter_name, reporter_phone, latitude, longitude } = req.body;
  
  console.log('Received body:', req.body);
  console.log('Received file:', req.file);
  
  // Validate required fields
  if (!description || !reporter_name || !reporter_phone) {
    return res.status(400).json({ 
      error: 'Description, reporter name, and phone are required' 
    });
  }
  
  const image_path = req.file ? `/uploads/${req.file.filename}` : null;
  
  const sql = `INSERT INTO reports 
    (description, reporter_name, reporter_phone, image_path, latitude, longitude) 
    VALUES (?, ?, ?, ?, ?, ?)`;
  
  db.run(
    sql,
    [description, reporter_name, reporter_phone, image_path, latitude || null, longitude || null],
    function(err) {
      if (err) {
        console.error('❌ DB insert error:', err);
        return res.status(500).json({ error: err.message });
      }
      
      const newReport = {
        id: this.lastID,
        description,
        reporter_name,
        reporter_phone,
        image_path,
        latitude,
        longitude,
        status: 'PENDING',
        created_at: new Date().toISOString()
      };
      
      console.log('✅ Report created:', newReport);
      res.status(201).json(newReport);
    }
  );
});

// PATCH update status
app.patch('/api/reports/:id/status', (req, res) => {
  const { id } = req.params;
  const { status } = req.body;
  
  const allowed = ['PENDING', 'ON_THE_WAY', 'RESOLVED'];
  if (!allowed.includes(status)) {
    return res.status(400).json({ error: 'Invalid status' });
  }
  
  db.run(
    'UPDATE reports SET status = ? WHERE id = ?', 
    [status, id], 
    function(err) {
      if (err) {
        console.error('DB update error:', err);
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Report not found' });
      }
      console.log(`✅ Report ${id} status updated to ${status}`);
      res.json({ success: true, status });
    }
  );
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Server error:', err);
  res.status(500).json({ error: err.message });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`\n🚀 Server running on http://localhost:${PORT}`);
  console.log(`📁 Uploads directory: ${path.join(__dirname, 'uploads')}`);
  console.log(`💾 Database: reports.db\n`);
});
