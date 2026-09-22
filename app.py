import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import io

# --- 1. Core Scheduling Logic ---
def calculate_metrics(df, gantt_data):
    """Calculates exact OS metrics based on the final Gantt chart timeline."""
    completed_times = {}
    for block in gantt_data:
        if block['Task'] != 'IDLE':
            p_id = int(block['Task'].replace('P', ''))
            completed_times[p_id] = block['Finish']
            
    res_df = df.copy()
    res_df['Completion Time'] = res_df['Process ID'].map(completed_times)
    
    res_df['Turnaround Time'] = res_df['Completion Time'] - res_df['Arrival Time']
    res_df['Waiting Time'] = res_df['Turnaround Time'] - res_df['Burst Time']
    
    avg_arrival = res_df['Arrival Time'].mean()
    avg_completion = res_df['Completion Time'].mean()
    avg_tat = res_df['Turnaround Time'].mean()
    avg_waiting = res_df['Waiting Time'].mean()
    
    total_time = gantt_data[-1]['Finish'] if gantt_data else 0
    throughput = len(res_df) / total_time if total_time > 0 else 0
    
    return res_df, avg_arrival, avg_completion, avg_tat, throughput, avg_waiting

def simulate_scheduler(df, algo="FCFS", tq=4, high_prio_is_low_int=True):
    """Simulates CPU scheduling algorithms and generates a timeline of execution."""
    processes = df.to_dict('records')
    for p in processes:
        p['Remaining Time'] = p['Burst Time']
        
    time = 0
    gantt = []
    ready_queue = []
    
    processes.sort(key=lambda x: (x['Arrival Time'], x['Process ID']))
    unarrived = processes.copy()
    current_p = None

    while unarrived or ready_queue or current_p:
        while unarrived and unarrived[0]['Arrival Time'] <= time:
            ready_queue.append(unarrived.pop(0))
            
        if algo == "SJF":
            ready_queue.sort(key=lambda x: (x['Remaining Time'], x['Arrival Time']))
        elif algo == "SRTF":
            if current_p: ready_queue.append(current_p)
            ready_queue.sort(key=lambda x: (x['Remaining Time'], x['Arrival Time']))
            current_p = ready_queue.pop(0) if ready_queue else None
        elif algo.startswith("Priority"):
            reverse_sort = not high_prio_is_low_int
            ready_queue.sort(key=lambda x: (x['Priority'] if not reverse_sort else -x['Priority'], x['Arrival Time']))
            
        if not current_p and ready_queue:
            current_p = ready_queue.pop(0)
            
        if current_p:
            start_time = time
            
            if algo == "Round Robin":
                execute_time = min(current_p['Remaining Time'], tq)
            elif algo == "SRTF":
                next_arrival = unarrived[0]['Arrival Time'] if unarrived else float('inf')
                execute_time = min(current_p['Remaining Time'], max(1, next_arrival - time))
            else: 
                execute_time = current_p['Remaining Time']
                
            time += execute_time
            current_p['Remaining Time'] -= execute_time
            
            gantt.append(dict(Task=f"P{current_p['Process ID']}", Start=start_time, Finish=time))
            
            if current_p['Remaining Time'] == 0:
                current_p = None
            elif algo == "Round Robin" or algo == "SRTF":
                while unarrived and unarrived[0]['Arrival Time'] <= time:
                    ready_queue.append(unarrived.pop(0))
                ready_queue.append(current_p)
                current_p = None
        else:
            next_arrival = unarrived[0]['Arrival Time']
            gantt.append(dict(Task="IDLE", Start=time, Finish=next_arrival))
            time = next_arrival

    return gantt

# --- 2. Template Generation Logic ---
def generate_template_excel():
    """Generates 1500 processes randomly and returns an Excel file in memory."""
    np.random.seed(42) 
    data = {
        'Process ID': range(1, 1501),
        'Arrival Time': np.random.randint(0, 1000, 1500),
        'Burst Time': np.random.randint(1, 50, 1500),
        'Priority': np.random.randint(1, 11, 1500)
    }
    df_template = pd.DataFrame(data)
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Lab Data')
    return buffer

# --- 3. Streamlit UI ---
st.set_page_config(page_title="Process Scheduling Lab", layout="wide")

st.title("CPU Scheduling & Process Management Simulator")
st.markdown("Upload your process table or download the generated lab template to begin.")

# Sidebar for Template Download
st.sidebar.header("Lab Data Generation")
st.sidebar.write("Need the 1,500 random processes?")
excel_buffer = generate_template_excel()
st.sidebar.download_button(
    label="📥 Download template.xlsx",
    data=excel_buffer.getvalue(),
    file_name="template.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Algorithm Descriptions Dictionary
algo_descriptions = {
    "FCFS": "**First-Come, First-Served (FCFS):** Non-preemptive. Processes are executed strictly in the order they arrive in the ready queue. Simple to implement but can lead to the 'convoy effect' if a long process arrives first.",
    "SJF": "**Shortest Job First (SJF):** Non-preemptive. The scheduler selects the process with the smallest total burst time. It provides the optimal average waiting time for a given set of processes.",
    "SRTF": "**Shortest Remaining Time First (SRTF):** Preemptive. The scheduler strictly evaluates the remaining burst time. If a newly arrived process has a shorter burst time than what is left of the currently executing process, it preempts it.",
    "Priority (Low Int = High Prio)": "**Priority Scheduling:** Non-preemptive. Processes are executed based on priority value. Lower integers indicate higher priority (e.g., Priority 1 goes before Priority 5). FCFS is used as a tie-breaker.",
    "Priority (High Int = High Prio)": "**Priority Scheduling:** Non-preemptive. Processes are executed based on priority value. Higher integers indicate higher priority (e.g., Priority 10 goes before Priority 2). FCFS is used as a tie-breaker.",
    "Round Robin": "**Round Robin (RR):** Preemptive. Each process is assigned a fixed time slot (Time Quantum). If a process does not finish within its quantum, it is preempted and moved to the back of the ready queue."
}

# File Upload and Validation
uploaded_file = st.file_uploader("Upload Processes (Excel)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    required_columns = ['Process ID', 'Arrival Time', 'Burst Time', 'Priority']
    if not all(col in df.columns for col in required_columns):
        st.error("⚠️ Invalid Excel format.")
        st.warning(f"Your uploaded file is missing required columns. Please ensure your headers are exactly: **{', '.join(required_columns)}**")
    else:
        st.success(f"✅ Successfully loaded {len(df)} processes.")
        
        st.divider()
        col1, col2 = st.columns([2, 1])
        with col1:
            algo = st.selectbox("Select Scheduling Algorithm", list(algo_descriptions.keys()))
        with col2:
            tq = 4
            if algo == "Round Robin":
                tq = st.number_input("Time Quantum (ms)", min_value=1, value=4)
        
        # Display the description of the chosen algorithm
        st.info(algo_descriptions[algo])
                
        # Execution
        if st.button("Run Simulation", type="primary"):
            with st.spinner("Simulating process states and generating Gantt timeline..."):
                high_prio = True if "Low Int" in algo else False
                
                gantt_data = simulate_scheduler(df, algo=algo, tq=tq, high_prio_is_low_int=high_prio)
                res_df, avg_arrival, avg_comp, avg_tat, throughput, avg_wait = calculate_metrics(df, gantt_data)
                
                # --- Average Metrics Table ---
                st.divider()
                st.subheader(f"Average Metrics Table: {algo}")
                
                metrics_summary_df = pd.DataFrame({
                    "Metric": ["Average Arrival Time", "Average Completion Time", "Average Turnaround Time", "Average Waiting Time", "Throughput"],
                    "Value": [f"{avg_arrival:.2f} ms", f"{avg_comp:.2f} ms", f"{avg_tat:.2f} ms", f"{avg_wait:.2f} ms", f"{throughput:.4f} proc/ms"]
                })
                # Hide the index column for a cleaner presentation
                st.table(metrics_summary_df.set_index("Metric"))
                
                # --- Detailed Process Table ---
                st.subheader("Detailed Process Table")
                st.caption("Scroll through the table below to see the exact times calculated for each individual process.")
                
                # Reorder the dataframe columns to read logically from left to right
                display_cols = ['Process ID', 'Arrival Time', 'Burst Time', 'Priority', 'Completion Time', 'Turnaround Time', 'Waiting Time']
                st.dataframe(res_df[display_cols], use_container_width=True, hide_index=True)
                
                # --- Textbook Style Single-Row Gantt Chart ---
                st.divider()
                st.subheader("Interactive Gantt Chart")
                st.caption("Tip: With 1,500 processes, the chart is highly compressed. Click and drag horizontally to zoom into specific blocks. Double-click to zoom out.")
                
                tasks = [d['Task'] for d in gantt_data]
                starts = [d['Start'] for d in gantt_data]
                finishes = [d['Finish'] for d in gantt_data]
                durations = [f - s for f, s in zip(finishes, starts)]
                
                colors = ['white' if t != 'IDLE' else '#f0f0f0' for t in tasks]
                line_colors = ['#1f77b4' if t != 'IDLE' else 'gray' for t in tasks]
                text_colors = ['#1f77b4' if t != 'IDLE' else 'gray' for t in tasks]
                
                hover_text = [f"<b>{t}</b><br>Start: {s} ms<br>Finish: {f} ms" for t, s, f in zip(tasks, starts, finishes)]

                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=durations,
                    base=starts,
                    y=['CPU'] * len(tasks), 
                    orientation='h',
                    text=tasks,
                    textposition='inside',
                    insidetextanchor='middle',
                    hoverinfo='text',
                    hovertext=hover_text,
                    marker=dict(
                        color=colors,
                        line=dict(color=line_colors, width=2)
                    ),
                    textfont=dict(color=text_colors, size=14)
                ))
                
                fig.update_layout(
                    height=250, 
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(t=20, b=20, l=10, r=10),
                    showlegend=False
                )
                
                fig.update_yaxes(visible=False, showticklabels=False)
                
                fig.update_xaxes(
                    title="Time Units (ms)",
                    showline=True, 
                    linewidth=2, 
                    linecolor='#1f77b4', 
                    tickcolor='#1f77b4',
                    tickfont=dict(color='#1f77b4'),
                    gridcolor='#e0e0e0'
                )

                st.plotly_chart(fig, use_container_width=True)