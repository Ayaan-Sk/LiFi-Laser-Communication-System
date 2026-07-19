import numpy as np
from comms_utils import AESCipher, LiFiModulator, LiFiDemodulator, bytes_to_bits, bits_to_bytes

key = "default_secret_k"
cipher_tx = AESCipher(key)
cipher_rx = AESCipher(key)
modulator = LiFiModulator(baud_rate=100)
demodulator = LiFiDemodulator(baud_rate=100)

text = "hello"
data_bytes = text.encode('utf-8')
lenght_header = len(data_bytes).to_bytes(4, byteorder='big')
encrypted_data = cipher_tx.encrypt(lenght_header + data_bytes)

bits = bytes_to_bits(encrypted_data)
waveform = modulator.modulate(bits)

fs = 44100
silence_len = int(2 * fs)
silence_start = np.random.normal(0, 0.01, silence_len)
silence_end = np.random.normal(0, 0.01, int(2 * fs))
noise = np.random.normal(0, 0.05, len(waveform))
noisy_waveform = np.concatenate([silence_start, waveform + noise, silence_end])

demodulated_bits = demodulator.demodulate(noisy_waveform)

rx_bytes = bits_to_bytes(demodulated_bits)
print("Demodulated rx_bytes (len={}):".format(len(rx_bytes)))
print(rx_bytes.hex())

decrypted_rx = cipher_rx.decrypt(rx_bytes)
print("Decrypted rx_bytes (len={}):".format(len(decrypted_rx)))
print(decrypted_rx.hex())

# Extract header and actual data
if len(decrypted_rx) >= 4:
    payload_len = int.from_bytes(decrypted_rx[:4], byteorder='big')
    print("Parsed payload_len:", payload_len)
    if 0 <= payload_len <= len(decrypted_rx) - 4:
        actual_payload = decrypted_rx[4:4+payload_len]
    else:
        actual_payload = decrypted_rx[4:]
else:
    actual_payload = decrypted_rx

print("Actual payload text:", actual_payload.decode('utf-8', errors='replace'))
