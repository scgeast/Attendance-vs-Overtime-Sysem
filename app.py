import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import io
import re

# Cek dependencies
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    st.warning("⚠️ Openpyxl tidak tersedia, menggunakan engine alternatif")

# Konfigurasi halaman
st.set_page_config(
    page_title="Overtime Management System",
    page_icon="⏰",
    layout="wide"
)

# CSS untuk merapikan bagian atas dan tombol download custom
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    h1, h2, h3 {
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }
    .stCheckbox {
        margin-top: 0.1rem !important;
        margin-bottom: 0.1rem !important;
    }
    .css-18e3th9 {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
    }
    .css-1d391kg {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0rem !important;
        padding-right: 0rem !important;
    }
    .stMetric {
        margin: 0.5rem 0 !important;
    }
    /* Gaya tombol download Excel custom */
    .custom-download-button {
        position: absolute !important;
        /* Top dan right akan diatur oleh st.markdown HTML */
        z-index: 101; /* Di atas elemen lain */
        background-color: #f0f8ff; /* Light blue background */
        border: 1px solid #4682b4; /* Steel blue border */
        border-radius: 4px;
        padding: 0.25rem 0.5rem;
        font-size: 0.75rem;
        cursor: pointer;
        transition: background-color 0.2s, border-color 0.2s;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }
    
    .custom-download-button:hover {
        background-color: #e6f3ff; /* Sedikit lebih gelap saat hover */
        border-color: #5a9bd5;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Judul aplikasi
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 0.5rem;">
        <img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48Y2lyY2xlIGN4PSIxMiIgY3k9IjEyIiByPSIxMCIgc3Ryb2tlPSIjMzQzNDM0IiBzdHJva2Utd2lkdGg9IjIiIGZpbGw9Im5vbmUiPjwvY2lyY2xlPjxwYXRoIGQ9Ik0xMiAydjEwTTExIDEySDcjLTQuOSAwLTktNC4xLTktOVoiIHN0cm9rZT0iIzM0MzQzNCIgc3Ryb2tlLXdpZHRoPSIyIiBmaWxsPSJub25lIj48L3BhdGg+PC9zdmc+" alt="Overtime" width="24" height="24">
        <h3 style="margin: 0; font-size: 2rem;">Overtime Management System</h3>
    </div>
    """,
    unsafe_allow_html=True
)

# Toggle di bawah judul
show_process_area = st.checkbox("Show Processing Steps", value=True)

st.markdown("---")

# Container untuk area proses
if show_process_area:
    process_container = st.container()
else:
    process_container = None

# --- Fungsi-fungsi ---
def read_excel_file(file):
    try:
        if OPENPYXL_AVAILABLE:
            return pd.read_excel(file, engine='openpyxl')
        else:
            return pd.read_excel(file, engine='xlrd')
    except Exception as e:
        st.error(f"Error membaca file: {e}")
        return None

def normalize_column_names(df):
    if df is None or df.empty:
        return df
    normalized_columns = {}
    for col in df.columns:
        normalized = re.sub(r'[^a-zA-Z0-9]', '', str(col)).lower()
        normalized_columns[col] = normalized
    df = df.rename(columns=normalized_columns)
    return df

def find_column(df, possible_names):
    if df is None or df.empty:
        return None
    normalized_df = normalize_column_names(df.copy())
    possible_names = [re.sub(r'[^a-zA-Z0-9]', '', name).lower() for name in possible_names]
    for col in normalized_df.columns:
        if col in possible_names:
            return col
    return None

def convert_to_hours(time_value):
    if pd.isna(time_value):
        return 0.0
    try:
        if isinstance(time_value, (int, float)):
            return float(time_value)
        if isinstance(time_value, timedelta):
            return time_value.total_seconds() / 3600
        if isinstance(time_value, time):
            return time_value.hour + time_value.minute / 60 + time_value.second / 3600
        time_str = str(time_value).strip()
        if 'day' in time_str or 'days' in time_str:
            td = pd.to_timedelta(time_str)
            return td.total_seconds() / 3600
        time_pattern = r'^(\d+):(\d+):?(\d+)?$'
        match = re.match(time_pattern, time_str)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3)) if match.group(3) else 0
            return hours + minutes / 60 + seconds / 3600
        return float(time_str)
    except (ValueError, TypeError):
        return 0.0

def hours_to_hhmm(hours):
    if pd.isna(hours) or hours == 0:
        return "00:00"
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"

def parse_dd_mm_yyyy(date_str):
    if pd.isna(date_str):
        return pd.NaT
    try:
        if isinstance(date_str, (datetime, pd.Timestamp)):
            return date_str
        date_str = str(date_str).strip()
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
            return datetime.strptime(date_str, '%d/%m/%Y')
        if re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', date_str):
            return datetime.strptime(date_str, '%d-%m-%Y')
        return pd.to_datetime(date_str, errors='coerce')
    except (ValueError, TypeError):
        return pd.NaT

def create_summary_table(overtime_merged):
    if overtime_merged is None or overtime_merged.empty:
        return pd.DataFrame()
    
    emp_col = find_column(overtime_merged, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
    job_col = find_column(overtime_merged, ['JobPosition', 'Position', 'Posisi', 'Jabatan'])
    shift_col = find_column(overtime_merged, ['Shift', 'ShiftKerja', 'Jadwal'])
    wt_normal_col = find_column(overtime_merged, ['WTNormal', 'WT/Normal', 'NormalHours', 'JamNormal'])
    
    if not emp_col:
        st.error("Kolom Employee tidak ditemukan untuk summary")
        return pd.DataFrame()
    
    summary_data = []
    for employee in overtime_merged[emp_col].unique():
        if pd.isna(employee):
            continue
        employee_data = overtime_merged[overtime_merged[emp_col] == employee]
        
        work_days = 0
        if shift_col and shift_col in employee_data.columns:
            shift_exclusions = ['off', 'libur', 'leave', 'cuti', 'hari libur', 'istirahat', 'kosong', '']
            work_days = employee_data[
                (employee_data[shift_col].notna()) & 
                (~employee_data[shift_col].astype(str).str.lower().isin(shift_exclusions)) & 
                (employee_data[shift_col].astype(str).str.strip() != '')
            ].shape[0]
        else:
            work_days = len(employee_data)
        
        wt_normal_hours = 0
        if wt_normal_col and wt_normal_col in employee_data.columns:
            for _, row in employee_data.iterrows():
                wt_value = row[wt_normal_col]
                wt_normal_hours += convert_to_hours(wt_value)
        
        rkp_pic_total_hours = 0
        for _, row in employee_data.iterrows():
            rkp_value = row['RKP_PIC']
            if rkp_value != "00:00":
                rkp_pic_total_hours += convert_to_hours(rkp_value)
        
        job_position = 'N/A'
        if job_col and job_col in employee_data.columns:
            job_positions = employee_data[job_col].dropna()
            if not job_positions.empty:
                job_position = job_positions.iloc[0]
        
        summary_data.append({
            'Employee Name': employee.title(),
            'Job Position': job_position,
            'D/Work': work_days,
            'WT/Normal': hours_to_hhmm(wt_normal_hours),
            'RKP PIC': hours_to_hhmm(rkp_pic_total_hours)
        })
    
    summary_df = pd.DataFrame(summary_data)
    if not summary_df.empty:
        summary_df.insert(0, 'No', range(1, len(summary_df) + 1))
    return summary_df

def process_overtime_data(overtime_file, rekap_file):
    try:
        overtime_df = read_excel_file(overtime_file)
        rekap_df = read_excel_file(rekap_file)
        if overtime_df is None or rekap_df is None:
            return None, None, None
    except Exception as e:
        st.error(f"Error membaca file: {e}")
        return None, None, None
    
    if process_container:
        with process_container:
            with st.expander("🔍 Informasi Kolom yang Terdeteksi", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**File Overtime:**")
                    st.write(list(overtime_df.columns))
                with col2:
                    st.write("**File Rekap:**")
                    st.write(list(rekap_df.columns))
    
    overtime_df = normalize_column_names(overtime_df)
    rekap_df = normalize_column_names(rekap_df)
    
    emp_col_overtime = find_column(overtime_df, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
    emp_col_rekap = find_column(rekap_df, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
    date_col_overtime = find_column(overtime_df, ['Date', 'Tanggal', 'Tgl'])
    date_col_rekap = find_column(rekap_df, ['Date', 'Tanggal', 'Tgl'])
    duration_col = find_column(rekap_df, ['Duration', 'Durasi', 'LamaWaktu'])
    
    if not emp_col_overtime:
        st.error("❌ Kolom Employee Name tidak ditemukan dalam file overtime!")
        st.info("Pastikan file overtime memiliki kolom: Employee Name, Employee, Nama Karyawan, atau Nama")
        return None, None, None
    if not emp_col_rekap:
        st.error("❌ Kolom Employee Name tidak ditemukan dalam file rekap!")
        st.info("Pastikan file rekap memiliki kolom: Employee Name, Employee, Nama Karyawan, atau Nama")
        return None, None, None
    if not date_col_overtime:
        st.error("❌ Kolom Date tidak ditemukan dalam file overtime!")
        return None, None, None
    if not date_col_rekap:
        st.error("❌ Kolom Date tidak ditemukan dalam file rekap!")
        return None, None, None
    if not duration_col:
        st.error("❌ Kolom Duration tidak ditemukan dalam file rekap!")
        return None, None, None
    
    if process_container:
        with process_container:
            st.success("✅ Semua kolom berhasil terdeteksi!")
            with st.expander("📋 Mapping Kolom yang Ditemukan", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**File Overtime:**")
                    st.write(f"- Employee: `{emp_col_overtime}`")
                    st.write(f"- Date: `{date_col_overtime}`")
                with col2:
                    st.write("**File Rekap:**")
                    st.write(f"- Employee: `{emp_col_rekap}`")
                    st.write(f"- Date: `{date_col_rekap}`")
                    st.write(f"- Duration: `{duration_col}`")
    
    if process_container:
        with process_container:
            with st.expander("🔄 Proses Konversi Format Tanggal", expanded=False):
                st.info("Mengkonversi format tanggal...")
                overtime_df[date_col_overtime] = overtime_df[date_col_overtime].apply(parse_dd_mm_yyyy)
                rekap_df[date_col_rekap] = rekap_df[date_col_rekap].apply(parse_dd_mm_yyyy)
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Overtime Dates (5 sample):**")
                    st.write(overtime_df[date_col_overtime].head())
                with col2:
                    st.write("**Rekap Dates (5 sample):**")
                    st.write(rekap_df[date_col_rekap].head())
    
    if process_container:
        with process_container:
            with st.expander("🔄 Normalisasi Data untuk Matching", expanded=False):
                st.info("Normalisasi nama karyawan dan tanggal...")
                
                def normalize_name(name):
                    if pd.isna(name):
                        return ""
                    name_str = str(name).strip().lower()
                    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
                    return name_str

                overtime_df[emp_col_overtime] = overtime_df[emp_col_overtime].apply(normalize_name)
                rekap_df[emp_col_rekap] = rekap_df[emp_col_rekap].apply(normalize_name)

                overtime_df[date_col_overtime] = pd.to_datetime(overtime_df[date_col_overtime], errors='coerce').dt.strftime('%Y-%m-%d')
                rekap_df[date_col_rekap] = pd.to_datetime(rekap_df[date_col_rekap], errors='coerce').dt.strftime('%Y-%m-%d')

                st.write("Contoh data setelah normalisasi:")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Overtime (Normalized):**")
                    st.write(overtime_df[[emp_col_overtime, date_col_overtime]].head())
                with col2:
                    st.write("**Rekap (Normalized):**")
                    st.write(rekap_df[[emp_col_rekap, date_col_rekap]].head())

    rekap_df['duration_hours'] = rekap_df[duration_col].apply(convert_to_hours)
    rekap_df['duration_hhmm'] = rekap_df['duration_hours'].apply(hours_to_hhmm)

    overtime_df['RKP_PIC'] = "00:00"
    overtime_df['RKP_PIC_HOURS'] = 0.0

    rekap_df_mapped = rekap_df.set_index([emp_col_rekap, date_col_rekap])

    def get_rkp_pic(row):
        employee = row[emp_col_overtime]
        date = row[date_col_overtime]
        if pd.isna(employee) or pd.isna(date):
            return "00:00", 0.0
        try:
            match_row = rekap_df_mapped.loc[(employee, date)]
            duration_hhmm = match_row['duration_hhmm'] if isinstance(match_row, pd.Series) else match_row.iloc[0]['duration_hhmm']
            duration_hours = match_row['duration_hours'] if isinstance(match_row, pd.Series) else match_row.iloc[0]['duration_hours']
            return duration_hhmm, duration_hours
        except KeyError:
            return "00:00", 0.0
        except Exception as e:
            st.warning(f"Error saat mencari data untuk ({employee}, {date}): {e}")
            return "00:00", 0.0

    results = overtime_df.apply(get_rkp_pic, axis=1, result_type='expand')
    overtime_df['RKP_PIC'], overtime_df['RKP_PIC_HOURS'] = results[0], results[1]

    matched_count = (overtime_df['RKP_PIC'] != "00:00").sum()
    total_count = len(overtime_df)
    
    if process_container:
        with process_container:
            st.info(f"📊 Data berhasil diproses: {matched_count}/{total_count} record matching ({matched_count/total_count*100:.1f}%)")
    
    if process_container:
        with process_container:
            with st.expander("🔍 Verifikasi Data Matching", expanded=False):
                st.write("**Contoh data yang berhasil match:**")
                matched_data = overtime_df[overtime_df['RKP_PIC'] != "00:00"].head()
                if not matched_data.empty:
                    display_cols = [emp_col_overtime, date_col_overtime, 'RKP_PIC']
                    available_cols = [col for col in display_cols if col in matched_data.columns]
                    st.write(matched_data[available_cols])
                else:
                    st.write("Tidak ada data yang match")
                st.write("---")
                st.write("**Contoh data yang TIDAK match:**")
                not_matched_data = overtime_df[overtime_df['RKP_PIC'] == "00:00"].head()
                if not not_matched_data.empty:
                    display_cols = [emp_col_overtime, date_col_overtime, 'RKP_PIC']
                    available_cols = [col for col in display_cols if col in not_matched_data.columns]
                    st.write(not_matched_data[available_cols])
                else:
                    st.write("Semua data match!")
                st.write("---")
                st.write("**Statistik Matching:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", total_count)
                with col2:
                    st.metric("Data Match", matched_count)
                with col3:
                    st.metric("Persentase Match", f"{matched_count/total_count*100:.1f}%")

    return overtime_df, rekap_df, overtime_df

# Sidebar untuk upload file
st.sidebar.header("📤 Upload Files")

uploaded_overtime = st.sidebar.file_uploader(
    "Upload Attendance Data File", 
    type=['xlsx'],
    help="Upload file overtime_data.xlsx"
)

uploaded_rekap = st.sidebar.file_uploader(
    "Upload Rekap Overtime File", 
    type=['xlsx'],
    help="Upload file OT detail.xlsx"
)

# Main content
if uploaded_overtime is not None and uploaded_rekap is not None:
    try:
        with st.spinner("Memproses data..."):
            overtime_df, rekap_df, overtime_merged = process_overtime_data(
                uploaded_overtime, 
                uploaded_rekap
            )
        
        if overtime_merged is not None:
            tab1, tab2, tab3 = st.tabs([
                "📊 Overtime Data (Merged)", 
                "📋 Original Data", 
                "📈 Summary"
            ])
            
            with tab1:
                st.subheader("Overtime Data With RKP PIC")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    emp_col = find_column(overtime_merged, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
                    total_employees = overtime_merged[emp_col].nunique() if emp_col else 0
                    st.metric("Total Karyawan", total_employees)
                
                with col2:
                    total_records = len(overtime_merged)
                    st.metric("Total Records", total_records)
                
                with col3:
                    filled_rkp = (overtime_merged['RKP_PIC'] != "00:00").sum()
                    st.metric("RKP PIC Terisi", f"{filled_rkp}/{total_records}")
                
                with col4:
                    total_overtime_hours = 0
                    for rkp_value in overtime_merged['RKP_PIC']:
                        if rkp_value != "00:00":
                            total_overtime_hours += convert_to_hours(rkp_value)
                    st.metric("Total Overtime (Jam)", round(total_overtime_hours, 2))
                
                display_columns = [col for col in overtime_merged.columns if col not in ['RKP_PIC_HOURS']]
                display_df = overtime_merged[display_columns].copy()
                
                if 'RKP_PIC' in display_df.columns:
                    cols = display_df.columns.tolist()
                    if 'RKP_PIC' in cols:
                        cols.remove('RKP_PIC')
                        date_col = find_column(display_df, ['Date', 'Tanggal', 'Tgl'])
                        emp_col = find_column(display_df, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
                        if date_col and date_col in cols:
                            date_idx = cols.index(date_col)
                            cols.insert(date_idx + 1, 'RKP_PIC')
                        elif emp_col and emp_col in cols:
                            emp_idx = cols.index(emp_col)
                            cols.insert(emp_idx + 1, 'RKP_PIC')
                        else:
                            cols.insert(1, 'RKP_PIC')
                        display_df = display_df[cols]
                
                def highlight_rkp_pic(row):
                    if row['RKP_PIC'] != "00:00":
                        return ['background-color: #e6ffe6'] * len(row)
                    else:
                        return [''] * len(row)
                
                try:
                    styled_df = display_df.style.apply(highlight_rkp_pic, axis=1)
                    # Render dataframe
                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        height=800
                    )
                except:
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=800
                    )
                
                # --- Tombol Download Excel Custom ---
                # Buat tombol download Excel dan sembunyikan label-nya
                output_excel = io.BytesIO()
                with pd.ExcelWriter(output_excel, engine='openpyxl' if OPENPYXL_AVAILABLE else 'openpyxl') as writer:
                    display_df.to_excel(writer, sheet_name='Overtime_Merged', index=False)
                output_excel.seek(0)
                
                # Gunakan st.download_button untuk fungsionalitas
                # dan HTML untuk menempatkan tombol di posisi yang diinginkan
                download_button_key = 'download_excel_custom'
                st.download_button(
                    label="", # Sembunyikan label tombol
                    data=output_excel,
                    file_name="overtime_merged_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=download_button_key,
                    help="Download as Excel"
                )
                
                # Tempatkan tombol HTML di sebelah kiri tombol CSV bawaan
                # Asumsi tinggi baris tombol sekitar 38px, dan lebar tombol CSV sekitar 100px
                # Penyesuaian posisi mungkin diperlukan tergantung layout
                st.markdown(
                    f"""
                    <script>
                    // Tunggu tombol CSV muncul, lalu posisikan tombol Excel kita
                    const checkForButtons = () => {{
                        const csvButton = document.querySelector('button[title="Download data as CSV"]');
                        const excelButton = document.querySelector('button[title="Download as Excel"]');
                        if (csvButton && excelButton) {{
                            const rect = csvButton.getBoundingClientRect();
                            excelButton.style.position = 'absolute';
                            excelButton.style.top = rect.top + window.scrollY + 'px';
                            excelButton.style.left = rect.left - 110 + window.scrollX + 'px'; // 110px ke kiri dari tombol CSV
                            excelButton.style.zIndex = '101';
                            excelButton.title = 'Download as Excel';
                            excelButton.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M8 13h2"></path><path d="M8 17h6"></path><path d="M8 9h6"></path></svg> Excel';
                            excelButton.classList.add('custom-download-button');
                            clearInterval(intervalId);
                        }}
                    }};
                    const intervalId = setInterval(checkForButtons, 100); // Cek setiap 100ms
                    </script>
                    """,
                    unsafe_allow_html=True
                )
                # --- Akhir Tombol Download Excel Custom ---
                
                # Tombol download di bawah tabel (yg sebelumnya ada) telah diHAPUS
                # (Baris kode untuk tombol download di bawah dataframe dihapus)
            
            with tab2:
                st.subheader("Data Overtime Original")
                st.dataframe(overtime_df, use_container_width=True, height=300)
                
                st.subheader("Data Rekap Overtime Original")
                st.dataframe(rekap_df, use_container_width=True, height=300)
            
            with tab3:
                st.subheader("Summary Data Overtime")
                
                summary_df = create_summary_table(overtime_merged)
                
                if not summary_df.empty:
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        height=400
                    )
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        total_work_days = summary_df['D/Work'].sum()
                        st.metric("Total Hari Kerja", int(total_work_days))
                    
                    with col2:
                        wt_normal_total = 0
                        for wt_value in summary_df['WT/Normal']:
                            wt_normal_total += convert_to_hours(wt_value)
                        st.metric("Total WT/Normal", hours_to_hhmm(wt_normal_total))
                    
                    with col3:
                        rkp_pic_total = 0
                        for rkp_value in summary_df['RKP PIC']:
                            rkp_pic_total += convert_to_hours(rkp_value)
                        st.metric("Total RKP PIC", hours_to_hhmm(rkp_pic_total))
                    
                    output_summary = io.BytesIO()
                    with pd.ExcelWriter(output_summary, engine='openpyxl' if OPENPYXL_AVAILABLE else 'openpyxl') as writer:
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    output_summary.seek(0)
                    
                    st.download_button(
                        label="📥 Download Summary Data",
                        data=output_summary,
                        file_name="overtime_summary.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("Tidak ada data untuk ditampilkan dalam summary.")
        
    except Exception as e:
        st.error(f"Terjadi error dalam memproses  {str(e)}")
        st.info("Pastikan format file sesuai dengan contoh yang diberikan.")
        with st.expander("🔧 Debug Information"):
            st.write(f"Error type: {type(e).__name__}")
            import traceback
            st.code(traceback.format_exc())

else:
    st.info("👆 Silakan upload kedua file untuk memulai proses:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("File Attendance Data")
        st.markdown("""
        **Format yang diharapkan:**
        - ✅ **Employee Name**: `Employee Name`, `EmployeeName`, `Employee`, `Nama Karyawan`, `Nama`
        - ✅ **Date**: `Date`, `Tanggal`, `Tgl` (format DD/MM/YYYY)
        - ✅ **Shift**: `Shift`, `Shift Kerja`, `Jadwal`
        - ✅ **WT/Normal**: `WT/Normal`, `WT Normal`, `Normal Hours`, `Jam Normal`
        - ✅ **Job Position**: `Job Position`, `Position`, `Posisi`, `Jabatan`
        
        *Nama kolom tidak case-sensitive*
        """)
        
    with col2:
        st.subheader("File Rekap Overtime")
        st.markdown("""
        **Format yang diharapkan:**
        - ✅ **Employee Name**: `Employee Name`, `EmployeeName`, `Employee`, `Nama Karyawan`, `Nama`
        - ✅ **Date**: `Date`, `Tanggal`, `Tgl` (format DD/MM/YYYY)
        - ✅ **Duration**: `Duration`, `Durasi`, `Lama Waktu`
        
        *Nama kolom tidak case-sensitive*
        """)

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Overtime Management System © 2025
    </div>
    <div style='text-align: center; color: red;'>
        Kim Jong Un
    </div>
    """,
    unsafe_allow_html=True
)
