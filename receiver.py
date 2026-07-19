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

        self.demodulator = LiFiDemodulator(baud_rate=100)
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
        self.key_entry = tk.Entry(settings_frame, width=30, show="*")
        self.key_entry.insert(0, "default_secret_k")
        self.key_entry.grid(row=0, column=1, padx=10)

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
        duration = 10 # Buffer size in seconds
        fs = 44100
        
        while self.is_listening:
            # Record a chunk
            recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
            sd.wait()
            
            if not self.is_listening: break
            
            self.process_audio(recording.flatten())

    def update_viz(self, audio_data):
        self.ax.clear()
        # Show a slice of the input
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
                self.status_var.set("Status: Listening (No data found)")
                return

            self.status_var.set("Status: Decrypting...")
            encrypted_bytes = bits_to_bytes(bits)
            
            cipher = AESCipher(self.key_entry.get())
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            
            # The sender prepends a 4-byte length header. We must extract it.
            if len(decrypted_bytes) >= 4:
                payload_len = int.from_bytes(decrypted_bytes[:4], byteorder='big')
                if 0 <= payload_len <= len(decrypted_bytes) - 4:
                    actual_payload = decrypted_bytes[4:4+payload_len]
                else:
                    actual_payload = decrypted_bytes[4:]
            else:
                actual_payload = decrypted_bytes
            
            # Try to interpret as text
            try:
                # Use errors='replace' to see whatever characters we can decode even if there are errors,
                # but first try a clean decode so we can report if it was perfectly clean or had errors.
                clean_text = actual_payload.decode('utf-8')
                self.root.after(0, self.display_text, f"[Text]: {clean_text}\n")
            except Exception as decode_err:
                # If clean decode fails, show a preview with replacement characters and debug info
                decoded_with_errors = actual_payload.decode('utf-8', errors='replace')
                debug_info = (
                    f"[Decode Fail] Demodulated bits count: {len(bits)}\n"
                    f"[Decode Fail] Decrypted bytes (len={len(actual_payload)}): {actual_payload.hex()}\n"
                    f"[Decode Fail] Decoded (with replacement): {decoded_with_errors}\n"
                    f"[Decode Fail] Error: {decode_err}\n\n"
                )
                self.root.after(0, self.display_text, debug_info)
                
                # If not text, maybe audio?
                if b'WAVE' in actual_payload[:20] or len(actual_payload) > 100:
                    threading.Thread(target=self.play_received_audio, args=(actual_payload,), daemon=True).start()

            self.status_var.set("Status: Listening...")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_var.set("Status: Decode Error")

    def display_text(self, text):
        self.text_output.insert(tk.END, text)
        self.text_output.see(tk.END)

    def play_received_audio(self, data):
        # Very basic check: if it looks like raw PCM (from our 8kHz mic test)
        # We'd need a header or a fixed format to be robust
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
