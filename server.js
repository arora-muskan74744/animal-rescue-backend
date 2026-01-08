const express = require('express');
const cors = require('cors');
const multer = require('multer');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

// Environment variables with defaults
const PORT = process.env.PORT || 5000;
const DATABASE_PATH = process.env.DATABASE_PATH || './reports.db';
const UPLOADS_DIR = process.env.UPLOADS_DIR || './uploads';

// Create uploads directory if it doesn't exist
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

app.use('/uploads', express.static(UPLOADS_DIR));

// SQLite database with path from environment
const db = new sqlite3.Database(DATABASE_PATH, (err) => {
  if (err) {
    console.error('❌ Error connecting to database:', err);
  } else {
    console.log(`✅ Connected to database: ${DATABASE_PATH}`);
  }
});

// Create table with correct schema
db.serialize(() => {
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
      console.error('❌ Error creating table:', err);
    } else {
      console.log('✅ Database table ready');
    }
  });
});

// Multer configuration with dynamic upload directory
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, UPLOADS_DIR);
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
      cb(new Error('Only images are allowed (jpeg, jpg, png, gif, webp)'));
    }
  }
});

// Test route
app.get('/', (req, res) => {
  res.json({
    message: 'Animal Rescue API is working ✅',
    version: '1.0.0',
    endpoints: {
      'GET /api/reports': 'Get all reports',
      'POST /api/reports': 'Create new report',
      'PATCH /api/reports/:id/status': 'Update report status'
    }
  });
});

// Health check route
app.get('/health', (req, res) => {
  db.get('SELECT COUNT(*) as count FROM reports', (err, row) => {
    if (err) {
      return res.status(500).json({ status: 'unhealthy', error: err.message });
    }
    res.json({
      status: 'healthy',
      database: 'connected',
      totalReports: row.count,
      uptime: process.uptime(),
      timestamp: new Date().toISOString()
    });
  });
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
      console.error('❌ DB error:', err);
      return res.status(500).json({ error: err.message });
    }
    console.log(`✅ Fetched ${rows.length} reports`);
    res.json(rows);
  });
});

// POST new report
app.post('/api/reports', upload.single('photo'), (req, res) => {
  const { description, reporter_name, reporter_phone, latitude, longitude } = req.body;
  
  console.log('📥 Received body:', req.body);
  console.log('📷 Received file:', req.file ? req.file.filename : 'No file');
  
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
      
      console.log('✅ Report created:', newReport.id);
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
    return res.status(400).json({ error: 'Invalid status. Allowed: PENDING, ON_THE_WAY, RESOLVED' });
  }
  
  db.run(
    'UPDATE reports SET status = ? WHERE id = ?', 
    [status, id], 
    function(err) {
      if (err) {
        console.error('❌ DB update error:', err);
        return res.status(500).json({ error: err.message });
      }
      if (this.changes === 0) {
        return res.status(404).json({ error: 'Report not found' });
      }
      console.log(`✅ Report #${id} → ${status}`);
      res.json({ success: true, status });
    }
  );
});

// DELETE report (optional - for testing)
app.delete('/api/reports/:id', (req, res) => {
  const { id } = req.params;
  
  db.run('DELETE FROM reports WHERE id = ?', [id], function(err) {
    if (err) {
      console.error('❌ DB delete error:', err);
      return res.status(500).json({ error: err.message });
    }
    if (this.changes === 0) {
      return res.status(404).json({ error: 'Report not found' });
    }
    console.log(`🗑️ Deleted report #${id}`);
    res.json({ success: true, message: 'Report deleted' });
  });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('❌ Server error:', err);
  res.status(500).json({ error: err.message });
});

// 404 handler
app.use((req, res) => {
  res.status(404).json({ error: 'Route not found' });
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n⏹️ Shutting down gracefully...');
  db.close((err) => {
    if (err) {
      console.error('Error closing database:', err);
    } else {
      console.log('✅ Database connection closed');
    }
    process.exit(0);
  });
});

// Start server
app.listen(PORT, () => {
  console.log('\n' + '='.repeat(50));
  console.log('🚀 Animal Rescue API Server');
  console.log('='.repeat(50));
  console.log(`🌐 URL: http://localhost:${PORT}`);
  console.log(`💾 Database: ${DATABASE_PATH}`);
  console.log(`📁 Uploads: ${path.resolve(UPLOADS_DIR)}`);
  console.log(`🔧 Environment: ${process.env.NODE_ENV || 'development'}`);
  console.log('='.repeat(50) + '\n');
});
