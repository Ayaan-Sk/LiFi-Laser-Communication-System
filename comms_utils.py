import numpy as np
from scipy import signal
from Crypto.Cipher import AES
from Crypto.Util import Counter
import hashlib

class AESCipher:
    """Handles AES encryption and decryption using CTR mode."""
    def __init__(self, key: str = "default_secret_k"):
        if not key or not str(key).strip():
            key_str = "default_secret_k"
        else:
            key_str = str(key).strip()
        key_bytes = key_str.encode('utf-8')
        self.key = hashlib.sha256(key_bytes).digest()

    def encrypt(self, plaintext: bytes) -> bytes:
        ctr = Counter.new(128)
        cipher = AES.new(self.key, AES.MODE_CTR, counter=ctr)
        return cipher.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        ctr = Counter.new(128)
        cipher = AES.new(self.key, AES.MODE_CTR, counter=ctr)
        return cipher.decrypt(ciphertext)

def bytes_to_bits(data: bytes) -> list:
    """Converts bytes to a list of bits (integers 0 or 1)."""
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def bits_to_bytes(bits: list) -> bytes:
    """Converts a list of bits (integers) back to bytes."""
    byte_list = []
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            chunk = chunk + [0] * (8 - len(chunk))
        byte = 0
        for bit in chunk:
            byte = (byte << 1) | int(bit)
        byte_list.append(byte)
    return bytes(byte_list)

class LiFiModulator:
    """Handles fast OOK modulation with a 5kHz carrier frequency."""
    def __init__(self, sample_rate=44100, baud_rate=100, carrier_freq=5000):
        self.fs = sample_rate
        self.baud = baud_rate
        self.carrier_freq = carrier_freq
        self.samples_per_bit = int(self.fs / self.baud)
        
        # Preamble: 16 alternating bits for clock sync
        self.preamble = [1, 0] * 8
        # Sync word: 8 bits to mark start of payload
        self.sync_word = [0, 1, 1, 1, 1, 1, 1, 0]

    def modulate(self, bits: list) -> np.ndarray:
        """Converts a bitstream into an audio waveform."""
        full_payload = self.preamble + self.sync_word + bits
        t = np.linspace(0, len(full_payload) * (1/self.baud), len(full_payload) * self.samples_per_bit, endpoint=False)
        
        carrier = np.sin(2 * np.pi * self.carrier_freq * t)
        mask = np.repeat(full_payload, self.samples_per_bit)
        
        min_len = min(len(carrier), len(mask))
        return (carrier[:min_len] * mask[:min_len]).astype(np.float32)

class LiFiDemodulator:
    """Handles fast OOK demodulation and synchronization."""
    def __init__(self, sample_rate=44100, baud_rate=100, carrier_freq=5000):
        self.fs = sample_rate
        self.baud = baud_rate
        self.carrier_freq = carrier_freq
        self.samples_per_bit = int(self.fs / self.baud)
        
        self.preamble = [1, 0] * 8
        self.sync_word = [0, 1, 1, 1, 1, 1, 1, 0]

    def demodulate(self, audio_data: np.ndarray) -> list:
        """Extracts bits from an audio waveform."""
        if len(audio_data) < self.samples_per_bit * 24:
            return []
            
        nyq = 0.5 * self.fs
        low = (self.carrier_freq - 500) / nyq
        high = (self.carrier_freq + 500) / nyq
        b, a = signal.butter(4, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, audio_data)
        
        rectified = np.abs(filtered)
        lp_b, lp_a = signal.butter(4, (self.baud * 2) / nyq, btype='low')
        envelope = signal.filtfilt(lp_b, lp_a, rectified)
        
        threshold = np.percentile(envelope, 98) * 0.5
        if threshold < 1e-4:
            return []
        binary_envelope = (envelope > threshold).astype(int)
        
        sync_bits = np.array(self.preamble + self.sync_word)
        sync_samples = np.repeat(sync_bits, self.samples_per_bit)
        
        binary_envelope_polar = 2 * binary_envelope - 1
        sync_samples_polar = 2 * sync_samples - 1
        
        correlation = signal.correlate(binary_envelope_polar, sync_samples_polar, mode='valid', method='fft')
        
        max_possible_corr = len(sync_bits) * self.samples_per_bit
        if len(correlation) == 0 or np.max(correlation) < 0.65 * max_possible_corr:
            return []
            
        sync_start = np.argmax(correlation)
        payload_start = sync_start + (len(sync_bits) * self.samples_per_bit)
        
        decoded_bits = []
        current_idx = payload_start
        search_half_window = max(1, self.samples_per_bit // 4)
        
        while current_idx + self.samples_per_bit <= len(binary_envelope):
            center_idx = int(current_idx + self.samples_per_bit / 2)
            if center_idx >= len(binary_envelope):
                break
            decoded_bits.append(int(binary_envelope[center_idx]))
            
            nominal_boundary = current_idx + self.samples_per_bit
            search_start = max(1, nominal_boundary - search_half_window)
            search_end = min(len(binary_envelope), nominal_boundary + search_half_window + 1)
            
            edge_found_idx = None
            min_dist = float('inf')
            
            for j in range(search_start, search_end):
                if binary_envelope[j] != binary_envelope[j-1]:
                    dist = abs(j - nominal_boundary)
                    if dist < min_dist:
                        min_dist = dist
                        edge_found_idx = j
            
            if edge_found_idx is not None:
                error = edge_found_idx - nominal_boundary
                current_idx = nominal_boundary + int(0.1 * error)
            else:
                current_idx = nominal_boundary
        
        return decoded_bits
