import streamlit as st
import pandas as pd
import requests
import datetime
import re
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import os


PICO_METRICS_URL = "http://192.168.10.10:8080/metrics"
METRIC_NAME = "graphix_pressure_value"
METRIC_UNIT = "Pa"
REFRESH_INTERVAL_MS = 5000
Y_AXIS_MIN = 980.0
Y_AXIS_MAX = 1020.0
DATA_FILE_PATH = "../data/pressure_log.csv"


if 'data_history' not in st.session_state:
    st.session_state['data_history'] = pd.DataFrame(columns=['Timestamp', f'Pression ({METRIC_UNIT})'])
    st.session_state['last_value'] = None
    st.session_state['status'] = "Starting"


def save_to_csv(timestamp, pressure_value):
    log_data = pd.DataFrame({
        'Timestamp' : [timestamp.strftime('%Y-%m-%d %H:%M:%S')],
        f'Pressure ({METRIC_UNIT})': [pressure_value]
    })

    file_exists = os.path.isfile(DATA_FILE_PATH)

    try:
        log_data.to_csv(
            DATA_FILE_PATH, 
            mode='a', 
            header=not file_exists,
            index=False
        )
        st.session_state['Log Status'] = 'Saved OK'
    
    except Exception as e:
        st.session_state['log_status'] = f"Saving issue: {e}"
    


def fetch_and_parse(url : str, metric_name : str) -> float | None :
    try:
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        metrics_text = response.text

        pattern = re.compile(rf"^{re.escape(metric_name)}{{.*?}}\s+([0-9\.]+)", re.MULTILINE)
        match = pattern.search(metrics_text)

        if match:
            value = float(match.group(1))
            st.session_state['status'] = "Working"
            return value
        
        else :
            st.session_state['status'] = "Parsing error"
            return None
        
    except requests.exceptions.Timeout:
        st.session_state['status'] = "Timeout"
        return None
    except requests.exceptions.RequestException as e:
        st.session_state['status'] = "Failed connection"
        return None
    except Exception as e:
        st.session_state['status'] = "Unexpected error"
        return None
    

st.set_page_config(layout="wide")
st.title("Pressure Gauge reader")
st.caption(f"Gauge : `{PICO_METRICS_URL}` | Automatic read every {REFRESH_INTERVAL_MS/1000} seconds.")

st_autorefresh(interval=REFRESH_INTERVAL_MS, key="data_refresher")
st.session_state['SAVE_ACTIVE'] = st.checkbox("Activate data saving (CSV)", value=False, key="save_checkbox")


current_pressure = fetch_and_parse(PICO_METRICS_URL, METRIC_NAME)


if current_pressure is not None:

    current_time = datetime.datetime.now()
    if st.session_state['SAVE_ACTIVE']:
        save_to_csv(current_time, current_pressure)
    else:
        st.session_state['log_status'] = 'Saving deactivated'

    new_data = pd.DataFrame({
        'Timestamp':[datetime.datetime.now()],
        f'Pressure ({METRIC_UNIT})':[current_pressure]
    })

    st.session_state['data_history'] = pd.concat(
        [st.session_state['data_history'], new_data], 
        ignore_index=True
    )

    st.session_state['last_value'] = current_pressure
    history_df = st.session_state['data_history'].tail(100)


else:
    history_df = st.session_state['data_history'].tail(100)




col1, col2, col3 = st.columns([1, 3, 1])



with col1:
    metric_label = f"Current pressure ({METRIC_UNIT})"
    st.metric(
        label=metric_label,
        value=f"{st.session_state['last_value']:.3f}" if st.session_state['last_value'] is not None else "N/A",
        delta="Starting" if st.session_state['last_value'] is None else None
    )   

    status_color = "green" if st.session_state['status'] == "Working" else "red"
    st.markdown(f"**Status:** :{status_color}[{st.session_state['status']}]")
    st.caption(f"Last update: {datetime.datetime.now().strftime('%H:%M:%S')}")

    st.markdown(f"**Log Status:** {st.session_state.get('log_status', 'N/A')}")


with col2:
    if not history_df.empty:
            plot_df = history_df.copy()
            y_column_name = f'Pressure ({METRIC_UNIT})'
            
            fig = px.line(
                plot_df, 
                x='Timestamp', 
                y=y_column_name,
                title="Pressure values along time",
                template="plotly_white" 
            )


            fig.update_yaxes(
                range=[Y_AXIS_MIN, Y_AXIS_MAX],
                title=y_column_name
            )
            

            fig.update_xaxes(
                title="Time"
            )
            

            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Waiting for the first value...")

with col3:
    st.download_button(
        label="Download Log CSV",
        data=open(DATA_FILE_PATH, 'rb').read() if os.path.exists(DATA_FILE_PATH) else "",
        file_name = DATA_FILE_PATH, 
        mime='text/csv',
        disabled=not os.path.exists(DATA_FILE_PATH),
    )
    st.warning("Warning : if the file is too voluminous the download can be too long")

with st.expander("History of the last 100 values (Raw Data)"):
    st.dataframe(history_df, use_container_width=True)
    