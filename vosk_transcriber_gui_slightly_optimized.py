# Optimized version of input_file_0.py
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import os
import json
import subprocess
import sys
import shutil # Added for cleanup on close
import traceback # For detailed error printing

# --- Vosk and Pydub ---
# Attempt imports and provide guidance if missing
try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
except ImportError:
    print("ERROR: vosk library not found. Please install it: pip install vosk")
    sys.exit(1)
try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError
except ImportError:
    print("ERROR: pydub library not found. Please install it: pip install pydub")
    sys.exit(1)

# --- Constants ---
DEFAULT_MODEL_DIR = "" # Optional: Set a default model path if desired
DEFAULT_OUTPUT_DIR = os.getcwd() # Default to current working directory
REQUIRED_SAMPLE_RATE = 16000
AUDIO_CHUNK_SIZE = 8000 # Size of audio chunks to process at a time
# Use a more specific temp directory name
TEMP_DIR_BASE_NAME = "vosk_gui_temp_audio"

# --- Audio Conversion ---

def get_ffmpeg_path():
    """
    Tries to find the ffmpeg executable in PATH or common locations.
    Returns the path to the executable or None if not found.
    """
    # Check common locations or PATH environment variable
    ffmpeg_cmd = "ffmpeg"
    try:
        # Check if ffmpeg is in PATH
        startupinfo = None
        if sys.platform == 'win32':
            # Prevent console window popup on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        subprocess.run(
            [ffmpeg_cmd, "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo
        )
        print("FFmpeg found in PATH.")
        return ffmpeg_cmd
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("FFmpeg not found in PATH, checking common locations...")
        # Try common install paths (add more if needed for your system)
        # Consider adding user configuration as a more robust alternative.
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg" # macOS (Apple Silicon) Homebrew
        ]
        for path in common_paths:
            if os.path.isfile(path): # Check if it's a file specifically
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
                         startupinfo=startupinfo
                     )
                     print(f"FFmpeg found at: {path}")
                     return path
                 except (subprocess.CalledProcessError, FileNotFoundError, PermissionError, OSError) as e:
                     # Catch OSError too, e.g., if path is a directory
                     print(f"Found path {path}, but couldn't verify execution: {e}. Skipping.")
                     continue
        print("FFmpeg executable not found in PATH or common locations.")
        return None # Not found

def convert_audio_if_needed(input_path, temp_dir):
    """
    Converts audio to WAV, 16kHz mono using pydub/FFmpeg if necessary.

    Always exports to a temporary WAV file to ensure format consistency,
    even if the input claims to be compatible.

    Args:
        input_path (str): Path to the input audio file.
        temp_dir (str): Directory to store temporary converted files.

    Returns:
        str: Path to the compatible WAV file (potentially temporary).

    Raises:
        RuntimeError: If FFmpeg is not found or conversion fails.
        ValueError: If the audio file cannot be decoded.
        FileNotFoundError: If the input file doesn't exist during processing.
    """
    ffmpeg_executable_path = get_ffmpeg_path()
    if not ffmpeg_executable_path:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH, or modify 'get_ffmpeg_path' function.")

    # Set pydub's converter path
    try:
        AudioSegment.converter = ffmpeg_executable_path
        print(f"Using FFmpeg converter at: {AudioSegment.converter}")
        # Optional: Set ffprobe path if available (often in the same directory)
        # ffprobe_executable = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
        # ffprobe_path = os.path.join(os.path.dirname(ffmpeg_executable_path), ffprobe_executable)
        # if os.path.isfile(ffprobe_path):
        #    AudioSegment.ffprobe = ffprobe_path
        #    print(f"Using FFprobe at: {AudioSegment.ffprobe}")
    except Exception as e:
         print(f"Warning: Could not configure pydub converter/ffprobe paths: {e}")
         # Proceed, pydub might still work if ffmpeg is in PATH correctly.

    try:
        # Load audio file
        print(f"Attempting to load audio file: {input_path}")
        audio = AudioSegment.from_file(input_path)
        print(f"Successfully loaded audio. Original: Channels={audio.channels}, Rate={audio.frame_rate}Hz, Width={audio.sample_width} bytes")

        # Conversion is always performed to ensure a clean WAV file for Vosk
        print(f"Preparing audio for Vosk (16kHz, mono, WAV)...")

        # Create a unique temporary file path inside the temp_dir
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        safe_base_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        # Include PID for potential parallel runs by the same user
        output_wav_path = os.path.join(temp_dir, f"{safe_base_name}_converted_pid{os.getpid()}.wav")

        print(f"Exporting to temporary WAV: '{output_wav_path}'")
        # Perform conversion steps
        audio = audio.set_frame_rate(REQUIRED_SAMPLE_RATE)
        audio = audio.set_channels(1)

        # Export as WAV (PCM 16-bit is default for WAV export in pydub)
        audio.export(output_wav_path, format='wav')
        print(f"Successfully exported temporary WAV file.")
        return output_wav_path

    except CouldntDecodeError as e:
        print(f"Pydub/FFmpeg decode error: {e}")
        raise ValueError(f"Could not decode audio file: {os.path.basename(input_path)}. Ensure it's a valid audio format and FFmpeg is correctly installed/accessible. Error: {e}")
    except FileNotFoundError as e:
        print(f"File not found during conversion: {e}")
        raise FileNotFoundError(f"Input audio file not found during conversion: {input_path}")
    except Exception as e:
        print(f"Unexpected error during audio conversion:")
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
        progress_callback (function): Function to call with progress updates.

    Raises:
        FileNotFoundError: If the model directory/files are invalid.
        RuntimeError: If transcription fails unexpectedly.
        IOError: If the output file cannot be written.
    """
    try:
        # --- Model Loading ---
        progress_callback("Loading Vosk model...")
        print(f"Attempting to load Vosk model from: {model_path}")
        if not os.path.isdir(model_path):
            raise FileNotFoundError(f"Model path is not a valid directory: {model_path}")

        # Check for essential model files (optional but good practice)
        required_model_parts = [os.path.join(model_path, "am", "final.mdl"), os.path.join(model_path, "conf", "model.conf")]
        for part in required_model_parts:
            if not os.path.exists(part):
                 raise FileNotFoundError(f"Model directory seems incomplete. Missing: {part}")

        # Suppress excessive Vosk logging (0=normal, -1=suppress)
        SetLogLevel(0) # Show initial loading messages
        model = Model(model_path)
        recognizer = KaldiRecognizer(model, REQUIRED_SAMPLE_RATE)
        recognizer.SetWords(True) # Enable word timestamps in JSON result
        # recognizer.SetPartialWords(True) # Enable partial words (can be noisy)
        SetLogLevel(-1) # Suppress logs during transcription

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
                    # print(f"Vosk Result JSON: {result_json_str}") # Debug: Full JSON
                    try:
                        result = json.loads(result_json_str)
                        text = result.get('text', '')
                        if text:
                            full_transcript.append(text)
                            progress_callback(f"Segment: ...{text[-70:]}") # Show tail end
                            print(f"Result segment: {text}")
                            # Word timings are in result.get('result', [])
                            # Example:
                            # for word_info in result.get('result', []):
                            #    print(f"Word: {word_info['word']}, Start: {word_info['start']}, End: {word_info['end']}")
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode Vosk Result JSON: {result_json_str}")

                else:
                    # Get partial result
                    partial_result_json_str = recognizer.PartialResult()
                    # print(f"Vosk Partial JSON: {partial_result_json_str}") # Debug: Partial JSON
                    try:
                        partial_result = json.loads(partial_result_json_str)
                        partial_text = partial_result.get('partial', '')
                        if partial_text:
                            progress_callback(f"Partial: ...{partial_text[-70:]}") # Show tail end
                            # print(f"Partial: {partial_text}", end='\r') # Option: print partial to console
                    except json.JSONDecodeError:
                         print(f"Warning: Could not decode Vosk Partial JSON: {partial_result_json_str}")


            print(f"Finished processing audio stream. Total bytes read: {total_bytes_read}")
            # --- Final Result ---
            final_result_json_str = recognizer.FinalResult()
            print(f"Vosk Final JSON: {final_result_json_str}") # Debug: Final JSON
            try:
                final_result = json.loads(final_result_json_str)
                 # Word timings for the whole utterance are in final_result.get('result', [])
                final_text = final_result.get('text', '')
                if final_text:
                    full_transcript.append(final_text)
                    print(f"Final segment result: {final_text}")
            except json.JSONDecodeError:
                 print(f"Warning: Could not decode Vosk Final Result JSON: {final_result_json_str}")


        # --- Save Transcription ---
        final_transcript_text = " ".join(full_transcript).strip()

        if not final_transcript_text:
             progress_callback("Transcription complete. No text detected in the audio.")
             print("Transcription complete. No text detected.")
             # Optionally delete the empty output file? For now, we save it.
             # if os.path.exists(output_txt_path): os.remove(output_txt_path)

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
        # Specifically for model path or essential file errors during loading
        print(f"Error: {e}")
        progress_callback(f"Error: {e}")
        raise
    except Exception as e:
        # Catch other Vosk or file errors
        print(f"An unexpected error occurred during transcription:")
        traceback.print_exc() # Print detailed traceback
        progress_callback(f"Error during transcription: {e}")
        raise # Re-raise for GUI handling

# --- GUI Application ---

class TranscriberApp:
    """
    Main Tkinter application class for the Vosk Transcriber GUI.
    """
    def __init__(self, master):
        """
        Initializes the GUI elements and application state.
        """
        self.master = master
        master.title("Vosk Audio Transcriber")
        master.geometry("650x520") # Slightly taller for button padding

        # --- Member Variables ---
        self.input_file_path = tk.StringVar()
        self.model_dir_path = tk.StringVar(value=DEFAULT_MODEL_DIR)
        self.output_file_path = tk.StringVar()
        # Create temp dir in user's temp folder for better isolation
        self.temp_dir = os.path.join(
            os.path.expanduser("~"),
            f"{TEMP_DIR_BASE_NAME}_pid{os.getpid()}" # Add PID to base name for safety
            )
        self.transcription_thread = None # To hold the thread object
        self.ffmpeg_path = None # Cache ffmpeg path

        # --- Ensure Temp Directory Exists ---
        try:
            os.makedirs(self.temp_dir, exist_ok=True)
            print(f"Temporary directory set to: {self.temp_dir}")
        except OSError as e:
            messagebox.showerror("Initialization Error", f"Could not create temporary directory:\n{self.temp_dir}\nError: {e}\n\nAudio conversion might fail.")
            print(f"ERROR: Failed to create temp directory {self.temp_dir}: {e}")

        # --- Check for FFmpeg early ---
        self.check_ffmpeg_on_startup()

        # --- Styling ---
        label_font = ("Helvetica", 10)
        button_font = ("Helvetica", 10, "bold")
        entry_font = ("Helvetica", 10)
        status_font = ("Helvetica", 9, "italic")
        status_area_font = ("Courier New", 9)

        # --- GUI Layout (using grid) ---
        master.grid_columnconfigure(1, weight=1) # Allow entry fields column to expand
        master.grid_rowconfigure(5, weight=1) # Allow status area row to expand

        # Input File Row
        tk.Label(master, text="Input Audio File:", font=label_font).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.input_entry = tk.Entry(master, textvariable=self.input_file_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.input_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        self.browse_input_btn = tk.Button(master, text="Browse...", command=self.browse_input_file, font=button_font, width=10)
        self.browse_input_btn.grid(row=0, column=2, padx=10, pady=8)

        # Model Directory Row
        tk.Label(master, text="Vosk Model Dir:", font=label_font).grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self.model_entry = tk.Entry(master, textvariable=self.model_dir_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.model_entry.grid(row=1, column=1, padx=5, pady=8, sticky="ew")
        self.browse_model_btn = tk.Button(master, text="Browse...", command=self.browse_model_dir, font=button_font, width=10)
        self.browse_model_btn.grid(row=1, column=2, padx=10, pady=8)

        # Output File Row
        tk.Label(master, text="Output Text File:", font=label_font).grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self.output_entry = tk.Entry(master, textvariable=self.output_file_path, width=60, font=entry_font, state='readonly', relief=tk.SUNKEN, bd=1)
        self.output_entry.grid(row=2, column=1, padx=5, pady=8, sticky="ew")
        self.set_output_btn = tk.Button(master, text="Set Output...", command=self.set_output_file, font=button_font, width=10)
        self.set_output_btn.grid(row=2, column=2, padx=10, pady=8)

        # Transcribe Button Row
        self.transcribe_button = tk.Button(master, text="Transcribe", command=self.start_transcription_thread, font=button_font, bg="#4CAF50", fg="white", relief=tk.RAISED, borderwidth=2, width=15, height=2)
        self.transcribe_button.grid(row=3, column=0, columnspan=3, padx=10, pady=25) # Increased pady

        # Status Label Row
        tk.Label(master, text="Status Log:", font=status_font).grid(row=4, column=0, padx=10, pady=(10, 0), sticky="nw")

        # Status Area Row
        self.status_text = scrolledtext.ScrolledText(master, height=12, width=80, wrap=tk.WORD, font=status_area_font, state='disabled', relief=tk.SUNKEN, borderwidth=1)
        self.status_text.grid(row=5, column=0, columnspan=3, padx=10, pady=(0, 10), sticky="nsew")


        # --- Set Initial State ---
        self.set_default_output_path() # Set initial default output path
        # Initial status depends on FFmpeg check
        if not self.ffmpeg_path:
             self.update_status("WARNING: FFmpeg not found. Audio conversion will likely fail. Please install FFmpeg and ensure it's in PATH.", is_warning=True)
        self.update_status("Ready. Select audio file, Vosk model, and set output path.")


    def check_ffmpeg_on_startup(self):
        """Checks for FFmpeg when the app starts and updates status."""
        self.update_status("Checking for FFmpeg...")
        self.ffmpeg_path = get_ffmpeg_path()
        if self.ffmpeg_path:
            self.update_status(f"FFmpeg found: {self.ffmpeg_path}")
        # Warning message will be added later in init if not found


    def browse_input_file(self):
        """Opens a dialog to select the input audio file."""
        filetypes = (
            ("Audio Files", "*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus *.wma *.aiff *.aif *.wv *.mpc *.ape *.amr *.au *.dat *.unknown"),
            ("All files", "*.*")
        )
        last_dir = os.path.dirname(self.input_file_path.get()) if self.input_file_path.get() else DEFAULT_OUTPUT_DIR
        filepath = filedialog.askopenfilename(
            title="Select Input Audio File",
            initialdir=last_dir,
            filetypes=filetypes
        )
        if filepath:
            self.input_file_path.set(filepath)
            self.set_default_output_path(filepath, force_update=True) # Update output suggestion
            self.update_status(f"Selected input: {os.path.basename(filepath)}")

    def browse_model_dir(self):
        """Opens a dialog to select the Vosk model directory."""
        last_dir = self.model_dir_path.get() if self.model_dir_path.get() else DEFAULT_MODEL_DIR
        dirpath = filedialog.askdirectory(
            title="Select Vosk Model Directory (e.g., 'vosk-model-en-us-0.22')",
            initialdir=last_dir
            )
        if dirpath:
            # Robust check for essential Vosk model structure elements
            required_elements = [
                os.path.join(dirpath, "am", "final.mdl"),      # Acoustic model
                os.path.join(dirpath, "conf", "model.conf"),   # Main config
                os.path.join(dirpath, "graph"),                # Graph directory
                # os.path.join(dirpath, "graph", "HCLG.fst"),  # Specific graph file (optional check)
                # os.path.join(dirpath, "graph", "words.txt") # Word list (optional check)
                os.path.join(dirpath, "ivector")               # Check for ivector dir if present in model structure
            ]
            missing_elements = []
            for elem in required_elements:
                # Allow for optional elements like ivector
                is_optional = "ivector" in elem
                if not os.path.exists(elem):
                    # Only count as missing if it's not an optional element OR if it was expected
                    # This logic might need refinement based on exact model structures
                    # Simplified: Check core required files/dirs
                     if elem.endswith(".mdl") or elem.endswith(".conf") or elem.endswith("graph"):
                        missing_elements.append(os.path.basename(os.path.dirname(elem)) + os.sep + os.path.basename(elem) if not os.path.isdir(elem) else os.path.basename(elem))


            if not missing_elements:
                self.model_dir_path.set(dirpath)
                self.update_status(f"Selected model: {os.path.basename(dirpath)}")
            else:
                missing_str = "\n - ".join(missing_elements)
                messagebox.showwarning("Invalid Model Directory",
                                       f"The selected directory:\n{dirpath}\n\n"
                                       f"Appears to be missing required Vosk model elements:\n - {missing_str}\n\n"
                                       "Please select the main folder containing 'am', 'conf', 'graph', etc.")
                self.model_dir_path.set("") # Clear invalid path


    def set_output_file(self):
        """Opens a dialog to set the output text file path."""
        initial_filename = "transcription.txt"
        input_path = self.input_file_path.get()
        if input_path:
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            initial_filename = f"{base_name}_transcription.txt"

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
        if force_update or not self.output_file_path.get():
             output_dir = DEFAULT_OUTPUT_DIR
             filename = "transcription.txt"
             if input_filepath:
                 base_name = os.path.splitext(os.path.basename(input_filepath))[0]
                 filename = f"{base_name}_transcription.txt"
                 # Default output to same directory as input file if possible
                 input_dir = os.path.dirname(input_filepath)
                 if input_dir and os.path.isdir(input_dir):
                     output_dir = input_dir

             default_output = os.path.join(output_dir, filename)
             self.output_file_path.set(default_output)
             # Avoid status update here as it's called implicitly


    def update_status(self, message, is_warning=False, is_error=False):
        """Updates the status text area in a thread-safe way."""
        def _update():
            self.status_text.config(state='normal')
            # Basic tagging for color (optional, could be more sophisticated)
            tag = None
            if is_error:
                tag = "error"
                self.status_text.tag_configure("error", foreground="red")
            elif is_warning:
                tag = "warning"
                self.status_text.tag_configure("warning", foreground="orange")

            if tag:
                self.status_text.insert(tk.END, message + "\n", tag)
            else:
                 self.status_text.insert(tk.END, message + "\n")

            self.status_text.see(tk.END) # Scroll to the bottom
            self.status_text.config(state='disabled')
        # Schedule the update to run in the main event loop
        if self.master.winfo_exists(): # Check if window exists before scheduling
             self.master.after(0, _update)


    def transcription_task(self):
        """The core transcription logic executed in a separate thread."""
        input_file = self.input_file_path.get()
        model_dir = self.model_dir_path.get()
        output_file = self.output_file_path.get()

        # Re-check FFmpeg availability before starting conversion
        if not self.ffmpeg_path:
            self.update_status("ERROR: FFmpeg not found. Cannot proceed with audio conversion.", is_error=True)
            self.enable_controls()
            self.master.after(0, lambda: messagebox.showerror("Dependency Error", "FFmpeg executable not found. Please install FFmpeg and ensure it is in your system's PATH."))
            return

        # Basic path checks (already done in GUI, but belt-and-suspenders)
        if not all([input_file, model_dir, output_file]):
            self.update_status("ERROR: Missing input, model, or output path.", is_error=True)
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
            self.update_status(f"Using audio for transcription: {os.path.basename(converted_audio_path)}")

            # --- Step 2: Transcription ---
            self.update_status("Step 2: Starting Vosk transcription...")
            # Pass the callback function
            transcribe_audio(converted_audio_path, model_dir, output_file, self.update_status)
            # Success message is now handled within transcribe_audio or here if needed

        except (ValueError, RuntimeError, FileNotFoundError, IOError) as e:
            # Catch errors from conversion or transcription (setup, file IO, etc.)
            error_msg = f"ERROR: {e}"
            print(error_msg)
            self.update_status(error_msg, is_error=True)
            # Show a popup for critical errors using thread-safe call
            self.master.after(0, lambda: messagebox.showerror("Transcription Error", f"An error occurred:\n{e}"))
        except Exception as e:
            # Catch unexpected errors during the process
            error_msg = f"UNEXPECTED ERROR: {e}"
            print(error_msg)
            traceback.print_exc() # Print detailed traceback
            self.update_status(error_msg, is_error=True)
            self.master.after(0, lambda: messagebox.showerror("Unexpected Error", f"An unexpected critical error occurred:\n{e}"))
        finally:
            # --- Step 3: Cleanup and Re-enable Controls ---
            self.update_status("-" * 30)
            # Clean up temporary converted file if created and exists
            if converted_audio_path and converted_audio_path != input_file and os.path.exists(converted_audio_path):
                 try:
                     os.remove(converted_audio_path)
                     print(f"Cleaned up temporary file: {converted_audio_path}")
                     self.update_status(f"Cleaned up temp file: {os.path.basename(converted_audio_path)}")
                 except OSError as e:
                     print(f"Warning: Could not remove temporary file {converted_audio_path}: {e}")
                     self.update_status(f"Warning: Could not remove temp file: {os.path.basename(converted_audio_path)}", is_warning=True)
            else:
                 # Only log if a temp file path was expected but not found/cleaned
                 if converted_audio_path and converted_audio_path != input_file:
                     print(f"Temporary file path was set ({converted_audio_path}), but not found for cleanup.")
                 else:
                     print("No temporary conversion file needed cleanup.")
                     self.update_status("No temporary conversion file to clean up.")


            self.enable_controls() # Re-enable button/controls
            self.update_status("Process finished.")


    def start_transcription_thread(self):
        """Validates inputs and starts the transcription process in a new thread."""
        input_file = self.input_file_path.get()
        model_dir = self.model_dir_path.get()
        output_file = self.output_file_path.get()

        # --- Validation ---
        if not input_file or not os.path.isfile(input_file): # Check if it's a file
            messagebox.showerror("Input Error", "Please select a valid input audio file.")
            return
        if not model_dir or not os.path.isdir(model_dir):
            messagebox.showerror("Input Error", "Please select a valid Vosk model directory.")
            return
        # Re-validate model structure just before starting
        required_model_parts = [os.path.join(model_dir, "am", "final.mdl"), os.path.join(model_dir, "conf", "model.conf")]
        if not all(os.path.exists(p) for p in required_model_parts):
             messagebox.showerror("Input Error", "The selected Vosk model directory seems invalid or incomplete. Please re-select.")
             return

        if not output_file:
            messagebox.showerror("Input Error", "Please set an output text file path using 'Set Output...'.")
            return
        # Check if output directory exists
        output_dir = os.path.dirname(output_file)
        if not os.path.isdir(output_dir):
             try:
                 # Attempt to create the output directory
                 os.makedirs(output_dir, exist_ok=True)
                 self.update_status(f"Created output directory: {output_dir}")
             except OSError as e:
                 messagebox.showerror("Output Error", f"The directory for the output file does not exist and could not be created:\n{output_dir}\nError: {e}")
                 return


        # --- Disable Controls and Start Thread ---
        self.disable_controls()
        # Create and start the thread
        # Use daemon=True so thread exits if main app closes unexpectedly
        self.transcription_thread = threading.Thread(target=self.transcription_task, daemon=True)
        self.transcription_thread.start()

    def disable_controls(self):
        """Disables buttons during processing."""
        self.transcribe_button.config(state=tk.DISABLED, text="Transcribing...")
        self.browse_input_btn.config(state=tk.DISABLED)
        self.browse_model_btn.config(state=tk.DISABLED)
        self.set_output_btn.config(state=tk.DISABLED)
        # Readonly entry fields are visually distinct enough usually

    def enable_controls(self):
        """Re-enables controls after processing (thread-safe)."""
        def _enable():
             # Check if window still exists before configuring widgets
            if self.master.winfo_exists():
                self.transcribe_button.config(state=tk.NORMAL, text="Transcribe")
                self.browse_input_btn.config(state=tk.NORMAL)
                self.browse_model_btn.config(state=tk.NORMAL)
                self.set_output_btn.config(state=tk.NORMAL)
        if self.master.winfo_exists():
            self.master.after(0, _enable)


    def clear_status(self):
        """Clears the status text area (thread-safe)."""
        def _clear():
             if self.master.winfo_exists():
                self.status_text.config(state='normal')
                self.status_text.delete('1.0', tk.END)
                self.status_text.config(state='disabled')
        if self.master.winfo_exists():
             self.master.after(0, _clear)

    def on_closing(self):
        """Handles window closing: confirms quit and cleans up temp directory."""
        print("Close button clicked.")
        if messagebox.askokcancel("Quit", "Do you want to quit?\nTemporary conversion files will be deleted."):
            print("Quitting application.")
            try:
                # Attempt to remove the specific temp directory for this run
                if os.path.isdir(self.temp_dir): # Check if it exists and is a directory
                    print(f"Attempting to remove temporary directory: {self.temp_dir}")
                    shutil.rmtree(self.temp_dir)
                    print(f"Successfully removed temporary directory.")
                else:
                    print(f"Temporary directory ({self.temp_dir}) not found or not a directory, no cleanup needed.")
            except Exception as e:
                # Log error but don't prevent closing
                print(f"Warning: Could not remove temporary directory {self.temp_dir}: {e}")
                # Use messagebox if GUI still exists conceptually, though it's being destroyed
                try:
                    messagebox.showwarning("Cleanup Warning", f"Could not automatically remove the temporary directory:\n{self.temp_dir}\n\nYou may need to delete it manually.\nError: {e}")
                except tk.TclError:
                    print("GUI already gone, cannot show messagebox.") # Gracefully handle if master is already destroyed

            # Destroy the Tkinter window
            self.master.destroy()


# --- Main Execution ---
if __name__ == "__main__":
    # Set up the main Tkinter window
    root = tk.Tk()
    # Create the application instance
    app = TranscriberApp(root)
    # Set the action for the window close button ('X')
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    # Start the Tkinter event loop
    root.mainloop()