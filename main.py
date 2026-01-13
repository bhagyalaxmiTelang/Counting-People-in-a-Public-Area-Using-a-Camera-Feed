import cv2
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# ---------------- YOLO MODEL ----------------
model = YOLO("yolov8n.pt")

# ---------------- DEEP SORT ----------------
tracker = DeepSort(
    max_age=30,
    n_init=3,
    max_iou_distance=0.7
)

# Store counted IDs
counted_ids = set()

# ---------------- DETECTION + TRACKING ----------------
def detect_track_and_count(frame):
    results = model(frame, conf=0.5)[0]

    detections = []

    # YOLO detections
    for box in results.boxes:
        cls_id = int(box.cls[0])
        label = results.names[cls_id]

        if label == "person":
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            w = x2 - x1
            h = y2 - y1
            confidence = float(box.conf[0])

            # Deep SORT format: [x, y, w, h], confidence, class
            detections.append(([x1, y1, w, h], confidence, "person"))

    # Update tracker
    tracks = tracker.update_tracks(detections, frame=frame)

    for track in tracks:
        if not track.is_confirmed():
            continue

        track_id = track.track_id
        l, t, w, h = map(int, track.to_ltrb())

        # Count only NEW IDs
        if track_id not in counted_ids:
            counted_ids.add(track_id)

        # Draw bounding box & ID
        cv2.rectangle(frame, (l, t), (l + w, t + h), (0, 255, 0), 2)
        cv2.putText(frame, f"ID {track_id}", (l, t - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Display people count
    cv2.putText(frame, f"People Count: {len(counted_ids)}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                (0, 0, 255), 2)

    return frame


# ---------------- VIDEO PROCESSING ----------------
def process_video(input_path, output_path):
    cap = cv2.VideoCapture(input_path)

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps,
                          (frame_width, frame_height))

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        output_frame = detect_track_and_count(frame)

        out.write(output_frame)
        cv2.imshow("YOLO + Deep SORT People Counting", output_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    out.release()
    cv2.destroyAllWindows()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    input_path = input("Enter video path: ")
    output_path = input("Enter output video path: ")
    process_video(input_path, output_path)
