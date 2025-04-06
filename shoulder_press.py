import cv2
import numpy as np
import mediapipe as mp
from collections import defaultdict
from models import db, UserExercise
import time
from flask import redirect, url_for


live_feedback = ''
def calculate_angle(a, b, c): #part assistance from ai
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0]) #
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle


def gen_frames(user_id, rep_goal):
    tut_start_time = None
    total_tut_score = 0
    #print(f"gen_frames called with user_id={user_id}, rep_goal={rep_goal}")
    global live_feedback
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Error: Camera could not be opened.")
        return

    mp_drawing = mp.solutions.drawing_utils
    mp_pose = mp.solutions.pose

    max_angle = None
    min_angle = None
    prev_angle = None
    direction = None
    repetition_count = 0
    ex_info = defaultdict(dict)
    exercise_id = 1

    total_rom_score = 0

    start_time = time.time()

    while True:
        success, frame = camera.read()
        if not success:
            print("Camera Fail")
            break

        elapsed_time = time.time() - start_time

        if elapsed_time < 5:
            remaining_time = 5 - int(elapsed_time)
            font_scale = 9
            font = cv2.FONT_HERSHEY_SIMPLEX
            thickness = 15

            text = str(remaining_time)
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = (frame.shape[0] + text_size[1]) // 2

            cv2.putText(frame, text, (text_x, text_y), font, font_scale, (0, 255, 0), thickness, cv2.LINE_AA)
            cv2.putText(frame, 'Get into starting position!!!', (185, 50),
                        cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        if elapsed_time >= 5:
            break

    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while True:
            success, frame = camera.read()
            if not success:
                print("Failed to read frame from camera.")
                break

            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            try:
                landmarks = results.pose_landmarks.landmark
                points = [mp_pose.PoseLandmark.RIGHT_HIP,
                          mp_pose.PoseLandmark.RIGHT_SHOULDER,
                          mp_pose.PoseLandmark.RIGHT_ELBOW]

                if points:
                    a = [landmarks[points[0].value].x, landmarks[points[0].value].y]
                    b = [landmarks[points[1].value].x, landmarks[points[1].value].y]
                    c = [landmarks[points[2].value].x, landmarks[points[2].value].y]
                    angle = calculate_angle(a, b, c)
                    color = (0, 255, 0) if 40 <= angle <= 140 else (0, 0, 255)

                    cv2.putText(image, str(int(angle)), tuple(np.multiply(b, [640, 480]).astype(int)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)

                    if angle > 125:
                        feedback = "Great Job!"
                    elif angle > 108:
                        feedback = "Little Higher"
                    elif angle < 40:
                        feedback = "Great Job!"
                    elif angle < 50:
                        feedback = "Go Lower"
                    else:
                        feedback = ""

                    if feedback:
                        cv2.putText(image, feedback, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2, cv2.LINE_AA)

                    rom_score = 0

                    if prev_angle is not None:
                        if angle > 120 and direction != "up":
                            max_angle = angle
                            direction = "up"
                            tut_start_time = time.time()  # Start timing the rep
                            print(f"Direction = UP. Max angle: {max_angle}")

                        elif angle < 50 and direction != "down":
                            if max_angle is not None:
                                repetition_count += 1
                                ex_info[repetition_count]['max'] = max_angle
                                ex_info[repetition_count]['min'] = angle

                                rep_rom_score = 0

                                if max_angle >= 122:
                                    rep_rom_score += 0.5
                                    print(f"Upper ROM: {rep_rom_score}")
                                else:
                                    print(f"Upper angle not reached: {max_angle}")

                                if angle <= 50:
                                    rep_rom_score += 0.5
                                    print(f"Lower ROM: {rep_rom_score}")
                                else:
                                    print(f"Lower angle not reached: {angle}")

                                total_rom_score += rep_rom_score
                                print(f"Rep ROM Score: {rep_rom_score}, Total ROM Score: {total_rom_score}")

                                if tut_start_time is not None:
                                    rep_tut_score = time.time() - tut_start_time  # Calculate the duration of the rep
                                    total_tut_score += rep_tut_score  # Accumulate the TUT
                                    print(f"Rep {repetition_count} TUT: {rep_tut_score:.2f} seconds")
                                    tut_start_time = None  # Reset the start time for the next rep


                                max_angle = None
                                direction = "down"
                                print("Direction reset to DOWN. ")
                            else:
                                print("max_angle is None")

                    prev_angle = angle
                    #mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)

                    cv2.putText(image, f'Rep {repetition_count}', (30, 150),
                                cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 0, 255), 2, cv2.LINE_AA)

                    if repetition_count >= rep_goal:
                        end_time = time.time() + 5

                        while time.time() < end_time:
                            success, frame = camera.read()
                            if not success:
                                print("Failed to read frame from camera.")
                                break

                            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            image.flags.writeable = False
                            results = pose.process(image)
                            image.flags.writeable = True
                            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                            cv2.putText(image, 'Great Job! '
                                               'Click the feedback button after page stops loading', (30, 200),
                                        cv2.FONT_HERSHEY_DUPLEX, 0.50, (0, 0, 255), 1, cv2.LINE_AA)

                            ret, buffer = cv2.imencode('.jpg', image)
                            frame = buffer.tobytes()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

                        try:
                            from app import app

                            with app.app_context():
                                print(user_id, rom_score)
                                new_exercise = UserExercise(
                                    user_id=user_id,
                                    exercise_id=exercise_id,
                                    total_reps=rep_goal,
                                    rom_score=total_rom_score,
                                    tut_score=total_tut_score,
                                    count=rep_goal
                                )
                                db.session.add(new_exercise)
                                db.session.commit()
                                print('data transferred!')


                                ex_info.clear()
                                repetition_count = 0
                                redirect_url = '/dash/'
                                return f'<html><head><meta http-equiv="refresh" content="0; url={redirect_url}" /></head><body></body></html>'
                        except Exception as e:
                            print(f"Error while appending to db: {e}")
                        finally:
                            break

            except Exception as e:
                print(f"Error during pose processing: {e}")

            ret, buffer = cv2.imencode('.jpg', image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    camera.release()






