import cv2
import numpy as np
from ultralytics import YOLO
import sqlite3
from datetime import datetime
import json
from collections import defaultdict
import threading
import time
from flask import Flask, render_template, Response, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==================== CONFIGURATION ====================
class Config:
    # Camera Configuration
    CAMERA_SOURCES = {
        'camera_1': 0,  # or 'rtsp://camera_ip/stream'
        'camera_2': 1,
    }
    
    # Zone Configuration
    ZONES = {
        'zone_1': {
            'polygon': [(100, 100), (400, 100), (400, 400), (100, 400)],
            'capacity': 50,
            'alert_threshold': 0.8  # 80% capacity
        },
        'zone_2': {
            'polygon': [(500, 100), (800, 100), (800, 400), (500, 400)],
            'capacity': 30,
            'alert_threshold': 0.9
        }
    }
    
    # Model Configuration
    YOLO_MODEL = 'yolov8n.pt'  # or 'yolov8s.pt', 'yolov8m.pt' for better accuracy
    CONFIDENCE_THRESHOLD = 0.5
    
    # Database
    DB_PATH = 'crowd_data.db'
    
    # Alerts
    EMAIL_CONFIG = {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender_email': 'your_email@gmail.com',
        'sender_password': 'your_app_password',
        'recipient_emails': ['admin@example.com']
    }
    
    # Firebase (Optional - comment out if not using)
    # FIREBASE_CREDENTIALS = 'firebase_credentials.json'

# ==================== DATABASE SETUP ====================
class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                camera_id TEXT,
                zone_id TEXT,
                person_count INTEGER,
                confidence REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                zone_id TEXT,
                alert_type TEXT,
                person_count INTEGER,
                capacity INTEGER,
                status TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS review_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                camera_id TEXT,
                zone_id TEXT,
                snapshot_path TEXT,
                notes TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_detection(self, camera_id, zone_id, person_count, confidence):
        """Insert detection record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO detections (camera_id, zone_id, person_count, confidence)
            VALUES (?, ?, ?, ?)
        ''', (camera_id, zone_id, person_count, confidence))
        conn.commit()
        conn.close()
    
    def insert_alert(self, zone_id, alert_type, person_count, capacity):
        """Insert alert record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (zone_id, alert_type, person_count, capacity, status)
            VALUES (?, ?, ?, ?, 'active')
        ''', (zone_id, alert_type, person_count, capacity))
        conn.commit()
        conn.close()
    
    def get_recent_stats(self, hours=24):
        """Get statistics for dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT zone_id, AVG(person_count), MAX(person_count), COUNT(*)
            FROM detections
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
            GROUP BY zone_id
        ''', (hours,))
        
        stats = cursor.fetchall()
        conn.close()
        return stats

# ==================== YOLO DETECTOR ====================
class CrowdDetector:
    def __init__(self, model_path):
        """Initialize YOLO model"""
        self.model = YOLO(model_path)
        self.person_class_id = 0  # COCO dataset person class
    
    def detect_people(self, frame, confidence_threshold=0.5):
        """Detect people in frame"""
        results = self.model(frame, verbose=False)[0]
        people = []
        
        for box in results.boxes:
            if int(box.cls[0]) == self.person_class_id and float(box.conf[0]) >= confidence_threshold:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                confidence = float(box.conf[0])
                
                people.append({
                    'bbox': (x1, y1, x2, y2),
                    'center': (center_x, center_y),
                    'confidence': confidence
                })
        
        return people

# ==================== ZONE LOGIC ====================
class ZoneManager:
    def __init__(self, zones):
        self.zones = zones
    
    def point_in_polygon(self, point, polygon):
        """Check if point is inside polygon"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def count_people_in_zones(self, people):
        """Count people in each zone"""
        zone_counts = defaultdict(int)
        
        for person in people:
            center = person['center']
            for zone_id, zone_config in self.zones.items():
                if self.point_in_polygon(center, zone_config['polygon']):
                    zone_counts[zone_id] += 1
                    break
        
        return dict(zone_counts)
    
    def check_alerts(self, zone_counts):
        """Check if any zone exceeds threshold"""
        alerts = []
        
        for zone_id, count in zone_counts.items():
            zone_config = self.zones[zone_id]
            capacity = zone_config['capacity']
            threshold = zone_config['alert_threshold']
            
            if count >= capacity * threshold:
                alerts.append({
                    'zone_id': zone_id,
                    'count': count,
                    'capacity': capacity,
                    'percentage': (count / capacity) * 100,
                    'type': 'capacity_warning' if count < capacity else 'capacity_exceeded'
                })
        
        return alerts

# ==================== ALERT SYSTEM ====================
class AlertSystem:
    def __init__(self, email_config):
        self.email_config = email_config
        self.last_alert_time = defaultdict(int)
        self.alert_cooldown = 300  # 5 minutes
    
    def send_email_alert(self, alert_info):
        """Send email notification"""
        try:
            current_time = time.time()
            zone_id = alert_info['zone_id']
            
            # Check cooldown
            if current_time - self.last_alert_time[zone_id] < self.alert_cooldown:
                return
            
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = ', '.join(self.email_config['recipient_emails'])
            msg['Subject'] = f"Crowd Alert: {zone_id}"
            
            body = f"""
            Alert Type: {alert_info['type']}
            Zone: {zone_id}
            Current Count: {alert_info['count']}
            Capacity: {alert_info['capacity']}
            Occupancy: {alert_info['percentage']:.1f}%
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.email_config['smtp_server'], 
                                self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['sender_email'], 
                        self.email_config['sender_password'])
            server.send_message(msg)
            server.quit()
            
            self.last_alert_time[zone_id] = current_time
            print(f"Alert email sent for {zone_id}")
            
        except Exception as e:
            print(f"Error sending email: {e}")

# ==================== PROCESSING ENGINE ====================
class ProcessingEngine:
    def __init__(self, config):
        self.config = config
        self.detector = CrowdDetector(config.YOLO_MODEL)
        self.zone_manager = ZoneManager(config.ZONES)
        self.db_manager = DatabaseManager(config.DB_PATH)
        self.alert_system = AlertSystem(config.EMAIL_CONFIG)
        self.running = False
        self.current_frame = None
        self.stats = defaultdict(int)
    
    def process_camera(self, camera_id, source):
        """Process video stream from camera"""
        cap = cv2.VideoCapture(source)
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect people
            people = self.detector.detect_people(
                frame, 
                self.config.CONFIDENCE_THRESHOLD
            )
            
            # Count people in zones
            zone_counts = self.zone_manager.count_people_in_zones(people)
            
            # Draw on frame
            annotated_frame = self.draw_annotations(
                frame.copy(), 
                people, 
                zone_counts
            )
            
            self.current_frame = annotated_frame
            
            # Store in database
            for zone_id, count in zone_counts.items():
                self.db_manager.insert_detection(
                    camera_id, 
                    zone_id, 
                    count, 
                    np.mean([p['confidence'] for p in people]) if people else 0
                )
            
            # Check alerts
            alerts = self.zone_manager.check_alerts(zone_counts)
            for alert in alerts:
                self.db_manager.insert_alert(
                    alert['zone_id'],
                    alert['type'],
                    alert['count'],
                    alert['capacity']
                )
                self.alert_system.send_email_alert(alert)
            
            # Update stats
            self.stats['total_people'] = sum(zone_counts.values())
            self.stats['zone_counts'] = zone_counts
            self.stats['alerts'] = len(alerts)
            
            time.sleep(0.1)  # Process at ~10 FPS
        
        cap.release()
    
    def draw_annotations(self, frame, people, zone_counts):
        """Draw bounding boxes and zones"""
        # Draw zones
        for zone_id, zone_config in self.config.ZONES.items():
            pts = np.array(zone_config['polygon'], np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            count = zone_counts.get(zone_id, 0)
            capacity = zone_config['capacity']
            color = (0, 255, 0) if count < capacity * 0.8 else (0, 165, 255) if count < capacity else (0, 0, 255)
            
            cv2.polylines(frame, [pts], True, color, 2)
            cv2.putText(frame, f"{zone_id}: {count}/{capacity}", 
                       zone_config['polygon'][0], 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        # Draw people bounding boxes
        for person in people:
            x1, y1, x2, y2 = person['bbox']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(frame, person['center'], 4, (0, 0, 255), -1)
        
        # Draw total count
        cv2.putText(frame, f"Total People: {len(people)}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        return frame
    
    def start(self):
        """Start processing"""
        self.running = True
        threads = []
        
        for camera_id, source in self.config.CAMERA_SOURCES.items():
            thread = threading.Thread(
                target=self.process_camera, 
                args=(camera_id, source)
            )
            thread.start()
            threads.append(thread)
        
        return threads
    
    def stop(self):
        """Stop processing"""
        self.running = False

# ==================== WEB DASHBOARD (Flask) ====================
app = Flask(__name__)
engine = None

@app.route('/')
def index():
    """Dashboard home page"""
    return render_template('dashboard.html')

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    def generate():
        while True:
            if engine and engine.current_frame is not None:
                ret, buffer = cv2.imencode('.jpg', engine.current_frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.1)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/stats')
def get_stats():
    """Get current statistics"""
    if engine:
        return jsonify({
            'total_people': engine.stats.get('total_people', 0),
            'zone_counts': engine.stats.get('zone_counts', {}),
            'alerts': engine.stats.get('alerts', 0),
            'timestamp': datetime.now().isoformat()
        })
    return jsonify({'error': 'Engine not running'})

@app.route('/api/trends')
def get_trends():
    """Get historical trends"""
    db = DatabaseManager(Config.DB_PATH)
    stats = db.get_recent_stats(24)
    return jsonify({'trends': stats})

# ==================== MAIN APPLICATION ====================
def main():
    """Main application entry point"""
    global engine
    
    print("Initializing Crowd Counting System...")
    
    # Create config
    config = Config()
    
    # Initialize processing engine
    engine = ProcessingEngine(config)
    
    # Start processing in background
    print("Starting video processing...")
    threads = engine.start()
    
    # Start Flask dashboard
    print("Starting dashboard on http://localhost:5000")
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\nStopping system...")
        engine.stop()
        for thread in threads:
            thread.join()
        print("System stopped.")

if __name__ == '__main__':
    main()