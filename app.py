import streamlit as st
import cv2
from ultralytics import YOLO

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Overcrowd Detection System",
    layout="wide"
)

# ---------------- CUSTOM DARK UI ----------------
st.markdown("""
<style>
.stApp { background-color:black; }
[data-testid="stSidebar"] {
    background-color: #0f172a;
    width: 350px !important;
}
[data-testid="stSidebar"] * {
    color: white;
    font-size: 16px;
}
.stButton > button {
    background: linear-gradient(90deg, #2563eb, #1e40af);
    color: white;
    font-size: 18px;
    padding: 12px;
    border-radius: 12px;
    width: 100%;
}
.stAlert {
    border-radius: 12px;
    font-size: 18px;
}
img { border-radius: 15px; }
</style>
""", unsafe_allow_html=True)

# ---------------- TITLE ----------------
st.markdown("""
<h1 style='text-align:center;color:#38bdf8;font-size:48px;'>
🚨 OVERCROWD DETECTION 
</h1>
<p style='text-align:center;color:white;font-size:20px;'>
Smart real-time crowd monitoring using YOLOv8
</p>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
st.sidebar.markdown("<h2 style='text-align:center;'>🎛 CONTROL PANEL</h2>", unsafe_allow_html=True)

max_people = st.sidebar.slider("👥 Allowed Crowd Limit", 1, 200, 25)
start_btn = st.sidebar.button("▶ START CROWD ANALYSIS")

# ---------------- LOAD MODEL ----------------
@st.cache_resource
def load_model():
    return YOLO("yolov8n.pt")

model = load_model()

VIDEO_PATH = "crowd_video.mp4"

video_area = st.empty()
status_area = st.empty()

# ---------------- MAIN LOGIC ----------------
if start_btn:

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        st.error("❌ Video file not found")
    else:
        status_area.success("✅ Video loaded successfully")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # ✅ Resize video (IMPORTANT FIX)
            frame = cv2.resize(frame, (960, 540))

            results = model(frame, conf=0.30, classes=[0])
            boxes = results[0].boxes
            people_count = len(boxes)

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(
                    frame, f"Person {i+1}",
                    (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2
                )

            if people_count > max_people:
                status_area.error(f"🚨 OVERCROWD ALERT: {people_count}/{max_people}")
                cv2.rectangle(frame, (0, 0), (frame.shape[1], 55), (0, 0, 255), -1)
                cv2.putText(
                    frame, "OVERCROWDING DETECTED!",
                    (25, 38),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1, (255, 255, 255), 3
                )
            else:
                status_area.success(f"✅ Crowd Normal ({people_count}/{max_people})")

            cv2.putText(
                frame, f"Total People: {people_count}",
                (20, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9, (255, 255, 0), 2
            )

            # ✅ Convert BGR → RGB for Streamlit
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # ✅ Proper display
            video_area.image(frame_rgb, use_column_width=True)

        cap.release()
        st.info("🎬 Crowd analysis completed")