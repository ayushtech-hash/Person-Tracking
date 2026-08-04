import cv2
from tkinter import Tk, filedialog

# Hide the Tkinter root window
root = Tk()
root.withdraw()

# Open file picker
video_path = filedialog.askopenfilename(
    title="Select a Video",
    filetypes=[
        ("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
        ("All Files", "*.*")
    ]
)

if not video_path:
    print("No video selected.")
    exit()

# Open the video
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error opening video.")
    exit()

print("Press 'q' to quit.")

while True:
    ret, frame = cap.read()

    if not ret:
        break

    cv2.imshow("Video Player", frame)

    # Press q to exit
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()