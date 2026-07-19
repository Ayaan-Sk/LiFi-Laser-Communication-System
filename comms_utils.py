import numpy as np
from scipy import signal
from Crypto.Cipher import AES
from Crypto.Util import Counter
import base64

class AESCipher:
    """Handles AES encryption and decryption using CTR mode."""
    def __init__(self, key: str):
        # AES-256 requires 32 bytes. We'll pad or truncate the user key.
        self.key = key.encode('utf-8').ljust(32, b'\0')[:32]

    def encrypt(self, plaintext: bytes) -> bytes:
        # Use CTR mode for arbitrary length data without padding issues
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
        byte = 0
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            # Pad with zeros if bits don't align to byte boundary
            chunk = chunk + [0] * (8 - len(chunk))
        for bit in chunk:
            byte = (byte << 1) | bit
        byte_list.append(byte)
    return bytes(byte_list)

class LiFiModulator:
    """Handles OOK modulation with a carrier frequency."""
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
        
        # Generate carrier signal
        carrier = np.sin(2 * np.pi * self.carrier_freq * t)
        
        # Create modulation mask (1 for '1', 0 for '0')
        mask = np.repeat(full_payload, self.samples_per_bit)
        
        # Ensure mask and carrier match in length
        min_len = min(len(carrier), len(mask))
        return (carrier[:min_len] * mask[:min_len]).astype(np.float32)

class LiFiDemodulator:
    """Handles OOK demodulation and synchronization."""
    def __init__(self, sample_rate=44100, baud_rate=100, carrier_freq=5000):
        self.fs = sample_rate
        self.baud = baud_rate
        self.carrier_freq = carrier_freq
        self.samples_per_bit = int(self.fs / self.baud)
        
        self.sync_word = [0, 1, 1, 1, 1, 1, 1, 0]

    def demodulate(self, audio_data: np.ndarray) -> list:
        """Extracts bits from an audio waveform."""
        # 1. Bandpass filter around carrier frequency
        nyq = 0.5 * self.fs
        low = (self.carrier_freq - 500) / nyq
        high = (self.carrier_freq + 500) / nyq
        b, a = signal.butter(4, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, audio_data)
        
        # 2. Envelope detection (Rectification + Lowpass)
        rectified = np.abs(filtered)
        # Lowpass filter to smooth the envelope (cutoff at 2 * baud)
        lp_b, lp_a = signal.butter(4, (self.baud * 2) / nyq, btype='low')
        envelope = signal.filtfilt(lp_b, lp_a, rectified)
        
        # 3. Dynamic Thresholding using 98th percentile to avoid pop/click noise spikes
        threshold = np.percentile(envelope, 98) * 0.5
        binary_envelope = (envelope > threshold).astype(int)
        
        # 4. Synchronization and Sampling
        # This is the tricky part: find the sync word
        # We'll use polar cross-correlation (mapping 0 -> -1 and 1 -> 1)
        # to ensure that mismatches (e.g. 1 where a 0 is expected) are penalized.
        sync_bits = np.array(self.sync_word)
        sync_samples = np.repeat(sync_bits, self.samples_per_bit)
        
        # Convert binary 0/1 to polar -1/1
        binary_envelope_polar = 2 * binary_envelope - 1
        sync_samples_polar = 2 * sync_samples - 1
        
        # Cross correlate to find sync word position
        correlation = np.correlate(binary_envelope_polar, sync_samples_polar, mode='valid')
        sync_start = np.argmax(correlation)
        
        # Start sampling bits after the sync word
        payload_start = sync_start + (len(self.sync_word) * self.samples_per_bit)
        
        decoded_bits = []
        for i in range(payload_start, len(binary_envelope) - self.samples_per_bit, self.samples_per_bit):
            # Sample in the middle of the bit period
            sample_point = i + (self.samples_per_bit // 2)
            if sample_point < len(binary_envelope):
                decoded_bits.append(binary_envelope[sample_point])
        
        return decoded_bits
