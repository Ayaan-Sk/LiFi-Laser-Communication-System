# Li-Fi Hardware Connection Guide

This guide explains how to connect your PC to the Laser and Solar Panel for the Li-Fi project.

## 1. Transmitter (Sender) Hardware
You have two options to drive the Laser module:

### Option A: Audio (AUX) Connection [Recommended]
This is the most precise method as the PC sound card handles the timing.
*   **Hardware Required**: 
    *   3.5mm AUX Cable (cut one end to expose wires).
    *   Laser Diode Module (most cheap 5V lasers work).
    *   Transistor (e.g., NPN 2N2222) or a Laser Driver Circuit.
*   **Connection**:
    *   **PC Line Out (L/R)** -> Resistor (1k) -> **Transistor Base**.
    *   **Transistor Collector** -> **Laser (-) Terminal**.
    *   **Laser (+) Terminal** -> **5V Power Supply**.
    *   **Transistor Emitter** -> **Ground (GND)**.
    *   *Note: Connect PC GND to Hardware GND.*

### Option B: Arduino (Serial) Connection
*   **Hardware Required**: Arduino Uno/Nano, Laser Module.
*   **Arduino Code**:
    ```cpp
    // Li-Fi Simple Serial Laser Driver
    const int LASER_PIN = 13;

    void setup() {
      Serial.begin(115200);
      pinMode(LASER_PIN, OUTPUT);
    }

    void loop() {
      if (Serial.available()) {
        char bit = Serial.read();
        if (bit == '1') digitalWrite(LASER_PIN, HIGH);
        else if (bit == '0') digitalWrite(LASER_PIN, LOW);
      }
    }
    ```
*   **Connection**: Arduino Pin 13 -> Laser (+), Arduino GND -> Laser (-).

---

## 2. Receiver Hardware (Solar Panel)
The receiver converts light pulses back into electrical signals.

*   **Hardware Required**: 
    *   Small Solar Panel (5V or similar).
    *   3.5mm AUX Cable (to PC Mic/Line-In).
*   **Connection**:
    *   **Solar Panel (+)** -> **AUX Tip/Ring (Left/Right channel)**.
    *   **Solar Panel (-)** -> **AUX Sleeve (Ground)**.
*   **Setup**: 
    *   Plug the AUX into your PC's **Microphone** or **Line-In** jack.
    *   Open Windows Sound Settings and ensure the level is high but not clipping.
    *   *In `receiver.py`, ensure the correct input device is selected.*

---

## 3. Best Practices
*   **Alignment**: Align the laser beam directly onto the solar panel cell.
*   **Distance**: Start with 10-50cm. Use a lens if going for long range.
*   **Ambient Light**: If the receiver is overwhelmed by room light, try shielding the solar panel with a tube or using a dark room.
