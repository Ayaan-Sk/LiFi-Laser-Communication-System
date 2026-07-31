import tkinter as tk
from tkinter import scrolledtext, messagebox
import numpy as np
import sounddevice as sd
import threading
import queue
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from comms_utils import AESCipher, LiFiDemodulator, bits_to_bytes

class LiFiReceiverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Li-Fi Receiver (Decoder)")
        self.root.geometry("800x800")
        self.root.configure(bg="#2c3e50")

        self.demodulator = LiFiDemodulator(baud_rate=100, carrier_freq=5000)
        self.audio_queue = queue.Queue()
        self.is_listening = False
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Label(self.root, text="Li-Fi Digital Audio Receiver", font=("Helvetica", 18, "bold"), fg="#ecf0f1", bg="#2c3e50")
        header.pack(pady=10)

        # Settings
        settings_frame = tk.LabelFrame(self.root, text="Settings", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        settings_frame.pack(fill="x", padx=20, pady=5)

        tk.Label(settings_frame, text="AES Decryption Key:", fg="#ecf0f1", bg="#2c3e50").grid(row=0, column=0, sticky="w")
        self.key_entry = tk.Entry(settings_frame, width=30)
        self.key_entry.insert(0, "default_secret_k")
        self.key_entry.grid(row=0, column=1, padx=10)

        tk.Label(settings_frame, text="Gemini API Key (Optional):", fg="#ecf0f1", bg="#2c3e50").grid(row=1, column=0, sticky="w", pady=5)
        self.ai_key_entry = tk.Entry(settings_frame, width=30, show="*")
        import os
        self.ai_key_entry.insert(0, os.environ.get("GEMINI_API_KEY", ""))
        self.ai_key_entry.grid(row=1, column=1, padx=10, pady=5)

        # Controls
        ctrl_frame = tk.Frame(self.root, bg="#2c3e50")
        ctrl_frame.pack(pady=10)

        self.listen_btn = tk.Button(ctrl_frame, text="Start Listening", command=self.toggle_listen, bg="#27ae60", fg="white", width=20)
        self.listen_btn.grid(row=0, column=0, padx=5)
        
        tk.Button(ctrl_frame, text="Clear Data", command=self.clear_data, bg="#7f8c8d", fg="white", width=20).grid(row=0, column=1, padx=5)

        # Output / Results
        out_frame = tk.LabelFrame(self.root, text="Received Data", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        out_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.text_output = scrolledtext.ScrolledText(out_frame, height=10, bg="#34495e", fg="#2ecc71", font=("Consolas", 10))
        self.text_output.pack(fill="both", expand=True)

        # Visualization
        viz_frame = tk.LabelFrame(self.root, text="Incoming Pulse Signal", fg="#ecf0f1", bg="#2c3e50", padx=10, pady=10)
        viz_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.fig = Figure(figsize=(6, 3), dpi=100, facecolor='#2c3e50')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#34495e')
        self.ax.tick_params(colors='white')
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Status: Ready")
        tk.Label(self.root, textvariable=self.status_var, fg="#f1c40f", bg="#2c3e50", font=("Helvetica", 12)).pack(pady=10)

    def toggle_listen(self):
        if not self.is_listening:
            self.is_listening = True
            self.listen_btn.config(text="Stop Listening", bg="#c0392b")
            self.status_var.set("Status: Listening...")
            threading.Thread(target=self.listening_thread, daemon=True).start()
        else:
            self.is_listening = False
            self.listen_btn.config(text="Start Listening", bg="#27ae60")
            self.status_var.set("Status: Stopped")

    def listening_thread(self):
        duration = 5 # 5-second buffer size for fast responsive audio processing
        fs = 44100
        
        while self.is_listening:
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()
            
            if not self.is_listening: break
            
            self.process_audio(recording.flatten())

    def update_viz(self, audio_data):
        self.ax.clear()
        self.ax.plot(audio_data[:2000], color='#f1c40f')
        self.ax.set_facecolor('#34495e')
        self.ax.tick_params(colors='white')
        self.canvas.draw()

    def process_audio(self, audio_data):
        self.root.after(0, self.update_viz, audio_data)
        
        self.status_var.set("Status: Decoding Bits...")
        try:
            bits = self.demodulator.demodulate(audio_data)
            if not bits or len(bits) < 8:
                self.status_var.set("Status: Listening...")
                return

            self.status_var.set("Status: Decrypting...")
            encrypted_bytes = bits_to_bytes(bits)
            
            key = self.key_entry.get().strip() or "default_secret_k"
            cipher = AESCipher(key)
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            
            if len(decrypted_bytes) >= 4:
                payload_len = int.from_bytes(decrypted_bytes[:4], byteorder='big')
                if 0 <= payload_len <= len(decrypted_bytes) - 4:
                    actual_payload = decrypted_bytes[4:4+payload_len]
                else:
                    actual_payload = decrypted_bytes[4:]
            else:
                actual_payload = decrypted_bytes
            
            try:
                clean_text = actual_payload.decode('utf-8')
                self.root.after(0, self.display_text, f"[Text]: {clean_text}\n")
            except Exception as decode_err:
                decoded_with_errors = actual_payload.decode('utf-8', errors='replace')
                self.root.after(0, self.display_text, f"[Decrypted Text]: {decoded_with_errors}\n")
                self.try_ai_repair(actual_payload, decoded_with_errors)

            self.status_var.set("Status: Listening...")
        except Exception as e:
            self.status_var.set("Status: Decode Error")

    def try_ai_repair(self, actual_payload, decoded_with_errors):
        api_key = self.ai_key_entry.get().strip()
        if not api_key:
            return
            
        def run_ai():
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                
                prompt = (
                    "You are assisting a Li-Fi communication system receiver. "
                    "Reconstruct the original intended plaintext message based on the following information.\n\n"
                    f"Partially decoded text: \"{decoded_with_errors}\"\n"
                    f"Raw decrypted payload bytes (hex): \"{actual_payload.hex()}\"\n\n"
                    "Output ONLY the corrected plaintext message without code blocks or extra formatting."
                )
                
                response = model.generate_content(prompt)
                reconstructed = response.text.strip()
                self.root.after(0, self.display_text, f"[AI Reconstructed]: {reconstructed}\n\n")
            except Exception as ai_err:
                self.root.after(0, self.display_text, f"[AI Repair Error]: {str(ai_err)}\n\n")
                
        threading.Thread(target=run_ai, daemon=True).start()

    def display_text(self, text):
        self.text_output.insert(tk.END, text)
        self.text_output.see(tk.END)

    def play_received_audio(self, data):
        try:
            audio_array = np.frombuffer(data, dtype='int16')
            sd.play(audio_array, samplerate=8000)
            sd.wait()
        except:
            pass

    def clear_data(self):
        self.text_output.delete("1.0", tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = LiFiReceiverApp(root)
    root.mainloop()
