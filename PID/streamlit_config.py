"""
This code is designed to set up an ergonomic interface to communicate with a CN7800 Omega PID, 
using Streamlit. 
You can find all the documentation concerning the PID at:
https://assets.omega.com/manuals/M4704.pdf

The precise details of the implemented functionnalities are actually directly accessible in the 
"User Description" tab once the code is executed. 

To run the code, you only need to run : 
"streamlit run path/to/file.py" in your powershell and the interface will automatically pop up. 
"""

import streamlit as st
import minimalmodbus
import numpy as np
import time
import pandas as pd
from datetime import datetime
from streamlit_autorefresh import st_autorefresh


# --- Page configuration ---
st.set_page_config(page_title="Omega CN7800 Controller", layout="wide")
st.title("Omega CN7800 Control Interface")


# --- Initialize Session State for Logging ---
if 'log_data' not in st.session_state:
    st.session_state['log_data'] = pd.DataFrame(columns=["Timestamp", "PV", "SV"])
if 'p_input' not in st.session_state:
    st.session_state['p_input'] = 47.0
if 'i_input' not in st.session_state:
    st.session_state['i_input'] = 240
if 'd_input' not in st.session_state:
    st.session_state['d_input'] = 60


# --- Sidebar: Connection Settings ---
st.sidebar.header("Connection Settings")
port = st.sidebar.text_input("Serial Port", value="COM8")
slave_id = st.sidebar.number_input("Slave ID", value=1)
baud = st.sidebar.selectbox("Baudrate", [9600, 19200, 38400], index=0)

st.sidebar.divider()
st.sidebar.header("Data Logger Settings")
logging_active = st.sidebar.toggle("Enable Live Logging", value=False)
log_interval = st.sidebar.number_input("Acquisition Interval (sec)", min_value=0.1, max_value=120.0, value=1.0, step=0.1)

if st.sidebar.button("Clear Log History"):
    st.session_state["log_data"] = pd.DataFrame(columns=["Timestamp", "PV", "SV"])
    st.rerun()  


# --- Instrument Initialization ---
@st.cache_resource
def get_instrument(port, slave_id, baud):
    """
    Check the serial connection and setup the instrument object.
    Args:
        port (str): Name of the serial port, format can differ between Windows and Linux
        slave_id (int): Slave ID of the target device
        vaud (int): Baudrate of the device, can usually be found in the manual
    """
    try:
        instr = minimalmodbus.Instrument(port, slave_id)
        instr.serial.baudrate = baud
        instr.serial.timeout = 0.5
        instr.serial.parity = minimalmodbus.serial.PARITY_EVEN
        instr.mode = minimalmodbus.MODE_RTU
        return instr
    except Exception as e:
        st.error(f"Connection Failed: {e}")
        return None
    

instrument = get_instrument(port, slave_id, baud)


# --- Autorefresh Logic ---
if logging_active:
    st_autorefresh(interval=log_interval * 1000, key="data_pull")


# --- Shared Functions ---
def safe_write(register, value):
    """
    Writes a value to a given register with a retry mechanism to handle interference.
    Args:
        register (int): Hex address of the register
        value (int): value to write 
    """
    try:
        instrument.write_register(register, value)
        return True
    except Exception as e:
        st.error(f"Write Error on {hex(register)}: {e}")
        return False


def chunk(lst, n):
    """
    Split the total list into chunks of size n
    Args:
        lst (list): list to split
        n (int): size of the chunks that will be created
    """
    for i in range(0, len(lst), n):
        yield lst[i:i+n] 




def find_program_end(instrument):
    """
    Returns (pattern_index, step_index) where the next step should be written.
    Raises RuntimeError if memory is full or no program exists.
    """
    last_used_pattern = None

    # Find the last pattern that actually contains steps
    for p_idx in range(8):
        steps_minus_one = instrument.read_register(0x1040 + p_idx, 0)
        if steps_minus_one >= 0:
            if steps_minus_one > 0 or p_idx == 0:
                if steps_minus_one > 0:
                    last_used_pattern = p_idx

    if last_used_pattern is None:
        raise RuntimeError("No existing program found. Upload a ramp first.")

    steps_minus_one = instrument.read_register(0x1040 + last_used_pattern, 0)

    # If there is room in the current pattern
    if steps_minus_one < 7:
        return last_used_pattern, steps_minus_one + 1

    # Otherwise, move to the next pattern
    if last_used_pattern >= 7:
        raise RuntimeError("Memory full: 64 steps reached.")

    # Link previous pattern to next
    safe_write(0x1060 + last_used_pattern, last_used_pattern + 1)

    return last_used_pattern + 1, 0


def resume_from_step(pattern_idx, step_idx):
    """
    Resume execution starting from a specific pattern/step.
    Used only when PID is not running.
    """
    safe_write(0x1030, pattern_idx)  # Start Pattern
    safe_write(0x1031, step_idx)     # Start Step
    instrument.write_bit(0x0814, 1)  # RUN



def is_program_actively_running():
    """
    Returns True if the PID program is actively executing steps.
    Returns False if the program has ended (PTsP / maintain).
    """

    current_pattern = instrument.read_register(0x1030, 0)
    current_step = instrument.read_register(0x1031, 0)

    # Find last programmed pattern
    last_pattern = None
    for p in range(8):
        steps = instrument.read_register(0x1040 + p, 0)
        if steps > 0 or p == 0:
            if steps > 0:
                last_pattern = p

    if last_pattern is None:
        return False

    last_step = instrument.read_register(0x1040 + last_pattern, 0)

    # If execution pointer is beyond program end → PTsP
    if current_pattern > last_pattern:
        return False
    if current_pattern == last_pattern and current_step > last_step:
        return False

    return True



def clear_all_patterns():
    """
    Fully reset program memory AND execution state
    """
    print("Clearing patterns in existence")

    # STOP execution and reset pointers
    instrument.write_bit(0x0814, 0)  # STOP
    safe_write(0x1030, 0)            # Pattern pointer
    safe_write(0x1031, 0)            # Step pointer

    TOTAL_PATTERNS = 8
    STEPS_PER_PATTERN = 8

    for p in range(TOTAL_PATTERNS):
        for s in range(STEPS_PER_PATTERN):
            safe_write(0x2000 + p * 8 + s, 0)  # Temp
            safe_write(0x2080 + p * 8 + s, 0)  # Time

        safe_write(0x1040 + p, 0)   # Steps
        safe_write(0x1050 + p, 0)   # Cycles
        safe_write(0x1060 + p, 0x08)  # End of program

    print("All patterns cleared.")

    

# --- UI Layout ---
st.title("Omega CN7800 Control & Logging Interface")
col1, col2 = st.columns([1, 2])


# --- Hardware Reading ---
pv, sv = 0.0, 0.0
if instrument:
    try:
        pv_raw = instrument.read_register(0x1000, 0)
        sv_raw = instrument.read_register(0x1001, 0)

        pv = float(pv_raw) / 10.0
        sv = float(sv_raw) / 10.0
        
        # Display with 1 decimal place
        st.metric("Current Temp (PV)", f"{pv:.1f} °C")
        st.metric("Target Setpoint (SV)", f"{sv:.1f} °C")
        
        # Append to log if active
        if logging_active:
            new_entry = pd.DataFrame({
                "Timestamp": [datetime.now().strftime("%H:%M:%S")], 
                "PV": [pv], 
                "SV": [sv]
            })
            st.session_state['log_data'] = pd.concat([st.session_state['log_data'], new_entry], ignore_index=True)

    except Exception as e:
        st.sidebar.warning(f"Poll Error: {e}")

with col1:
    st.subheader("Monitoring")
    m1, m2 = st.columns(2)
    m1.metric("Current PV", f"{pv} °C")
    m2.metric("Target SV", f"{sv} °C")

    # Live Chart
    if not st.session_state['log_data'].empty:
        st.line_chart(st.session_state['log_data'].set_index("Timestamp"))
    
    # Export Options
    st.write("### Data Export")
    if not st.session_state['log_data'].empty:
        csv = st.session_state['log_data'].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Log as .txt / .csv",
            data=csv,
            file_name=f"PID_Log_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime='text/csv',
            use_container_width=True
        )

    if st.button("STOP PROGRAM", use_container_width=True, type="primary"):
        if instrument:
            instrument.write_bit(0x0814, 0)
            st.warning("Heater Output Forced to STOP.")


with col2:
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Parameters Preset", "Ramp Programmer", "PID Mode Programmer", "Alarm Setup", "User Documentation"])

    # --- TAB 1: PID Parameters Preset ---
    with tab1:
        st.write("### PID Group Selection")
        
        # Select the active PID Group (0 to 4)
        # Options 0-3 are manual presets, 4 is Auto PID
        selected_group = st.radio( 
            "Select PID Preset Group", 
            options=[0, 1, 2, 3, 4], 
            format_func=lambda x: f"Group {x}" if x < 4 else "Group 4 (Auto PID)",
            horizontal=True,
            help="Choose which PID parameter set the controller should use."
        )

        # Boolean to check if the 4th preset (Auto) is selected
        is_auto_mode = (selected_group == 4)

        if st.button("Activate Selected Preset"):
            if safe_write(0x101C, selected_group):
                st.success(f"Controller is now using {'Auto PID' if is_auto_mode else f'PID Group {selected_group}'}")

        st.divider()

        st.write(f"### Configure PID Values for Group {selected_group}")
        
        # If in Auto Mode, we grey out the fetch button
        if st.button("Fetch Values from PID", disabled=is_auto_mode):
            try:
                pb = instrument.read_register(0x1009, 1) 
                ti = instrument.read_register(0x100A, 0)
                td = instrument.read_register(0x100B, 0)
                
                st.session_state['p_input'] = instrument.read_register(0x1009, 1) 
                st.session_state['i_input'] = instrument.read_register(0x100A, 0)
                st.session_state['d_input'] = instrument.read_register(0x100B, 0)
                st.rerun()  
            except Exception as e:
                st.error(f"Read Error: {e}")

        # Disable the inputs if in Auto Mode
        c1, c2, c3 = st.columns(3)
        new_pb = c1.number_input("Proportional (P)", value=st.session_state.get('pb', 47.0), key="p_input", disabled=is_auto_mode)
        new_ti = c2.number_input("Integral (I)", value=st.session_state.get('ti', 240), key="i_input", disabled=is_auto_mode)
        new_td = c3.number_input("Derivative (D)", value=st.session_state.get('td', 60), key="d_input", disabled=is_auto_mode)

        # Disable the save button if in Auto Mode
        if st.button("Save Settings to this Preset", disabled=is_auto_mode):
            safe_write(0x101C, selected_group)
            safe_write(0x1009, int(new_pb * 10))
            safe_write(0x100A, int(new_ti))
            safe_write(0x100B, int(new_td))
            st.success(f"Parameters saved to Group {selected_group}!")
        
        if is_auto_mode:
            st.info("Manual adjustments are disabled in Auto PID mode.")


    # --- TAB 2: Ramp Programmer ---
    with tab2:
        st.subheader("Ramp Configuration")
        
        col_params_1, col_params_2 = st.columns(2)
        
        with col_params_1:
            # Add buttons to set the parameters of the ramp.
            ui_total_steps = st.slider("Total Number of Steps", 2, 64, 10)
            ui_final_temp = st.number_input("Final Target Temperature (°C)", min_value=0, max_value=800, value=100)
        
        with col_params_2:
            ui_time_step = st.number_input("Time per Step (minutes)", min_value=1, value=20)
            ui_first_step_time = st.number_input("First Step Duration (to avoid overshoot)", value=1)

        # Visual Preview of the ramp
        if st.button("Preview Ramp Curve"):
            try:
                room_temp = instrument.read_register(0x1000, 1)
                # Logic: Start at PV+1, then linear to Final Temp
                y = np.linspace(room_temp + 1, ui_final_temp, ui_total_steps)
                st.line_chart(y)
                st.caption(f"Ramp: {room_temp+1}°C → {ui_final_temp}°C over {ui_total_steps * ui_time_step} total minutes.")
            except:
                st.error("Connect to PID to preview with live Room Temperature.")

        st.divider()

        # Ramp implementation
        if st.button("Upload & Run Ramp", type="primary"):
            with st.spinner("Programming PID... This may take a moment."):
                try:
                    # Initialize Program Mode
                    safe_write(0x1005, 3) 
                    instrument.write_bit(0x0813, 0) 
                    clear_all_patterns()

                    # Generate Temperatures locally using UI variables
                    room_temp = instrument.read_register(0x1000, 1)
                    first_target = float(room_temp) + 1.0
                    temperatures = np.linspace(first_target, ui_final_temp, ui_total_steps).tolist()

                    # Split into patterns of 8
                    patterns = list(chunk(temperatures, 8))

                    count = 0
                    for p_idx, steps in enumerate(patterns):
                        for s_idx, T in enumerate(steps):
                            temp_reg = 0x2000 + p_idx * 8 + s_idx
                            time_reg = 0x2080 + p_idx * 8 + s_idx
                            
                            # Write Temperature (Temp * 10)
                            safe_write(temp_reg, int(round(T * 10)))

                            # Write Time
                            current_duration = ui_first_step_time if count == 0 else ui_time_step
                            safe_write(time_reg, current_duration)
                            count += 1

                        # Pattern Metadata
                        safe_write(0x1040 + p_idx, len(steps) - 1) # Steps in pattern
                        safe_write(0x1050 + p_idx, 0)             # Cycles
                        
                        # Linking logic
                        link_reg = 0x1060 + p_idx
                        if p_idx == len(patterns) - 1:
                            safe_write(link_reg, 0x08) # Stop at end
                        else:
                            safe_write(link_reg, p_idx + 1) # Link to next

                    # Start Execution
                    safe_write(0x1030, 0) # Start Pattern 0
                    safe_write(0x1031, 0) # Start Step 0
                    instrument.write_bit(0x0814, 1) # Set to RUN

                    st.success(f"Ramp started: {ui_total_steps} steps uploaded successfully.")
                
                except Exception as e:
                    st.error(f"Failed to program: {e}")
        
        st.divider()
        st.subheader("Extend Existing Ramp")
        st.info("This will add a single step to the end of the current sequence without clearing existing data.")

        col_sub1, col_sub2 = st.columns(2)
        with col_sub1:
            ui_sub_temp = st.number_input("Subsequent Target Temp (°C)", min_value=0, max_value=800, value=150)
        with col_sub2:
            ui_sub_time = st.number_input("Subsequent Duration (min)", min_value=1, value=20)

        if st.button("Add Step to Program"):
            if instrument:
                try:
                    # 1. Detect whether program is actively running
                    program_running = is_program_actively_running()

                    # 2. Append new step
                    target_p, target_s = find_program_end(instrument)

                    temp_reg = 0x2000 + target_p * 8 + target_s
                    time_reg = 0x2080 + target_p * 8 + target_s

                    safe_write(temp_reg, int(ui_sub_temp * 10))
                    safe_write(time_reg, int(ui_sub_time))

                    safe_write(0x1040 + target_p, target_s)
                    safe_write(0x1060 + target_p, 0x08)

                    # 3. Resume ONLY if program had ended (PTsP)
                    if not program_running:
                        instrument.write_bit(0x0814, 0)   # STOP (required)
                        safe_write(0x1030, target_p)
                        safe_write(0x1031, target_s)
                        instrument.write_bit(0x0814, 1)   # RUN

                        st.success(
                            f"Step added → resumed from Pattern {target_p}, Step {target_s}"
                        )
                    else:
                        st.success(
                            f"Step added → program already running"
                        )

                except Exception as e:
                    st.error(f"Error extending ramp: {e}")




    # --- TAB 3: PID Mode Programmer ---
    with tab3:
        st.subheader("PID Mode Programmer")
        
        # Static Setpoint Control
        st.markdown("### Target Setpoint")
        col_sv1, col_sv2 = st.columns([3, 1])
        
        with col_sv1:
            new_sv = st.number_input("Set Target Temperature (°C)", min_value=0.0, max_value=800.0, value=25.0, step=0.1)
        with col_sv2:
            if st.button("Update SV", use_container_width=True):
                try:

                    # Omega uses (Temp * 10) for register 0x1001 (Setpoint SV)
                    if safe_write(0x1001, int(new_sv * 10)):
                        st.success(f"Setpoint updated to {new_sv}°C")
                
                except Exception as e:
                    st.error(f"Failed to update: {e}")
        
        st.divider()

        # Autotuning Control
        st.markdown("### Autotuning (AT)")
        st.info("Autotuning will oscillate the temperature around the setpoint to calculate ideal P, I, and D values.")
        
        col_at1, col_at2 = st.columns(2)
        
        with col_at1:
            if st.button("Start Autotuning", type="secondary", use_container_width=True):
                if instrument:
                    try:
                        instrument.write_bit(0x0813, 1)
                        st.warning("Autotuning Started.")
                    except Exception as e:
                        st.error(f"Failed to start AT: {e}")
                else:
                    st.error("Not connected to instrument.")

        with col_at2:
            if st.button("Stop Autotuning", type="secondary", use_container_width=True):
                if instrument:
                    try:
                        instrument.write_bit(0x0813, 0)
                        st.success("Autotuning Stopped.")
                    except Exception as e:
                        st.error(f"Failed to stop AT: {e}")

        # Execution
        st.markdown("### Execution")

        if st.button("Upload and Run", type="primary", use_container_width=True):
            try:
                # Force the controller into 'PID Control' mode (Value 0)
                safe_write(0x1005, 0)

                # Set the RUN bit (0x0814) to 1
                instrument.write_bit(0x0814, 1)

                st.success("Controller set to PID Mode and Started!")
            
            except Exception as e:
                st.error(f"Critical Error starting program: {e}")
    
    # --- TAB 4: Alarm Settings ---
    with tab4:
        st.subheader("Safety Alarm Settings")
        st.info("Configuration : Alarm is **ON** while Temperature < Upper Limit.")

        col_al1, col_al2 = st.columns(2)
        with col_al1:
            alarm_threshold = st.number_input("Alarm Threshold (°C)", min_value=0.0, max_value=800.0, value=50.0)
        with col_al2:
            alarm_channel = st.selectbox("Select Alarm Channel", options=[1,2,3], index=0)

        if st.button("Set Safety Alarm"):
            if instrument:
                try:
                    type_reg = 0x1020 + (alarm_channel - 1)
                    limit_reg = 0x1025 +((alarm_channel - 1) * 2)

                    safe_write(type_reg, 7)

                    safe_write(limit_reg, int(alarm_threshold * 10))

                    st.success(f"Alarm {alarm_channel} configured! It will turn OFF above {alarm_threshold}°C.")
                
                except Exception as e:
                    st.error(f"Failed to set alarm: {e}")
            else:
                st.error("Instrument not connected.")

    # --- TAB 5: User Documentation ---
    with tab5:
        st.header("User Documentation")

        st.subheader("Connection Settings")
        st.write("The sidebar allows to quickly set up the connection with the PID : \n\n - **Serial Port** : By default COM8. If you have a Linux, this should look like **/dev/tty**. \n\n - **Slave Address** : By default 1, needs to be changed if multiple devices are connected to the same port. \n\n - **Baudrate** : Speed of communication of the device. Can be checked on the manual, usually (9600, 115200).")

        st.subheader("Monitoring and Safety")
        st.write("The left column shows live data. Please note that the value needs to be manually updated through the **Refresh Live Values** button. \n\n Use the **STOP PROGRAM** button to immediately stop the PID heating in case of emergency.")

        st.subheader("Parameters Preset")
        st.write("This tab allows to set the PID parameters (P, Ti, Td) for each of the possible preset, ranging from 0~3. For each of the preset, you can read the already assigned value through the **Fetch Values from PID** button, or set new parameters using the **Save Settings to this Preset** button. \n\n The 4th preset allows the PID to automatically choose what preset is the most optimal.")

        st.subheader("Ramp Programmer")
        st.write("This tab allows the user to set up and run a ramp. The first step is always exactly one degrees above room temperature to avoid PID overshooting. You can plot the ramp before running it to check its coherence, using the **Preview Ramp Curve** button. Using the **Upload and Run** button will automatically set the PID in programming mode and will start running the code. \n\n Please note that only linear ramps are currently implemented.")

        st.subheader("PID Mode Programmer")
        st.write("Allows to set a target value using PID mode. You can enable or disable AT (Auto-tuning) while the code is running without issue. Please note that pressing the **Upload and Run** button will automatically set the PID in PID mode and start running the code.")

        st.subheader("Safety Alarm Settings")
        st.write("Allows to setup an alarm.")