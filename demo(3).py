from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("yolov8n.pt")

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run detection
    results = model(frame)

    person_count = 0

    # Loop through detected objects
    for r in results:
        for box in r.boxes:
            cls = int(box.cls[0])
            if cls == 0:  # 0 means 'person'
                person_count += 1

    # Show count on screen
    cv2.putText(frame, f"People Count: {person_count}",
                (30, 50), cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 255, 0), 2)

    cv2.imshow("Demo 3 - People Counter", frame)

    if cv2.waitKey(1) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
