import numpy as np
from comms_utils import (
    AESCipher, LiFiModulator, LiFiDemodulator,
    bytes_to_bits, bits_to_bytes
)

def run_tests():
    print("==========================================")
    print("   Li-Fi Encryption & Comms Test Suite")
    print("==========================================")

    key = "default_secret_k"
    cipher_tx = AESCipher(key)
    cipher_rx = AESCipher(key)
    modulator = LiFiModulator(baud_rate=100)
    demodulator = LiFiDemodulator(baud_rate=100)

    text = "hello"
    data_bytes = text.encode('utf-8')
    length_header = len(data_bytes).to_bytes(4, byteorder='big')
    encrypted_data = cipher_tx.encrypt(length_header + data_bytes)

    bits = bytes_to_bits(encrypted_data)
    waveform = modulator.modulate(bits)

    fs = 44100
    silence_start = np.random.normal(0, 0.01, int(1 * fs))
    silence_end = np.random.normal(0, 0.01, int(1 * fs))
    noise = np.random.normal(0, 0.02, len(waveform))
    noisy_waveform = np.concatenate([silence_start, waveform + noise, silence_end])

    demodulated_bits = demodulator.demodulate(noisy_waveform)
    rx_bytes = bits_to_bytes(demodulated_bits)
    decrypted_rx = cipher_rx.decrypt(rx_bytes)

    assert len(decrypted_rx) >= 4
    payload_len = int.from_bytes(decrypted_rx[:4], byteorder='big')
    assert payload_len == 5
    actual_payload = decrypted_rx[4:4+payload_len]
    decoded_text = actual_payload.decode('utf-8')

    assert decoded_text == text, f"Expected '{text}', got '{decoded_text}'"
    print(f"[PASS] End-to-End Transmission: '{decoded_text}'")
    print("\nALL COMMUNICATIONS & ENCRYPTION TESTS PASSED SUCCESSFULLY! [OK]")

if __name__ == "__main__":
    run_tests()
