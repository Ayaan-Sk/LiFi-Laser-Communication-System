import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import numpy as np
import sounddevice as sd
import pyttsx3
import os
import tempfile
import wave
import threading
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from comms_utils import AESCipher, LiFiModulator, bytes_to_bits

class LiFiSenderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Li-Fi Digital Audio Transmitter (Sender)")
        self.root.geometry("800x800")
        self.root.configure(bg="#2c3e50")

        self.cipher = None
        self.modulator = LiFiModulator(baud_rate=100, carrier_freq=5000) # Fast & Loud
        self.is_transmitting = False

        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Label(self.root, text="Li-Fi Digital Audio Transmitter", font=("Helvetica", 18, "bold"), fg="#ecf0f1", bg="#2c3e50")
        header.pack(pady=10)

        # Settings Frame
        settings_frame = tk.LabelFrame(self.root, text="Settings", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        settings_frame.pack(fill="x", padx=20, pady=5)

        tk.Label(settings_frame, text="AES Encryption Key (16 chars):", fg="#ecf0f1", bg="#2c3e50").grid(row=0, column=0, sticky="w")
        self.key_entry = tk.Entry(settings_frame, width=30)
        self.key_entry.insert(0, "default_secret_k")
        self.key_entry.grid(row=0, column=1, padx=10)

        # Serial Frame
        serial_frame = tk.LabelFrame(settings_frame, text="Serial Output (Arduino / Laser Driver)", fg="#ecf0f1", bg="#2c3e50")
        serial_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        
        tk.Label(serial_frame, text="COM Port:", fg="#ecf0f1", bg="#2c3e50").grid(row=0, column=0)
        self.port_entry = tk.Entry(serial_frame, width=10)
        self.port_entry.insert(0, "COM3")
        self.port_entry.grid(row=0, column=1, padx=5)
        
        self.use_serial = tk.BooleanVar(value=False)
        tk.Checkbutton(serial_frame, text="Enable Serial Output", variable=self.use_serial, bg="#2c3e50", fg="#ecf0f1", selectcolor="#34495e").grid(row=0, column=2, padx=10)

        # Input Frame
        input_frame = tk.LabelFrame(self.root, text="Audio / Text Input", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        input_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Text mode
        tk.Label(input_frame, text="Enter Text for TTS or Data:", fg="#ecf0f1", bg="#2c3e50").pack(anchor="w")
        self.text_input = scrolledtext.ScrolledText(input_frame, height=5, bg="#34495e", fg="white")
        self.text_input.pack(fill="x", pady=5)

        btn_frame = tk.Frame(input_frame, bg="#2c3e50")
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Transmit Text", command=self.transmit_text, bg="#27ae60", fg="white", width=20).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Select WAV File", command=self.load_wav, bg="#2980b9", fg="white", width=20).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Rec Mic (5s)", command=self.record_mic, bg="#c0392b", fg="white", width=20).grid(row=0, column=2, padx=5)

        # Visualization Frame
        viz_frame = tk.LabelFrame(self.root, text="Signal Visualization", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        viz_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.fig = Figure(figsize=(6, 3), dpi=100, facecolor='#2c3e50')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#34495e')
        self.ax.tick_params(colors='white')
        self.ax.set_title("Modulated Signal Output", color='white')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Status
        self.status_var = tk.StringVar(value="Status: Ready")
        tk.Label(self.root, textvariable=self.status_var, fg="#f1c40f", bg="#2c3e50", font=("Helvetica", 12)).pack(pady=10)

    def update_viz(self, signal):
        self.ax.clear()
        self.ax.plot(signal[:5000], color='#2ecc71')
        self.ax.set_title("OOK Modulated Waveform (First 5000 samples)", color='white')
        self.ax.set_facecolor('#34495e')
        self.ax.tick_params(colors='white')
        self.canvas.draw()

    def get_cipher(self):
        key = self.key_entry.get().strip() or "default_secret_k"
        return AESCipher(key)

    def process_and_transmit(self, data_bytes):
        cipher = self.get_cipher()

        self.status_var.set("Status: Encrypting...")
        lenght_header = len(data_bytes).to_bytes(4, byteorder='big')
        encrypted_data = cipher.encrypt(lenght_header + data_bytes)
        
        self.status_var.set("Status: Modulating...")
        bits = bytes_to_bits(encrypted_data)
        
        # Binary Visualization
        binary_str = "".join(map(str, bits[:100])) + ("..." if len(bits) > 100 else "")
        self.text_input.insert(tk.END, f"\n\n[Binary Stream]:\n{binary_str}\n")
        
        # Audio Output
        waveform = self.modulator.modulate(bits)
        self.update_viz(waveform)
        
        self.status_var.set("Status: Transmitting...")
        
        # Serial Output (If enabled)
        if self.use_serial.get():
            import serial
            try:
                ser = serial.Serial(self.port_entry.get(), 115200, timeout=1)
                for bit in bits:
                    ser.write(str(bit).encode())
                ser.close()
            except Exception as e:
                messagebox.showerror("Serial Error", str(e))

        # Play audio waveform
        sd.play(waveform, samplerate=44100)
        sd.wait()
        self.status_var.set("Status: Transmission Complete")

    def transmit_text(self):
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Warning", "Text is empty!")
            return
        threading.Thread(target=self.process_and_transmit, args=(text.encode('utf-8'),), daemon=True).start()

    def load_wav(self):
        path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if path:
            with open(path, 'rb') as f:
                data = f.read()
                if len(data) > 10000:
                    if not messagebox.askyesno("Large File", "This file is large and will take a long time to transmit. Continue?"):
                        return
                threading.Thread(target=self.process_and_transmit, args=(data,), daemon=True).start()

    def record_mic(self):
        duration = 5  # seconds
        fs = 8000     # Sample rate
        self.status_var.set("Status: Recording...")
        
        def do_rec():
            rec = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            self.status_var.set("Status: Recording Finished")
            data = rec.tobytes()
            self.process_and_transmit(data)

        threading.Thread(target=do_rec, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = LiFiSenderApp(root)
    root.mainloop()
