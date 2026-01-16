import streamlit as st
import minimalmodbus
import numpy as np
import time


# --- Page configuration ---
st.set_page_config(page_title="Omega CN7800 Controller", layout="wide")
st.title("Omega CN7800 Control Interface")

# --- Sidebar: Connection Settings ---
st.sidebar.header("Connection Settings")
port = st.sidebar.text_input("Serial Port", value="COM8")
slave_id = st.sidebar.number_input("Slave ID", value=1)
baud = st.sidebar.selectbox("Baudrate", [9600, 19200, 38400], index=0)


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
        list: list to split
        int: size of the chunks that will be created
    """
    for i in range(0, len(lst), n):
        yield lst[i:i+n] 


def clear_all_patterns():
    """
    Reset all existing patterns and steps to zero to avoid overlapping with
    previous runs.
    """
    print("Clearing patterns in existence")

    TOTAL_PATTERNS = 8
    STEPS_PER_PATTERN = 8

    for p in range(TOTAL_PATTERNS):
        for s in range(STEPS_PER_PATTERN):
            temp_reg = int("0x2000", 0) + p * 8 + s
            time_reg = int("0x2080", 0) + p * 8 + s

            # Set temperature and time to zero
            safe_write(temp_reg, 0)
            safe_write(time_reg, 0)

        # Set number of steps to 0
        safe_write(0x1040 + p, 0)

        # Set cycle count to 0
        safe_write(0x1050 + p, 0)

        # Set pattern link to "End of Program"
        safe_write(0x1060 + p, 0x08)

    print("All patterns cleared.")

    

# --- UI Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Monitoring")
    
    # 1. Add the Refresh Button
    if st.button("Refresh Live Values", use_container_width=True):
        # In Streamlit, clicking a button automatically reruns the script,
        # fetching the new values from the hardware below.
        st.rerun()

    if instrument:
        try:
            # 2. Fetch the data
            pv = instrument.read_register(0x1000, 1)
            sv = instrument.read_register(0x1001, 1)
            
            # 3. Display with Metrics
            st.metric("Current Temp (PV)", f"{pv} °C")
            st.metric("Target Setpoint (SV)", f"{sv} °C")
            
            # Show the last update time
            st.caption(f"Last updated: {time.strftime('%H:%M:%S')}")
            
        except Exception as e:
            st.error(f"Communication Error: {e}")
            st.warning("Ensure the PID is powered on and the COM port is correct.")
    else:
        st.info("Waiting for connection...")

    st.divider()

    # 4. Stop Button
    if st.button("STOP PROGRAM", use_container_width=True, type="primary"):
        if instrument:
            instrument.write_bit(0x0814, 0)
            st.warning("Heater Output Forced to STOP.")
            st.rerun()


with col2:
    tab1, tab2, tab3, tab4 = st.tabs(["Parameters Preset", "Ramp Programmer", "PID Mode Programmer", "User Documentation"])

    # --- TAB 1: PARAMETERS PRESET ---
    with tab1:
        st.write("### PID Group Selection")
        
        # Select the active PID Group (0 to 3)
        # Register 0x101C: PID parameter selection
        selected_group = st.radio(
            "Select PID Preset Group", 
            options=[0, 1, 2, 3], 
            horizontal=True,
            help="Choose which PID parameter set the controller should use."
        )

        if st.button("Activate Selected Preset"):
            if safe_write(0x101C, selected_group):
                st.success(f"Controller is now using PID Group {selected_group}")

        st.divider()

        st.write(f"### Configure PID Values for Group {selected_group}")
        
        # When reading/writing P, I, D, the register addresses often change based on the group.
        # However, for most Omega CN models, writing to 1009-100B updates the *currently active* group.
        
        if st.button("Fetch Values from PID"):
            try:
                # Read current group's values
                pb = instrument.read_register(0x1009, 1) / 10.0
                ti = instrument.read_register(0x100A, 0)
                td = instrument.read_register(0x100B, 0)
                
                st.session_state['pb'] = pb
                st.session_state['ti'] = ti
                st.session_state['td'] = td
                st.rerun()
            except Exception as e:
                st.error(f"Read Error: {e}")

        c1, c2, c3 = st.columns(3)
        new_pb = c1.number_input("Proportional (P)", value=st.session_state.get('pb', 47.0), key="p_input")
        new_ti = c2.number_input("Integral (I)", value=st.session_state.get('ti', 240), key="i_input")
        new_td = c3.number_input("Derivative (D)", value=st.session_state.get('td', 60), key="d_input")

        if st.button("Save Settings to this Preset"):
            # First, make sure the controller is pointing to the right group
            safe_write(0x101C, selected_group)
            # Then write the values
            safe_write(0x1009, int(new_pb * 10))
            safe_write(0x100A, int(new_ti))
            safe_write(0x100B, int(new_td))
            st.success(f"Parameters saved to Group {selected_group}!")

    # --- TAB 2: RAMP PROGRAMMER ---
    with tab2:
        st.subheader("Ramp Configuration")
        
        # 1. Manual Implementation of Variables
        col_params_1, col_params_2 = st.columns(2)
        
        with col_params_1:
            # Replaces TOTAL_STEPS
            ui_total_steps = st.slider("Total Number of Steps", 2, 64, 10)
            # Replaces FINAL_TEMPERATURE
            ui_final_temp = st.number_input("Final Target Temperature (°C)", min_value=0, max_value=800, value=100)
        
        with col_params_2:
            # Replaces TIME_BETWEEN_STEPS
            ui_time_step = st.number_input("Time per Step (minutes)", min_value=1, value=20)
            # Replaces TIME_FIRST_STEP
            ui_first_step_time = st.number_input("First Step Duration (to avoid overshoot)", value=1)

        # 2. Visual Preview
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

        # 3. Programming Logic
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

    
    with tab3:
        st.subheader("PID Mode Programmer")
        
        # 1. Static Setpoint Control
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

        # 2. Autotuning Control
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

        # 3. Execution
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


    with tab4:
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