import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import json
import subprocess
import sys
import shutil # Added for cleanup on close
from vosk import Model, KaldiRecognizer, SetLogLevel
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

# --- Constants ---
DEFAULT_MODEL_DIR = "" # Optional: Set a default model path if desired
DEFAULT_OUTPUT_DIR = os.getcwd() # Default to current working directory
REQUIRED_SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = 8000 # Increased chunk size for potentially better performance
TEMP_DIR_NAME = "temp_audio_conversion" # Name for the temporary directory

# --- Audio Conversion ---

def get_ffmpeg_path():
    """Tries to find the ffmpeg executable."""
    # Check common locations or PATH environment variable
    ffmpeg_cmd = "ffmpeg"
    try:
        # Check if ffmpeg is in PATH
        # Use CREATE_NO_WINDOW flag on Windows to prevent console popup
        startupinfo = None
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        subprocess.run(
            [ffmpeg_cmd, "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo # Pass startupinfo for Windows
        )
        print("FFmpeg found in PATH.")
        return ffmpeg_cmd
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("FFmpeg not found in PATH, checking common locations...")
        # Try common install paths (add more if needed for your system)
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe", # Example Windows path 1
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe", # Example Windows path 2
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe", # Example Windows path 3
            "/usr/bin/ffmpeg",          # Example Linux path
            "/usr/local/bin/ffmpeg",    # Example macOS/Linux path
            "/opt/homebrew/bin/ffmpeg" # Example macOS (Apple Silicon) path
        ]
        for path in common_paths:
            if os.path.exists(path):
                 try:
                     # Verify it's runnable
                     startupinfo = None
                     if sys.platform == 'win32':
                         startupinfo = subprocess.STARTUPINFO()
                         startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                         startupinfo.wShowWindow = subprocess.SW_HIDE

                     subprocess.run(
                         [path, "-version"],
                         check=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         startupinfo=startupinfo # Pass startupinfo for Windows
                     )
                     print(f"FFmpeg found at: {path}")
                     return path
                 except (subprocess.CalledProcessError, FileNotFoundError, PermissionError):
                     print(f"Found path {path}, but couldn't run 'ffmpeg -version'. Skipping.")
                     continue
        print("FFmpeg executable not found in PATH or common locations.")
        return None # Not found

def convert_audio_if_needed(input_path, temp_dir):
    """
    Converts audio to WAV, 16kHz mono if necessary using pydub.
    Returns the path to the compatible WAV file or raises an error.
    """
    # Ensure ffmpeg is available for pydub - pydub needs the *directory* containing ffmpeg
    ffmpeg_executable_path = get_ffmpeg_path()
    if not ffmpeg_executable_path:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH, or add its location to the 'common_paths' list in the 'get_ffmpeg_path' function.")

    # pydub uses AudioSegment.converter which should point to the ffmpeg *executable*
    AudioSegment.converter = ffmpeg_executable_path
    print(f"Using FFmpeg converter at: {AudioSegment.converter}")
    # Optional: If you also have ffprobe, set its path too (often in the same dir)
    # ffprobe_path = os.path.join(os.path.dirname(ffmpeg_executable_path), "ffprobe.exe" if sys.platform == "win32" else "ffprobe")
    # if os.path.exists(ffprobe_path):
    #    AudioSegment.ffprobe = ffprobe_path
    #    print(f"Using FFprobe at: {AudioSegment.ffprobe}")


    try:
        # Load audio file using pydub
        print(f"Attempting to load audio file: {input_path}")
        audio = AudioSegment.from_file(input_path)
        print(f"Successfully loaded audio. Original format: Channels={audio.channels}, Frame Rate={audio.frame_rate}Hz, Sample Width={audio.sample_width} bytes")

        # Check if conversion is needed
        is_compatible = (
            audio.frame_rate == REQUIRED_SAMPLE_RATE and
            audio.channels == 1
            # We will export as WAV regardless to ensure compatibility,
            # so no need to check input_path extension here.
        )

        if is_compatible:
            print(f"Audio '{os.path.basename(input_path)}' has compatible rate and channels.")
            # Even if compatible, export to a temporary WAV to ensure format consistency
            # This avoids potential issues with formats Vosk might not handle directly via file reading.
            # Fall through to the export step.
            pass
        else:
             print(f"Audio requires conversion: Rate={audio.frame_rate}Hz (need {REQUIRED_SAMPLE_RATE}Hz), Channels={audio.channels} (need 1)")

        # Create a predictable temporary file path inside the temp_dir
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        # Sanitize basename slightly for filesystem safety (optional)
        safe_base_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        output_wav_path = os.path.join(temp_dir, f"{safe_base_name}_converted_{os.getpid()}.wav") # Add PID for uniqueness

        print(f"Preparing to export to temporary WAV: '{output_wav_path}'")
        # Perform conversion (or re-export if already compatible)
        audio = audio.set_frame_rate(REQUIRED_SAMPLE_RATE)
        audio = audio.set_channels(1)

        # Export as WAV
        audio.export(output_wav_path, format='wav')
        print(f"Successfully exported temporary WAV file.")
        return output_wav_path

    except CouldntDecodeError as e:
        print(f"Pydub/FFmpeg decode error: {e}")
        raise ValueError(f"Could not decode audio file: {os.path.basename(input_path)}. Ensure it's a valid audio format and FFmpeg is correctly installed and accessible. Original error: {e}")
    except FileNotFoundError as e:
        # This might happen if the input file disappears between selection and processing
        print(f"File not found during conversion: {e}")
        raise FileNotFoundError(f"Input audio file not found: {input_path}")
    except Exception as e:
        # Catch other potential errors during pydub processing
        print(f"Unexpected error during audio conversion: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
        raise RuntimeError(f"Error during audio conversion: {e}")


# --- Transcription Logic ---

def transcribe_audio(audio_path, model_path, output_txt_path, progress_callback):
    """
    Transcribes the given audio file using the specified Vosk model.

    Args:
        audio_path (str): Path to the compatible WAV audio file (16kHz, mono).
        model_path (str): Path to the Vosk model directory.
        output_txt_path (str): Path to save the transcription text file.
        progress_callback (function): Function to call with progress updates (e.g., partial text).
    """
    try:
        # --- Model Loading ---
        progress_callback("Loading Vosk model...")
        print(f"Attempting to load Vosk model from: {model_path}")
        if not os.path.exists(model_path) or not os.path.isdir(model_path):
            raise FileNotFoundError(f"Model directory not found or is not a directory: {model_path}")

        # Suppress excessive Vosk logging (0=normal, -1=suppress)
        SetLogLevel(0) # Set to 0 initially to see model loading messages, then maybe -1 later
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, REQUIRED_SAMPLE_RATE)
        recognizer.SetWords(True) # Enable word timestamps (optional, adds detail to JSON)
        # recognizer.SetPartialWords(True) # Enable partial words (optional)
        SetLogLevel(-1) # Suppress logs after successful load

        progress_callback("Model loaded successfully. Starting transcription...")
        print("Model loaded. Starting transcription...")

        full_transcript = []
        total_bytes_read = 0

        # --- Audio Processing ---
        print(f"Opening converted audio file for reading: {audio_path}")
        with open(audio_path, 'rb') as wf:
            while True:
                data = wf.read(AUDIO_CHUNK_SIZE)
                total_bytes_read += len(data)
                if len(data) == 0:
                    print("End of audio file reached.")
                    break

                # Feed data to the recognizer
                if recognizer.AcceptWaveform(data):
                    # Segment complete, get result
                    result_json_str = recognizer.Result()
                    # print(f"Vosk Result JSON: {result_json_str}") # Debugging
                    result = json.loads(result_json_str)
                    text = result.get('text', '')
                    if text:
                        full_transcript.append(text)
                        progress_callback(f"Segment: ...{text[-60:]}") # Show tail end of the segment
                        print(f"Result segment: {text}") # Log full result segment
                else:
                    # Get partial result
                    partial_result_json_str = recognizer.PartialResult()
                    # print(f"Vosk Partial JSON: {partial_result_json_str}") # Debugging
                    partial_result = json.loads(partial_result_json_str)
                    partial_text = partial_result.get('partial', '')
                    if partial_text:
                        progress_callback(f"Partial: ...{partial_text[-60:]}") # Show tail end
                        # print(f"Partial: {partial_text}", end='\r') # Option to print partial to console

            print(f"Finished processing audio stream. Total bytes read: {total_bytes_read}")
            # --- Final Result ---
            final_result_json_str = recognizer.FinalResult()
            print(f"Vosk Final JSON: {final_result_json_str}") # Debugging
            final_result = json.loads(final_result_json_str)
            final_text = final_result.get('text', '')
            if final_text:
                full_transcript.append(final_text)
                print(f"Final segment result: {final_text}")

        # --- Save Transcription ---
        final_transcript_text = " ".join(full_transcript).strip()

        if not final_transcript_text:
             progress_callback("Transcription complete. No text detected in the audio.")
             print("Transcription complete. No text detected.")
             # Optionally delete the empty output file or leave it
             # if os.path.exists(output_txt_path):
             #     try:
             #         os.remove(output_txt_path)
             #     except OSError as e:
             #         print(f"Could not remove empty output file: {e}")
             return # Don't save empty file

        print(f"Saving transcription to: {output_txt_path}")
        try:
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write(final_transcript_text)
            progress_callback(f"Transcription complete! Saved to:\n{output_txt_path}")
            print(f"Transcription saved successfully.")
        except IOError as e:
             print(f"Error saving transcription file: {e}")
             progress_callback(f"Error: Could not write to output file:\n{output_txt_path}")
             raise # Re-raise for GUI handling


    except FileNotFoundError as e:
        # Specifically for model path error during loading
        print(f"Error: {e}")
        progress_callback(f"Error: {e}")
        raise # Re-raise for GUI handling
    except Exception as e:
        # Catch other Vosk or file errors
        print(f"An unexpected error occurred during transcription: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging
        progress_callback(f"Error during transcription: {e}")
        raise # Re-raise for GUI handling

# --- GUI Application ---

class TranscriberApp:
    def __init__(self, master):
        self.master = master
        master.title("Vosk Audio Transcriber")
        master.geometry("650x500") # Slightly larger window

        # --- Member Variables ---
        self.input_file_path = tk.StringVar()
        self.model_dir_path = tk.StringVar(value=DEFAULT_MODEL_DIR)
        self.output_file_path = tk.StringVar()
        # Create temp dir in user's temp folder for better practice
        self.temp_dir = os.path.join(os.path.expanduser("~"), TEMP_DIR_NAME)
        self.transcription_thread = None # To hold the thread object

        # --- Ensure Temp Directory Exists ---
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"Temporary directory set to: {self.temp_dir}")
        except OSError as e:
            messagebox.showerror("Error", f"Could not create temporary directory:\n{self.temp_dir}\nError: {e}")
            # Decide how to handle this - maybe disable transcription?
            # For now, we'll let it proceed, conversion might fail later.
            print(f"ERROR: Failed to create temp directory {self.temp_dir}: {e}")


        # --- Styling ---
        label_font = ("Helvetica", 10)
        button_font = ("Helvetica", 10, "bold")
        entry_font = ("Helvetica", 10)
        status_font = ("Helvetica", 9, "italic") # Italic for status
        status_area_font = ("Courier New", 9) # Monospaced for status log

        # --- GUI Layout (using grid) ---

        # Input File Row
        tk.Label(master, text="Input Audio File:", font=label_font).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.input_entry = tk.Entry(master, textvariable=self.input_file_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.input_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        tk.Button(master, text="Browse...", command=self.browse_input_file, font=button_font, width=10).grid(row=0, column=2, padx=10, pady=8)

        # Model Directory Row
        tk.Label(master, text="Vosk Model Dir:", font=label_font).grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.model_entry = tk.Entry(master, textvariable=self.model_dir_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.model_entry.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
        tk.Button(master, text="Browse...", command=self.browse_model_dir, font=button_font, width=10).grid(row=1, column=2, padx=10, pady=8)

        # Output File Row
        tk.Label(master, text="Output Text File:", font=label_font).grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.output_entry = tk.Entry(master, textvariable=self.output_file_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.output_entry.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
        tk.Button(master, text="Set Output...", command=self.set_output_file, font=button_font, width=10).grid(row=2, column=2, padx=10, pady=8)

        # Transcribe Button Row
        self.transcribe_button = tk.Button(master, text="Transcribe", command=self.start_transcription_thread, font=button_font, bg="#4CAF50", fg="white", relief=tk.RAISED, borderwidth=2, width=15, height=2)
        self.transcribe_button.grid(row=3, column=0, columnspan=3, padx=10, pady=20)

        # Status Label Row
        tk.Label(master, text="Status Log:", font=status_font).grid(row=4, column=0, padx=10, pady=(10, 0), sticky="nw")

        # Status Area Row
        self.status_text = scrolledtext.ScrolledText(master, height=12, width=80, wrap=tk.WORD, font=status_area_font, state='disabled', relief=tk.SUNKEN, borderwidth=1)
        self.status_text.grid(row=5, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="nsew")

        # --- Configure Grid Resizing ---
        master.grid_columnconfigure(1, weight=1) # Allow entry fields column to expand horizontally
        master.grid_rowconfigure(5, weight=1) # Allow status area row to expand vertically

        # --- Set Initial State ---
        self.set_default_output_path()
        self.update_status("Ready. Please select an audio file and Vosk model.")


    def browse_input_file(self):
        """Opens a dialog to select the input audio file."""
        # More comprehensive list of common audio types FFmpeg usually handles
        filetypes = (
            ("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus *.wma *.aiff *.aif *.wv *.mpc *.ape *.amr *.au *.dat *.unknown"),
            ("All files", "*.*")
        )
        # Remember the last directory opened for convenience
        last_dir = os.path.dirname(self.input_file_path.get()) if self.input_file_path.get() else DEFAULT_OUTPUT_DIR
        filepath = filedialog.askopenfilename(
            title="Select Input Audio File",
            initialdir=last_dir,
            filetypes=filetypes
        )
        if filepath:
            self.input_file_path.set(filepath)
            # Automatically suggest an output path based on the new input
            self.set_default_output_path(filepath, force_update=True)
            self.update_status(f"Selected input: {os.path.basename(filepath)}")

    def browse_model_dir(self):
        """Opens a dialog to select the Vosk model directory."""
        # Remember the last directory opened
        last_dir = self.model_dir_path.get() if self.model_dir_path.get() else DEFAULT_MODEL_DIR
        dirpath = filedialog.askdirectory(
            title="Select Vosk Model Directory (e.g., 'vosk-model-en-us-0.22')",
            initialdir=last_dir
            )
        if dirpath:
            # Perform a more robust check for a valid Vosk model structure
            required_files = [
                os.path.join(dirpath, "am", "final.mdl"),
                os.path.join(dirpath, "conf", "model.conf"),
                os.path.join(dirpath, "graph", "HCLG.fst"), # Check for graph too
                os.path.join(dirpath, "graph", "words.txt")
            ]
            missing_files = [f for f in required_files if not os.path.exists(f)]

            if not missing_files:
                self.model_dir_path.set(dirpath)
                self.update_status(f"Selected model: {os.path.basename(dirpath)}")
            else:
                missing_str = "\n - ".join([os.path.basename(m) for m in missing_files])
                messagebox.showwarning("Invalid Model Directory",
                                       f"The selected directory:\n{dirpath}\n\n"
                                       f"Appears to be missing required Vosk model files:\n - {missing_str}\n\n"
                                       "Please select the folder containing 'am', 'conf', 'graph' subdirectories.")
                self.model_dir_path.set("") # Clear invalid path


    def set_output_file(self):
        """Opens a dialog to set the output text file path."""
        # Suggest a filename based on input, but let user change it
        initial_filename = "transcription.txt" # Default if no input selected yet
        input_path = self.input_file_path.get()
        if input_path:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            initial_filename = f"{base_name}_transcription.txt"

        # Remember the last directory used for output
        last_dir = os.path.dirname(self.output_file_path.get()) if self.output_file_path.get() else DEFAULT_OUTPUT_DIR

        filepath = filedialog.asksaveasfilename(
            title="Save Transcription As",
            defaultextension=".txt",
            initialfile=initial_filename,
            initialdir=last_dir,
            filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
        )
        if filepath:
            self.output_file_path.set(filepath)
            self.update_status(f"Set output file: {os.path.basename(filepath)}")

    def set_default_output_path(self, input_filepath=None, force_update=False):
        """Sets a default output path based on input file or CWD."""
        # Only set if not already set by user OR if force_update is True
        if force_update or not self.output_file_path.get():
             output_dir = DEFAULT_OUTPUT_DIR
             filename = "transcription.txt"
             if input_filepath:
                 base_name = os.path.splitext(os.path.basename(input_filepath))[0]
                 filename = f"{base_name}_transcription.txt"
                 # Try to use the same directory as the input file for the default output
                 input_dir = os.path.dirname(input_filepath)
                 if input_dir and os.path.isdir(input_dir):
                     output_dir = input_dir

             default_output = os.path.join(output_dir, filename)
             self.output_file_path.set(default_output)
             # Don't log status here, it's called initially and on input change


    def update_status(self, message):
        """Updates the status text area in a thread-safe way."""
        # Ensure this runs on the main Tkinter thread
        def _update():
            self.status_text.config(state='normal')
            self.status_text.insert(tk.END, message + "\n")
            self.status_text.see(tk.END) # Scroll to the bottom
            self.status_text.config(state='disabled')
        # Schedule the update to run in the main event loop
        self.master.after(0, _update)


    def transcription_task(self):
        """The actual workhorse function run in a separate thread."""
        input_file = self.input_file_path.get()
        model_dir = self.model_dir_path.get()
        output_file = self.output_file_path.get()

        # --- Pre-flight Checks (already done in GUI, but good practice) ---
        if not all([input_file, model_dir, output_file]):
            # This case should ideally not be reached due to GUI validation
            self.update_status("ERROR: Missing input, model, or output path.")
            self.enable_controls()
            return

        self.clear_status()
        self.update_status(f"Starting Transcription Process...")
        self.update_status(f"Input: {os.path.basename(input_file)}")
        self.update_status(f"Model: {os.path.basename(model_dir)}")
        self.update_status(f"Output: {os.path.basename(output_file)}")
        self.update_status("-" * 30)

        converted_audio_path = None # To track converted file for cleanup
        try:
            # --- Step 1: Conversion ---
            self.update_status("Step 1: Checking audio format & converting if needed...")
            converted_audio_path = convert_audio_if_needed(input_file, self.temp_dir)
            self.update_status(f"Using audio file for transcription: {os.path.basename(converted_audio_path)}")

            # --- Step 2: Transcription ---
            self.update_status("Step 2: Starting Vosk transcription...")
            transcribe_audio(converted_audio_path, model_dir, output_file, self.update_status)
            # Final success message is handled within transcribe_audio

        except (ValueError, RuntimeError, FileNotFoundError) as e:
            # Catch errors from conversion or transcription setup
            error_msg = f"ERROR: {e}"
            print(error_msg) # Log error to console too
            self.update_status(error_msg)
            # Show a popup for critical errors
            self.master.after(0, lambda: messagebox.showerror("Transcription Error", f"An error occurred:\n{e}"))
        except Exception as e:
            # Catch unexpected errors
            error_msg = f"UNEXPECTED ERROR: {e}"
            print(error_msg)
            import traceback
            traceback.print_exc() # Print detailed traceback
            self.update_status(error_msg)
            self.master.after(0, lambda: messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n{e}"))
        finally:
            # --- Step 3: Cleanup and Re-enable ---
            self.update_status("-" * 30)
            # Clean up temporary converted file if it was created and exists
            if converted_audio_path and converted_audio_path != input_file and os.path.exists(converted_audio_path):
                 try:
                     os.remove(converted_audio_path)
                     print(f"Cleaned up temporary file: {converted_audio_path}")
                     self.update_status(f"Cleaned up temp file: {os.path.basename(converted_audio_path)}")
                 except OSError as e:
                     print(f"Warning: Could not remove temporary file {converted_audio_path}: {e}")
                     self.update_status(f"Warning: Could not remove temp file: {os.path.basename(converted_audio_path)}")
            else:
                 self.update_status("No temporary conversion file to clean up.")

            self.enable_controls() # Re-enable button regardless of success/failure
            self.update_status("Process finished.")


    def start_transcription_thread(self):
        """Starts the transcription process in a new thread if inputs are valid."""
        input_file = self.input_file_path.get()
        model_dir = self.model_dir_path.get()
        output_file = self.output_file_path.get()

        # --- Validation ---
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Input Error", "Please select a valid input audio file.")
            return
        if not model_dir or not os.path.isdir(model_dir): # Check if it's a directory
            messagebox.showerror("Input Error", "Please select a valid Vosk model directory.")
            return
        # Check model validity again just before starting
        required_files = [
            os.path.join(model_dir, "am", "final.mdl"),
            os.path.join(model_dir, "conf", "model.conf")
        ]
        if not all(os.path.exists(f) for f in required_files):
             messagebox.showerror("Input Error", "The selected Vosk model directory seems invalid or incomplete.")
             return

        if not output_file:
            messagebox.showerror("Input Error", "Please set an output text file path using 'Set Output...'.")
            return
        # Check if output directory exists (asksaveasfilename usually handles file creation)
        output_dir = os.path.dirname(output_file)
        if not os.path.isdir(output_dir):
             messagebox.showerror("Output Error", f"The directory for the output file does not exist:\n{output_dir}")
             return


        # --- Disable Controls and Start Thread ---
        self.disable_controls()
        # Create and start the thread
        # Use daemon=True so thread exits if main app closes unexpectedly
        self.transcription_thread = threading.Thread(target=self.transcription_task, daemon=True)
        self.transcription_thread.start()

    def disable_controls(self):
        """Disables buttons and entries during processing."""
        self.transcribe_button.config(state=tk.DISABLED, text="Transcribing...")
        # Disable browse/set buttons as well
        for widget in self.master.winfo_children():
            if isinstance(widget, tk.Button) and widget != self.transcribe_button:
                widget.config(state=tk.DISABLED)
            # Optionally disable entry fields too, though they are readonly
            # if isinstance(widget, tk.Entry):
            #     widget.config(state='disabled') # Use 'disabled' instead of 'readonly' state

    def enable_controls(self):
        """Re-enables controls after processing."""
        def _enable():
            self.transcribe_button.config(state=tk.NORMAL, text="Transcribe")
            # Re-enable browse/set buttons
            for widget in self.master.winfo_children():
                if isinstance(widget, tk.Button) and widget != self.transcribe_button:
                    widget.config(state=tk.NORMAL)
                # Re-enable entry fields if they were disabled
                # if isinstance(widget, tk.Entry):
                #     widget.config(state='readonly') # Back to readonly state
        self.master.after(0, _enable) # Schedule enabling in the main thread


    def clear_status(self):
        """Clears the status text area."""
        def _clear():
            self.status_text.config(state='normal')
            self.status_text.delete('1.0', tk.END)
            self.status_text.config(state='disabled')
        self.master.after(0, _clear) # Schedule clearing in the main thread

    def on_closing(self):
        """Handle window closing: clean up temp directory."""
        print("Close button clicked.")
        if messagebox.askokcancel("Quit", "Do you want to quit?\nTemporary conversion files will be deleted."):
            print("Quitting application.")
            try:
                # Attempt to remove the temp directory and its contents
                if os.path.exists(self.temp_dir):
                    print(f"Attempting to remove temporary directory: {self.temp_dir}")
                    shutil.rmtree(self.temp_dir)
                    print(f"Successfully removed temporary directory.")
                else:
                    print("Temporary directory does not exist, no cleanup needed.")
            except Exception as e:
                # Log error but don't prevent closing
                print(f"Warning: Could not remove temporary directory {self.temp_dir}: {e}")
                messagebox.showwarning("Cleanup Warning", f"Could not automatically remove the temporary directory:\n{self.temp_dir}\n\nYou may need to delete it manually.\nError: {e}")
            # Destroy the Tkinter window
            self.master.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    # Set up the main Tkinter window
    root = tk.Tk()
    # Create the application instance
    app = TranscriberApp(root)
    # Set the action for the window close button
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    # Start the Tkinter event loop
    root.mainloop()
