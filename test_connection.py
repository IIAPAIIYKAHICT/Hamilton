import serial
import time
import logging
from datetime import datetime
import os

# --- Logger setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
file_handler = logging.FileHandler('hamilton_hl7_log.log', mode='w', encoding='utf-8')
file_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if (logger.hasHandlers()):
    logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# --- KONFIGURACJA / CONFIGURATION ---
SERIAL_PORT = 'COM3' 
BAUD_RATE = 38400
RECONNECT_DELAY = 10
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PATIENT_ID = "PATIENT_12345"  # <--- Enter patient id here
HL7_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "hl7_messages")

# --- Hamilton Protocol Constants ---
STX = 0x02
ETX = 0x03
CR = 0x0D
VT = 0x0B
CMD_ACTIVATE_MIXED_MODE = 0x31
SEND_TIMED_ONLY = 0x30
SEND_ONCE = 0x31
SEND_BREATH_BY_BREATH = 0x32
SEND_ON_CHANGE = 0x33

GROUP_IDS = {
    0x40: "Identifications",
    0x41: "SW-Versions",
    0x50: "Monitored Parameters",
    0x60: "Active Alarms",
    0x70: "Control Settings",
}

PARAMETER_MAP = {
    "Monitored Parameters": {
        0x20: "Breath Number",
        0x21: "P max",
        0x22: "P Plateau",
        0x23: "P mean",
        0x24: "PEEP/CPAP",
        0x25: "P min",
        0x2C: "Exp. Volume",
        0x2E: "Vexp/min",
        0x30: "f total",
        0x34: "I:E ratio",
        0x37: "Compliance",
        0x3E: "Oxygen",
        0x4E: "Pulse",
        0x4F: "SpO2",
    },
    "Control Settings": {
        0x22: "Mode Name",
    }
}

# --- MAPPING: Hamilton Parameter Name -> HL7 Key ---
VENTILATOR_TO_HL7_MAP = {
    'P max': 'MPAP',        # Maximum Positive Airway Pressure
    'P mean': 'MEAP',       # Mean airway pressure
    'P min': 'MIAP',        # Minimum Airway Pressure
    'PEEP/CPAP': 'PEEP',
    'Exp. Volume': 'TDLV',  # Tidal Volume Expired
    'Vexp/min': 'EXPM',     # EXP - Minute Volume
    'f total': 'RRM',       # Respiratory Rate
    'I:E ratio': 'IER',
    'Oxygen': 'FIO2',
    'SpO2': 'SAT',          # Oxygen Saturation
    'Pulse': 'HR',
    'Mode Name': 'VENM'     # Ventilation Mode
}

# --- MAPPING: HL7 Key -> HL7 OBX Identifier (LOINC codes) ---
HL7_IDENTIFIER_MAP = {
    'MPAP': '3002-3^Maximum Positive Airway Pressure',
    'MEAP': '3002-6^Mean airway pressure',
    'MIAP': '3002-2^Minimum Airway Pressure',
    'PEEP': '3005-4^PEEP',
    'TDLV': 'LP73863-0^Tidal Volume Expired',
    'EXPM': '76008-2^EXP - Minute Volume',
    'RRM': '9279-2^Respiratory_Rate',
    'IER': '3008-1^I:E Ratio',
    'FIO2': '3008-7^FIO2',
    'SAT': '59408-5^oxygen_saturation',
    'HR': '8867-4^HR_Pulse',
    'VENM': '3008-3^Ventilation Mode'
}


def crc8(data: bytes) -> int:
    """Calculate CRC-8 with polynomial 0xD5."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0xD5
            else:
                crc <<= 1
    return crc & 0xFF

def build_activate_mixed_mode_command():
    """Builds the command to request all specified data groups."""
    payload = bytearray([0x30])  # 0x30 = Waveforms OFF
    
    groups_to_request = {
        0x50: (SEND_BREATH_BY_BREATH, 0), # Monitored Parameters (breath-by-breath)
        0x70: (SEND_ON_CHANGE, 0),        # Control Settings (on change)
    }

    for group_id, (send_state, repeat_timer) in groups_to_request.items():
        payload.append(group_id)
        payload.append(send_state)
        payload.extend(f"{repeat_timer:03d}".encode('ascii'))
        
    command_body = bytes([CMD_ACTIVATE_MIXED_MODE]) + payload
    full_packet_for_crc = bytes([STX]) + command_body + bytes([ETX])
    checksum = crc8(full_packet_for_crc)
    final_command = full_packet_for_crc + f"{checksum:02X}".encode('ascii') + bytes([CR])
    return final_command

def generate_and_save_hl7_message(data: dict):
    """Builds an HL7 message from the collected data and saves it to a file."""
    if not data:
        logger.warning("No data to generate HL7 message.")
        return

    now = datetime.now()
    date_str = now.strftime('%Y%m%d%H%M%S')
    
    # MSH Segment
    msh = f'MSH|^~\\&|HAMILTON_VENT||||{date_str}||ORU^R01^ORU_R01|{date_str}|P|2.4|||||||||'
    
    # PID Segment
    pid = f'PID|||{PATIENT_ID}'
    
    # ORC Segment
    orc = 'ORC|NW|||||||||||||||||Hamilton_Ventilator'
    
    # OBR Segment
    obr = f'OBR|||||||{date_str}||||||||||||||||||||||||||||'
    
    message_parts = [msh, pid, orc, obr]
    obx_index = 1
    
    # Create OBX segments for each mapped parameter
    for ventilator_name, hl7_key in VENTILATOR_TO_HL7_MAP.items():
        # Find the value in the collected data
        value = None
        for group_data in data.values():
            if ventilator_name in group_data:
                value = group_data[ventilator_name]
                break
        
        if value is not None and value.strip() != '':
            obx_identifier = HL7_IDENTIFIER_MAP.get(hl7_key, f'^^^^^{hl7_key}')
            obx = f'OBX|{obx_index}||{obx_identifier}||{value}'
            message_parts.append(obx)
            obx_index += 1
            
    hl7_message = '\n'.join(message_parts)
    
    # Save the message to a file
    try:
        if not os.path.exists(HL7_OUTPUT_DIR):
            os.makedirs(HL7_OUTPUT_DIR)
            logger.info(f"Created output directory: {HL7_OUTPUT_DIR}")
            
        filename = f"HL7_{now.strftime('%Y%m%d_%H%M%S_%f')}.hl7"
        filepath = os.path.join(HL7_OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(hl7_message)
        logger.info(f"Successfully generated HL7 file: {filename}")

    except Exception as e:
        logger.error(f"Failed to save HL7 file: {e}")


def parse_packet_and_trigger_hl7(data_bytes, ventilator_data: dict):
    """
    Parses parameter data, updates the main data dictionary, and triggers
    HL7 generation when a new breath number is detected.
    """
    param_chunks = data_bytes.split(bytes([VT]))
    
    # Store the breath number before parsing new data
    old_breath_number = ventilator_data.get("Monitored Parameters", {}).get("Breath Number")
    
    for chunk in param_chunks:
        if not chunk or chunk[1] == 0xFF:  # Skip empty chunks and group end markers
            continue
            
        group_id = chunk[0]
        param_id = chunk[1]
        value = chunk[2:].decode('ascii', errors='ignore').strip()
        
        group_name = GROUP_IDS.get(group_id)
        if not group_name:
            continue
            
        param_name = PARAMETER_MAP.get(group_name, {}).get(param_id)
        if not param_name:
            continue

        # Update the central data dictionary
        ventilator_data.setdefault(group_name, {})[param_name] = value

    # Check if a new breath has occurred to trigger HL7 generation
    new_breath_number = ventilator_data.get("Monitored Parameters", {}).get("Breath Number")

    if new_breath_number and new_breath_number != old_breath_number:
        logger.info(f"New breath detected (No. {new_breath_number}). Generating HL7 message.")
        # Pass a copy of the data to avoid issues with ongoing updates
        generate_and_save_hl7_message(ventilator_data.copy())

def main():
    """Main program loop."""
    ser = None
    try:
        logger.info(f"Attempting to connect to port {SERIAL_PORT}...")
        ser = serial.Serial(
            port=SERIAL_PORT, baudrate=BAUD_RATE, bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.1
        )
        logger.info(f"Successfully connected to {SERIAL_PORT}.")
        
        buffer = bytearray()
        last_command_time = 0
        ventilator_data = {}
        
        while True:
            # Resend activation command periodically to ensure connection stays active
            if time.time() - last_command_time > 30:
                command_to_send = build_activate_mixed_mode_command()
                logger.info(f"Sending Activate Mixed Mode command: {command_to_send.hex(' ')}")
                ser.write(command_to_send)
                last_command_time = time.time()

            if ser.in_waiting > 0:
                buffer.extend(ser.read(ser.in_waiting))

            stx_pos = buffer.find(STX)
            if stx_pos != -1:
                cr_pos = buffer.find(CR, stx_pos)
                if cr_pos != -1:
                    packet = buffer[stx_pos : cr_pos + 1]
                    buffer = buffer[cr_pos + 1:] # Remove processed packet from buffer

                    etx_pos = packet.find(ETX)
                    if etx_pos == -1 or etx_pos > len(packet) - 4:
                        logger.warning(f"Discarding frame with invalid ETX: {packet.hex(' ')}")
                        continue

                    packet_for_crc = packet[:etx_pos + 1]
                    received_crc_hex = packet[etx_pos + 1 : -1]
                    
                    try:
                        received_crc = int(received_crc_hex, 16)
                        calculated_crc = crc8(packet_for_crc)

                        if received_crc != calculated_crc:
                            logger.error(f"CRC MISMATCH! Packet: {packet.hex(' ')}, Got: {received_crc:02X}, Expected: {calculated_crc:02X}")
                            continue 
                        
                        data_body = packet[1:etx_pos]
                        if data_body and data_body[0] == CMD_ACTIVATE_MIXED_MODE:
                            vt_pos = data_body.find(VT)
                            if vt_pos != -1:
                                parse_packet_and_trigger_hl7(data_body[vt_pos + 1:], ventilator_data)
                    
                    except (ValueError, IndexError) as e:
                        logger.error(f"Error parsing packet: {e}. Packet: {packet.hex(' ')}")
            
            time.sleep(0.01)

    except serial.SerialException as e:
        logger.error(f"Connection error: {e}. Please check the port '{SERIAL_PORT}'.")
    except KeyboardInterrupt:
        logger.info("Program terminated by user.")
    finally:
        if ser and ser.is_open:
            ser.close()
            logger.info("Port closed.")

if __name__ == '__main__':
    main()