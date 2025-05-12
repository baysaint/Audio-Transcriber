# Vosk Audio Transcriber GUI

A simple graphical user interface (GUI) application built with Python and Tkinter to transcribe audio files using the Vosk offline speech recognition toolkit.

This application allows users to:

* Select an audio file (various formats supported via FFmpeg).
* Select a downloaded Vosk language model directory.
* Specify an output text file location.
* Transcribe the audio file, automatically converting it to the required format (16kHz mono WAV) if necessary.
* View transcription progress and status updates.

## Features

* **GUI Interface:** Easy-to-use graphical interface powered by Tkinter.
* **Audio Conversion:** Automatically converts various input audio formats to the WAV format required by Vosk using `pydub` and FFmpeg.
* **Vosk Integration:** Uses the `vosk` library for offline speech recognition.
* **Progress Display:** Shows partial transcription results and status messages.
* **Error Handling:** Provides feedback on common errors (e.g., file not found, invalid model).
* **Cross-Platform (Potentially):** Built with standard Python libraries, should work on Windows, macOS, and Linux (requires dependencies to be installed correctly).

## Prerequisites

Before running the application, ensure you have the following installed:

1.  **Python:** Version 3.7 or higher recommended. Download from [python.org](https://www.python.org/downloads/).
2.  **FFmpeg:** This is required by `pydub` for audio conversion.
    * **Download:** Get FFmpeg from the official website: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
    * **Installation:** Follow the installation instructions for your operating system.
    * **Crucially:** Ensure the `ffmpeg` executable is added to your system's **PATH environment variable** so the script can find it automatically. Alternatively, you might need to modify the `get_ffmpeg_path()` function in the script if FFmpeg is installed in a non-standard location.
3.  **Vosk Language Model:** You need to download a Vosk language model suitable for the audio you want to transcribe.
    * **Download:** Models are available on the Vosk website: [https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)
    * **Extraction:** Download the model archive (e.g., `vosk-model-en-us-0.22.zip`) and **unzip it** into a dedicated folder. You will select this *folder* (e.g., `vosk-model-en-us-0.22`) in the application.
4.  **`audioop-lts` (for Python 3.13+):** If you are using Python version 3.13 or newer, you will need to install the `audioop-lts` package. The standard `audioop` module, which `pydub` depends on, was removed in Python 3.13. This package provides the necessary replacement. Users on Python 3.12 or older do not need this specific package. It will be handled automatically if using the `requirements.txt` file below.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url> # Replace <repository-url> with your repo URL
    cd <repository-directory>
    ```
    Or, download the script (`vosk_transcriber_gui.py`) directly.

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # Activate the virtual environment
    # Windows:
    .\venv\Scripts\activate
    # macOS/Linux:
    source venv/bin/activate
    ```

3.  **Create `requirements.txt`:** Create a file named `requirements.txt` in your project directory with the following content:
    ```txt
    vosk
    pydub
    audioop-lts; python_version>='3.13'
    ```
    *(The last line uses an environment marker to ensure `audioop-lts` is only installed when using Python 3.13 or newer).*

4.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

1.  **Activate Virtual Environment** (if you created one).
2.  **Run the Python Script:**
    ```bash
    python vosk_transcriber_gui.py # Use the actual name of your script file
    ```
3.  **Using the GUI:**
    * Click **"Browse..."** next to "Input Audio File" to select the audio file you want to transcribe.
    * Click **"Browse..."** next to "Vosk Model Directory" to select the **folder** where you extracted the Vosk language model.
    * Click **"Set Output..."** next to "Output Text File" to choose where the final transcription `.txt` file will be saved. A default name based on the input file will be suggested.
    * Click the **"Transcribe"** button.
    * The "Status" area will show progress updates, including conversion steps and partial transcription results.
    * Once finished, a confirmation message will appear, and the transcription will be saved to the specified output file.

## Performance Notes

* **Model Size:** Larger Vosk models generally offer better accuracy but require more memory and processing time. Smaller models are faster but might be less accurate.
* **Hardware:** Transcription speed is heavily dependent on your CPU performance.
* **Audio Length:** Longer audio files will naturally take longer to transcribe.
* **Chunk Size:** The `AUDIO_CHUNK_SIZE` in the script can be experimented with, but significant speedups are usually limited by the model inference itself.
* **FFmpeg:** Ensure FFmpeg is correctly installed and accessible, as conversion issues can halt the process.

## Potential Improvements

* Add proper punctuation to the transcribed text. Text can be summarized comprehensively by the help of any AI tool.
* Add support for selecting specific languages if multiple models are present.
* Implement pausing/stopping the transcription process.
* Display word timings if the model supports it (`recognizer.SetWords(True)` is enabled).
* Package the application into an executable using tools like PyInstaller.
* More robust FFmpeg path detection or configuration.

## License

[GInitiatives, e.g., Free-to-use License]
