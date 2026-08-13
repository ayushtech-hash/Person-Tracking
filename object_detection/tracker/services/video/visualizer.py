import cv2

class Visualizer:
    """
    Responsible for drawing annotations on video frames.
    """

    @staticmethod
    def draw_detections(frame, detections):
        """
        Draw person detections on a frame.
        """ 

        for det in detections:

            x1, y1, x2, y2 = map(int, det.bbox)

            if det.confidence > 0.6:
                color = (0, 255, 0)
                thickness = 10

            else:
                color = (0, 0, 255)
                thickness = 10

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                thickness,
            )

            label = f"{det.confidence:.2f}"

            cv2.putText(
                frame,
                label,
                (x1, max(50, y1 - 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                3.5,
                color,
                thickness,
            )

        return frame


    @staticmethod
    def draw_tracks(frame, tracked_detections,selected_track_id=None):
        """
        TRACK person detections on a frame.
        """

        for det in tracked_detections:

            x1, y1, x2, y2 = map(int, det.bbox)

            # Default style
            color = (255, 0, 0)
            thickness = 8

            # Highlight selected person
            if (
                selected_track_id is not None
                and det.track_id == selected_track_id
            ):
                color = (0, 255, 0)
                thickness = 10

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                color,
                thickness,
            )

            label = f"ID {det.track_id}"


            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                3.5,
                color,
                2,
            )

        return frame