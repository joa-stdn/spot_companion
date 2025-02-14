import os
import time
from extract_class_answer import process_question_attempts
from openai_client import OpenAIClient, speech_to_text, find_object_in_image
from together_client import TogetherClient

from constants import OBJ_CLASSES

# Attempt to import SpotController, set flag if not available
try:
    from spot_controller import SpotController

    local_laptop = False
except ImportError:
    local_laptop = True
print(f"Local laptop: {local_laptop}")
from gtts import gTTS
import cv2
from typing import Callable, Any

ROBOT_IP = "10.0.0.3"  # os.environ['ROBOT_IP']
SPOT_USERNAME = "admin"  # os.environ['SPOT_USERNAME']
SPOT_PASSWORD = "2zqa8dgw7lor"  # os.environ['SPOT_PASSWORD']


# Wrapper class
class SpotControllerWrapper:
    def __init__(self, *args, **kwargs):
        if not local_laptop:
            self.spot = SpotController(*args, **kwargs)

    def __getattr__(self, name):
        """If local_laptop is True, replace SpotController methods with no-op.
        Otherwise, return method from SpotController."""
        if local_laptop:

            def method(*args, **kwargs):
                print(f"Skipping {name} due to local execution.")

            return method
        else:
            return getattr(self.spot, name)

    def __enter__(self):
        if not local_laptop:
            return self.spot.__enter__()
        return self  # Return self to work with context manager syntax

    def __exit__(self, exc_type, exc_value, traceback):
        if not local_laptop:
            return self.spot.__exit__(exc_type, exc_value, traceback)


if local_laptop:
    SpotClass = SpotControllerWrapper
else:
    SpotClass = SpotController

ROBOT_IP = "10.0.0.3"  # os.environ['ROBOT_IP']
SPOT_USERNAME = "admin"  # os.environ['SPOT_USERNAME']
SPOT_PASSWORD = "2zqa8dgw7lor"  # os.environ['SPOT_PASSWORD']


def say_something(text: str, file_name: str = "welcome.mp3"):
    print(f"Say something")
    print(f"\t- Saying: {text}")
    myobj = gTTS(text=text, lang="en", slow=False)
    myobj.save(file_name)
    # Play loud audio
    # Amplify audio
    os.system(f"ffmpeg -i {file_name} -filter:a 'volume=2.0' temp_{file_name} -y")
    # Play amplified audio
    os.system(f"ffplay -nodisp -autoexit -loglevel quiet temp_{file_name}")
    print(f"\t- Done saying something")


def nod_head(x: int, spot: SpotControllerWrapper):
    print(f"Nodding head {x} times")
    # Nod head x times
    for _ in range(x):
        print(f"\t- Moving head up")
        spot.move_head_in_points(
            yaws=[0, 0], pitches=[0.18, 0], rolls=[0, 0], sleep_after_point_reached=0
        )
        print(f"\t- Moving head down")
        spot.move_head_in_points(
            yaws=[0, 0], pitches=[-0.1, 0], rolls=[0, 0], sleep_after_point_reached=0
        )
    # Reset head position
    print(f"\t- Resetting head position")
    spot.move_head_in_points(
        yaws=[0, 0], pitches=[0, 0], rolls=[0, 0], sleep_after_point_reached=0
    )
    print(f"\t- Done nodding head")


def detect_object(
    spot: SpotControllerWrapper,
    camera_capture: cv2.VideoCapture,
    obj_class: str,
):
    for _ in range(10):
        frame = camera_capture.read()[1]
    return 1 if find_object_in_image(frame, obj_class) else 0


def rotate_and_run_function(
    spot: SpotControllerWrapper,
    function: Callable[[SpotControllerWrapper, Any], int],
    every_n_milliseconds: int,
    rotation_speed: float,
    n_rotations: int,
    **kwargs,
) -> bool:
    """Rotate the robot for n_rotations and run the function every_n_milliseconds

    Args:
        spot (SpotController): SpotController object
        function (Callable[[SpotController, Any], int]): Function to run
            This function should return 1 if the robot should stop
        every_n_milliseconds (int): Run function every n milliseconds
        rotation_speed (float): Rotation speed in rad/s
        n_rotations (int): Number of rotations

    Returns:
        int: The result of the function
    """
    duration: int = n_rotations * 2 * 3.14 / abs(rotation_speed)
    print(f"Rotate and run function")
    print(f"\t- Rotating for {n_rotations} rotations during {duration} seconds")
    print(f"\t- Going to execute function every {every_n_milliseconds} milliseconds")
    result: int = 0
    start_time = time.time()
    last_command_time_ms = start_time * 1000 - every_n_milliseconds
    delay = 0
    while time.time() - start_time < duration:
        spot.move_by_velocity_control(
            v_x=0,
            v_y=0,
            v_rot=rotation_speed,
            cmd_duration=2,
        )
        start_exec_time = time.time()
        if (time.time() * 1000 - last_command_time_ms) >= every_n_milliseconds:
            last_command_time_ms = time.time() * 1000
            result: int = function(spot, **kwargs)
            if result == 1:
                print("\t- Function returned 1, stopping")
                delay = time.time() - start_exec_time
                break
    print("\t- Stopping")
    spot.move_by_velocity_control(
        v_x=0,
        v_y=0,
        v_rot=0,
        cmd_duration=0.1,
    )
    print("\t- Done rotating and running function")
    return result == 1, delay


def record_audio(sample_name: str = "recording.wav", duration: int = 7) -> str:
    print("Recording audio")
    if local_laptop:
        cmd = (
            f"arecord -vv --format=cd -r 48000 --duration={duration} -c 1 {sample_name}"
        )
    else:
        cmd = f'arecord -vv --format=cd --device={os.environ["AUDIO_INPUT_DEVICE"]} -r 48000 --duration={duration} -c 1 {sample_name}'
    print(f"\t- Running command: {cmd}")
    os.system(cmd)
    print(f"\t- Done recording audio")
    result = speech_to_text(sample_name)
    print(f"\t- Transcribed audio: {result}")
    return result


def main():
    # Capture image
    camera_capture = cv2.VideoCapture(0)

    say_something("Booting up the robot")
    # Load the Haar Cascade for face detection
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    # client = TogetherClient(
    #     model_name="mistralai/Mistral-7B-Instruct-v0.2",
    #     api_key=os.environ.get("TOGETHER_API_KEY"),
    # )
    client = OpenAIClient(
        model_name="gpt-4-1106-preview", api_key=os.environ.get("OPENAI_API_KEY")
    )

    def detect_faces(
        spot: SpotControllerWrapper, camera_capture: cv2.VideoCapture
    ) -> int:
        # Convert the frame to grayscale for the Haar Cascade detector
        frame = camera_capture.read()[1]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        return len(faces) > 0

    # Use wrapper in context manager to lease control, turn on E-Stop, power on the robot and stand up at start
    # and to return lease + sit down at the end
    with SpotClass(
        username=SPOT_USERNAME, password=SPOT_PASSWORD, robot_ip=ROBOT_IP
    ) as spot:
        # Start
        nod_head(1, spot)
        say_something("Hi, I am spot, how are you doing today? Where are you?")

        # Rotate and run function
        success, delay = rotate_and_run_function(
            spot=spot,
            function=detect_faces,
            every_n_milliseconds=200,
            rotation_speed=-0.5,
            n_rotations=2,
            camera_capture=camera_capture,
        )
        if success:
            say_something("Oh, here you are, it's nice to see you!")
        else:
            say_something("It seems like no one is here. I will lay down for now.")
        time.sleep(1)

        # Ask for help
        start_time = time.time()
        say_something("How can I help you today?")
        while time.time() - start_time < 60:
            question: str = record_audio()
            dict_output = process_question_attempts(
                OBJ_CLASSES, question, num_attempts=2, client=client
            )
            say_something(dict_output["answer"])

            if (
                dict_output.get("object_class_to_find", None) is not None
                and dict_output["object_class_to_find"] != ""
            ):
                class_: str = dict_output["object_class_to_find"]
                say_something(f"Let me find your {class_}.")

                # Look for the object
                ROTATION_SPEED = 0.15
                success, delay = rotate_and_run_function(
                    spot=spot,
                    function=detect_object,
                    every_n_milliseconds=200,
                    rotation_speed=ROTATION_SPEED,
                    n_rotations=2,
                    camera_capture=camera_capture,
                    obj_class=class_,
                )

                if success:
                    spot.move_by_velocity_control(
                        v_x=0,
                        v_y=0,
                        v_rot=-ROTATION_SPEED,
                        cmd_duration=delay,
                    )
                    spot.move_to_goal(goal_x=0.25, goal_y=0)
                    time.sleep(1)
                    say_something(f"Here is your {class_}. Look at where I am nodding.")
                    nod_head(2, spot)
                    say_something(
                        f"Be careful, it might be hot! Let me know if you need anything else."
                    )
                    break
                else:
                    say_something(f"I am sorry, but I could not find your {class_}.")
            else:
                pass  # say_something("Can you please rephrase your question?")

    camera_capture.release()


if __name__ == "__main__":
    main()
