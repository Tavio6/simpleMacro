import tkinter as tk
from tkinter import filedialog
from pynput import mouse, keyboard
import json
import threading
import time

def precise_sleep(delay):
    if delay <= 0:
        return
    target = time.perf_counter() + delay
    while True:
        remaining = target - time.perf_counter()
        if remaining <= 0:
            break
        time.sleep(min(remaining / 2, 0.001))

class MacroRecorder:
    def __init__(self):
        self.events = []
        self.recording = False
        self.replaying = False

    def record_mouse_move(self, x, y):
        if self.recording:
            self.events.append({
                "type": "mouse_move",
                "time": time.perf_counter(),
                "x": x,
                "y": y
            })

    def record_mouse(self, x, y, button, pressed):
        if self.recording:
            self.events.append({
                "type": "mouse_click",
                "time": time.perf_counter(),
                "x": x,
                "y": y,
                "button": str(button),
                "pressed": pressed
            })

    def record_keyboard(self, key, pressed):
        if self.recording:
            self.events.append({
                "type": "keyboard",
                "time": time.perf_counter(),
                "key": str(key),
                "pressed": pressed
            })

    def toggle_recording(self, update_ui):
        if self.recording:
            self.recording = False
            try:
                if hasattr(self, "mouse_listener"):
                    self.mouse_listener.stop()
                if hasattr(self, "keyboard_listener"):
                    self.keyboard_listener.stop()
            except Exception as e:
                print("Error stopping listeners:", e)
            update_ui(False, "Start Recording")
        else:
            self.recording = True
            self.events = []
            self.mouse_listener = mouse.Listener(
                on_move=self.record_mouse_move,
                on_click=self.record_mouse
            )
            self.keyboard_listener = keyboard.Listener(
                on_press=lambda key: self.record_keyboard(key, True),
                on_release=lambda key: self.record_keyboard(key, False)
            )
            self.mouse_listener.start()
            self.keyboard_listener.start()
            update_ui(True, "Stop Recording")

    def toggle_replaying(self, update_ui, repetitions=1, speed_multiplier=1.0):
        if self.replaying:
            self.replaying = False
            update_ui(False, "Start Replay")
        else:
            if not self.events:
                print("No events to replay.")
                return
            self.replaying = True
            threading.Thread(
                target=self.replay_events,
                args=(update_ui, repetitions, speed_multiplier),
                daemon=True
            ).start()
            update_ui(True, "Stop Replay")

    def replay_events(self, update_ui, repetitions, speed_multiplier):
        m_controller = mouse.Controller()
        k_controller = keyboard.Controller()

        for rep in range(repetitions):
            if not self.replaying:
                update_ui(False, "Start Replay")
                return

            base = self.events[0]["time"]
            previous_offset = 0

            for event in self.events:
                if not self.replaying:
                    update_ui(False, "Start Replay")
                    return

                current_offset = event["time"] - base
                delay = (current_offset - previous_offset) / speed_multiplier
                if delay > 0:
                    precise_sleep(delay)
                previous_offset = current_offset

                if event["type"] == "mouse_move":
                    m_controller.position = (event["x"], event["y"])
                elif event["type"] == "mouse_click":
                    button_str = event["button"]
                    if "Button.left" in button_str:
                        button_to_use = mouse.Button.left
                    elif "Button.right" in button_str:
                        button_to_use = mouse.Button.right
                    elif "Button.middle" in button_str:
                        button_to_use = mouse.Button.middle
                    else:
                        button_to_use = mouse.Button.left
                    m_controller.position = (event["x"], event["y"])
                    if event["pressed"]:
                        m_controller.press(button_to_use)
                    else:
                        m_controller.release(button_to_use)
                elif event["type"] == "keyboard":
                    key_str = event["key"]
                    if key_str.startswith("Key."):
                        key_attr = key_str.split('.')[1]
                        try:
                            key_value = getattr(keyboard.Key, key_attr)
                        except AttributeError:
                            continue
                    else:
                        key_value = key_str.strip("'\"")
                    if event["pressed"]:
                        k_controller.press(key_value)
                    else:
                        k_controller.release(key_value)

            if rep < repetitions - 1:
                time.sleep(0.5)

        self.replaying = False
        update_ui(False, "Start Replay")

    def save_events(self, filename):
        try:
            with open(filename, "w") as f:
                json.dump(self.events, f, indent=4)
            print(f"Events saved to {filename}")
        except Exception as e:
            print("Error saving events:", e)

    def load_events(self, filename):
        try:
            with open(filename, "r") as f:
                self.events = json.load(f)
            print(f"Events loaded from {filename}")
        except Exception as e:
            print("Error loading events:", e)

def build_ui():
    recorder = MacroRecorder()

    root = tk.Tk()
    root.title("Macro Recorder")
    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack()

    def update_recording_status(is_recording, text):
        root.after(0, lambda: recording_button.config(text=text))
        root.after(0, lambda: status_label.config(text="Recording..." if is_recording else "Idle"))

    def update_replay_status(is_replaying, text):
        root.after(0, lambda: replay_button.config(text=text))
        root.after(0, lambda: status_label.config(text="Replaying..." if is_replaying else "Idle"))

    def get_replay_count():
        try:
            count = int(replay_count_entry.get())
            return max(count, 1)
        except ValueError:
            return 1

    def get_speed_multiplier():
        try:
            speed = float(speed_entry.get())
            return max(speed, 0.1)
        except ValueError:
            return 1.0

    recording_button = tk.Button(
        frame, text="Start Recording", width=20,
        command=lambda: threading.Thread(
            target=recorder.toggle_recording,
            args=(update_recording_status,),
            daemon=True
        ).start()
    )
    recording_button.pack(pady=5)

    replay_button = tk.Button(
        frame, text="Start Replay", width=20,
        command=lambda: threading.Thread(
            target=recorder.toggle_replaying,
            args=(update_replay_status, get_replay_count(), get_speed_multiplier()),
            daemon=True
        ).start()
    )
    replay_button.pack(pady=5)

    replay_count_frame = tk.Frame(frame)
    replay_count_frame.pack(pady=5)
    tk.Label(replay_count_frame, text="Replay count:").pack(side=tk.LEFT)
    replay_count_entry = tk.Entry(replay_count_frame, width=5)
    replay_count_entry.insert(0, "1")
    replay_count_entry.pack(side=tk.LEFT, padx=5)

    speed_frame = tk.Frame(frame)
    speed_frame.pack(pady=5)
    tk.Label(speed_frame, text="Speed (e.g., 1.0 = normal):").pack(side=tk.LEFT)
    speed_entry = tk.Entry(speed_frame, width=5)
    speed_entry.insert(0, "1.0")
    speed_entry.pack(side=tk.LEFT, padx=5)

    def save_events_func():
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")]
        )
        if filename:
            recorder.save_events(filename)
            status_label.config(text=f"Saved to {filename}")

    def load_events_func():
        filename = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json")]
        )
        if filename:
            recorder.load_events(filename)
            status_label.config(text=f"Loaded from {filename}")

    tk.Button(frame, text="Save Events", width=20, command=save_events_func).pack(pady=5)
    tk.Button(frame, text="Load Events", width=20, command=load_events_func).pack(pady=5)

    status_label = tk.Label(frame, text="Idle")
    status_label.pack(pady=10)

    def hotkey_toggle_recording():
        root.after(0, lambda: threading.Thread(
            target=recorder.toggle_recording,
            args=(update_recording_status,),
            daemon=True
        ).start())

    def hotkey_toggle_replay():
        root.after(0, lambda: threading.Thread(
            target=recorder.toggle_replaying,
            args=(update_replay_status, get_replay_count(), get_speed_multiplier()),
            daemon=True
        ).start())

    hotkeys = keyboard.GlobalHotKeys({
        '<f6>': hotkey_toggle_recording,
        '<f7>': hotkey_toggle_replay
    })
    hotkeys.start()

    root.mainloop()

if __name__ == "__main__":
    build_ui()