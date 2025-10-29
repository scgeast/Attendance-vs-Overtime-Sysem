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

# Judul aplikasi
st.title("⏰ Overtime Management System")
st.markdown("---")

# Toggle di bawah judul untuk menyembunyikan/menampilkan area proses
show_process_area = st.toggle("🔻 Show Processing Steps", value=True)

# Container untuk area proses (akan dihide jika toggle off)
if show_process_area:
    process_container = st.container()
else:
    process_container = None

def read_excel_file(file):
    """Membaca file Excel dengan engine fallback"""
    try:
        if OPENPYXL_AVAILABLE:
            return pd.read_excel(file, engine='openpyxl')
        else:
            return pd.read_excel(file, engine='xlrd')
    except Exception as e:
        st.error(f"Error membaca file: {e}")
        return None

def normalize_column_names(df):
    """Normalisasi nama kolom untuk mengabaikan huruf besar/kecil dan spasi"""
    if df is None or df.empty:
        return df
        
    normalized_columns = {}
    for col in df.columns:
        # Hilangkan spasi, karakter khusus, dan ubah ke lowercase
        normalized = re.sub(r'[^a-zA-Z0-9]', '', str(col)).lower()
        normalized_columns[col] = normalized
    
    # Rename columns
    df = df.rename(columns=normalized_columns)
    return df

def find_column(df, possible_names):
    """Mencari kolom berdasarkan beberapa kemungkinan nama"""
    if df is None or df.empty:
        return None
        
    normalized_df = normalize_column_names(df.copy())
    possible_names = [re.sub(r'[^a-zA-Z0-9]', '', name).lower() for name in possible_names]
    
    for col in normalized_df.columns:
        if col in possible_names:
            return col
    return None

def convert_to_hours(time_value):
    """Mengkonversi berbagai format waktu ke jam (float)"""
    if pd.isna(time_value):
        return 0.0
    
    try:
        # Jika sudah numeric, langsung return
        if isinstance(time_value, (int, float)):
            return float(time_value)
        
        # Jika timedelta
        if isinstance(time_value, timedelta):
            return time_value.total_seconds() / 3600
        
        # Jika datetime.time
        if isinstance(time_value, time):
            return time_value.hour + time_value.minute / 60 + time_value.second / 3600
        
        # Jika string
        time_str = str(time_value).strip()
        
        # Coba parse sebagai timedelta string
        if 'day' in time_str or 'days' in time_str:
            td = pd.to_timedelta(time_str)
            return td.total_seconds() / 3600
        
        # Coba parse sebagai time string (HH:MM:SS atau HH:MM)
        time_pattern = r'^(\d+):(\d+):?(\d+)?$'
        match = re.match(time_pattern, time_str)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3)) if match.group(3) else 0
            return hours + minutes / 60 + seconds / 3600
        
        # Coba konversi langsung ke float
        return float(time_str)
    
    except (ValueError, TypeError):
        return 0.0

def hours_to_hhmm(hours):
    """Mengkonversi jam (float) ke format HH:MM"""
    if pd.isna(hours) or hours == 0:
        return "00:00"
    
    total_minutes = int(hours * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"

def parse_dd_mm_yyyy(date_str):
    """Parse tanggal dalam format DD/MM/YYYY"""
    if pd.isna(date_str):
        return pd.NaT
    
    try:
        # Jika sudah datetime object
        if isinstance(date_str, (datetime, pd.Timestamp)):
            return date_str
        
        # Convert to string and parse
        date_str = str(date_str).strip()
        
        # Coba format DD/MM/YYYY
        if re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', date_str):
            return datetime.strptime(date_str, '%d/%m/%Y')
        
        # Coba format DD-MM-YYYY
        if re.match(r'^\d{1,2}-\d{1,2}-\d{4}$', date_str):
            return datetime.strptime(date_str, '%d-%m-%Y')
        
        # Coba format default pandas
        return pd.to_datetime(date_str, errors='coerce')
        
    except (ValueError, TypeError):
        return pd.NaT

def create_summary_table(overtime_merged):
    """Membuat tabel summary"""
    
    if overtime_merged is None or overtime_merged.empty:
        return pd.DataFrame()
    
    # Cari kolom yang diperlukan
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
        
        # Hitung D/Work (jumlah hari kerja, exclude Off, Libur, Leave, Cuti)
        if shift_col and shift_col in employee_data.columns:
            shift_exclusions = ['off', 'libur', 'leave', 'cuti', 'hari libur', 'istirahat', 'kosong', '']
            work_days = employee_data[
                (employee_data[shift_col].notna()) & 
                (~employee_data[shift_col].astype(str).str.lower().isin(shift_exclusions)) & 
                (employee_data[shift_col].astype(str).str.strip() != '')
            ].shape[0]
        else:
            work_days = len(employee_data)  # Default jika tidak ada kolom shift
        
        # Hitung WT/Normal (jumlah jam normal)
        wt_normal_hours = 0
        if wt_normal_col and wt_normal_col in employee_data.columns:
            for _, row in employee_data.iterrows():
                wt_value = row[wt_normal_col]
                wt_normal_hours += convert_to_hours(wt_value)
        
        # Hitung RKP PIC (total overtime) - konversi dari format HH:MM ke hours
        rkp_pic_total_hours = 0
        for _, row in employee_data.iterrows():
            rkp_value = row['RKP_PIC']
            if rkp_value != "00:00":
                rkp_pic_total_hours += convert_to_hours(rkp_value)
        
        # Ambil Job Position
        job_position = 'N/A'
        if job_col and job_col in employee_data.columns:
            job_positions = employee_data[job_col].dropna()
            if not job_positions.empty:
                job_position = job_positions.iloc[0]
        
        summary_data.append({
            'Employee Name': employee.title(),  # Kembalikan ke format kapital
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
    """Memproses data overtime dan rekap overtime"""
    
    # Membaca file
    try:
        overtime_df = read_excel_file(overtime_file)
        rekap_df = read_excel_file(rekap_file)
        
        if overtime_df is None or rekap_df is None:
            return None, None, None
            
    except Exception as e:
        st.error(f"Error membaca file: {e}")
        return None, None, None
    
    # Tampilkan informasi kolom dalam expander
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
    
    # Normalisasi nama kolom
    overtime_df = normalize_column_names(overtime_df)
    rekap_df = normalize_column_names(rekap_df)
    
    # Cari kolom yang diperlukan
    emp_col_overtime = find_column(overtime_df, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
    emp_col_rekap = find_column(rekap_df, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
    date_col_overtime = find_column(overtime_df, ['Date', 'Tanggal', 'Tgl'])
    date_col_rekap = find_column(rekap_df, ['Date', 'Tanggal', 'Tgl'])
    duration_col = find_column(rekap_df, ['Duration', 'Durasi', 'LamaWaktu'])
    
    # Validasi kolom yang diperlukan
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
    
    # Tampilkan mapping kolom yang berhasil dalam expander
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
    
    # Konversi kolom Date ke format datetime dengan format DD/MM/YYYY
    if process_container:
        with process_container:
            with st.expander("🔄 Proses Konversi Format Tanggal", expanded=False):
                st.info("Mengkonversi format tanggal...")
                
                # Untuk file overtime
                overtime_df[date_col_overtime] = overtime_df[date_col_overtime].apply(parse_dd_mm_yyyy)
                
                # Untuk file rekap
                rekap_df[date_col_rekap] = rekap_df[date_col_rekap].apply(parse_dd_mm_yyyy)
                
                # Tampilkan sample tanggal setelah konversi
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Overtime Dates (5 sample):**")
                    st.write(overtime_df[date_col_overtime].head())
                with col2:
                    st.write("**Rekap Dates (5 sample):**")
                    st.write(rekap_df[date_col_rekap].head())
    
    # --- NORMALISASI LEBIH KETAT UNTUK MATCHING ---
    if process_container:
        with process_container:
            with st.expander("🔄 Normalisasi Data untuk Matching", expanded=False):
                st.info("Normalisasi nama karyawan dan tanggal...")
                
                # Fungsi helper untuk normalisasi nama
                def normalize_name(name):
                    if pd.isna(name):
                        return ""
                    name_str = str(name).strip().lower()
                    # Hapus karakter non-alphanumeric (opsional)
                    name_str = re.sub(r'[^a-z0-9\s]', '', name_str)
                    return name_str

                # Normalisasi nama karyawan
                overtime_df[emp_col_overtime] = overtime_df[emp_col_overtime].apply(normalize_name)
                rekap_df[emp_col_rekap] = rekap_df[emp_col_rekap].apply(normalize_name)

                # Normalisasi tanggal ke format YYYY-MM-DD
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

    # Konversi kolom Duration ke format jam (float) dan format HH:MM
    rekap_df['duration_hours'] = rekap_df[duration_col].apply(convert_to_hours)
    rekap_df['duration_hhmm'] = rekap_df['duration_hours'].apply(hours_to_hhmm)
    
    # --- BUAT KOLOM RKP_PIC DI FILE OVERTIME ---
    # Buat kolom baru di overtime_df
    overtime_df['RKP_PIC'] = "00:00"  # Default value
    overtime_df['RKP_PIC_HOURS'] = 0.0  # Jika perlu untuk perhitungan

    # Buat mapping dari rekap_df untuk matching
    rekap_df_mapped = rekap_df.set_index([emp_col_rekap, date_col_rekap])

    def get_rkp_pic(row):
        employee = row[emp_col_overtime]
        date = row[date_col_overtime]
        
        if pd.isna(employee) or pd.isna(date):
            return "00:00", 0.0
            
        try:
            # Cari data yang cocok di rekap_df
            match_row = rekap_df_mapped.loc[(employee, date)]
            # Ambil nilai duration_hhmm dari hasil pencarian
            duration_hhmm = match_row['duration_hhmm'] if isinstance(match_row, pd.Series) else match_row.iloc[0]['duration_hhmm']
            duration_hours = match_row['duration_hours'] if isinstance(match_row, pd.Series) else match_row.iloc[0]['duration_hours']
            return duration_hhmm, duration_hours
        except KeyError:
            # Jika tidak ditemukan, kembalikan default
            return "00:00", 0.0
        except Exception as e:
            st.warning(f"Error saat mencari data untuk ({employee}, {date}): {e}")
            return "00:00", 0.0

    # Terapkan fungsi ke setiap baris
    results = overtime_df.apply(get_rkp_pic, axis=1, result_type='expand')
    overtime_df['RKP_PIC'], overtime_df['RKP_PIC_HOURS'] = results[0], results[1]

    # Hitung statistik matching
    matched_count = (overtime_df['RKP_PIC'] != "00:00").sum()
    total_count = len(overtime_df)
    
    if process_container:
        with process_container:
            st.info(f"📊 Data berhasil diproses: {matched_count}/{total_count} record matching ({matched_count/total_count*100:.1f}%)")
    
    # Tampilkan data matching untuk verifikasi dalam expander
    if process_container:
        with process_container:
            with st.expander("🔍 Verifikasi Data Matching", expanded=False):
                st.write("**Contoh data yang berhasil match:**")
                matched_data = overtime_df[overtime_df['RKP_PIC'] != "00:00"].head()
                if not matched_data.empty:
                    # Tampilkan kolom yang relevan
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

    # Kembalikan overtime_df yang sudah ditambah kolom RKP_PIC
    return overtime_df, rekap_df, overtime_df

# Sidebar untuk upload file
st.sidebar.header("📤 Upload Files")

uploaded_overtime = st.sidebar.file_uploader(
    "Upload Overtime Data File", 
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
        # Proses data
        with st.spinner("Memproses data..."):
            overtime_df, rekap_df, overtime_merged = process_overtime_data(
                uploaded_overtime, 
                uploaded_rekap
            )
        
        if overtime_merged is not None:
            # Buat tabs
            tab1, tab2, tab3 = st.tabs([
                "📊 Overtime Data (Merged)", 
                "📋 Original Data", 
                "📈 Summary"
            ])
            
            with tab1:
                st.subheader("Overtime Data dengan RKP PIC")
                
                # Tampilkan statistik
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    emp_col = find_column(overtime_merged, ['EmployeeName', 'Employee', 'NamaKaryawan', 'Name', 'Nama'])
                    total_employees = overtime_merged[emp_col].nunique() if emp_col else 0
                    st.metric("Total Karyawan", total_employees)
                
                with col2:
                    total_records = len(overtime_merged)
                    st.metric("Total Records", total_records)
                
                with col3:
                    # Hitung yang memiliki RKP PIC (bukan "00:00")
                    filled_rkp = (overtime_merged['RKP_PIC'] != "00:00").sum()
                    st.metric("RKP PIC Terisi", f"{filled_rkp}/{total_records}")
                
                with col4:
                    # Hitung total overtime dari kolom RKP_PIC
                    total_overtime_hours = 0
                    for rkp_value in overtime_merged['RKP_PIC']:
                        if rkp_value != "00:00":
                            total_overtime_hours += convert_to_hours(rkp_value)
                    st.metric("Total Overtime (Jam)", round(total_overtime_hours, 2))
                
                # Tampilkan kolom yang relevan saja
                display_columns = [col for col in overtime_merged.columns if col not in ['RKP_PIC_HOURS']]
                display_df = overtime_merged[display_columns].copy()
                
                # Pastikan kolom RKP_PIC ada di posisi yang mudah dilihat
                if 'RKP_PIC' in display_df.columns:
                    cols = display_df.columns.tolist()
                    # Pindahkan RKP_PIC ke posisi lebih depan
                    if 'RKP_PIC' in cols:
                        cols.remove('RKP_PIC')
                        # Cari posisi setelah kolom tanggal atau employee
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
                
                # Highlight baris yang memiliki RKP PIC
                def highlight_rkp_pic(row):
                    if row['RKP_PIC'] != "00:00":
                        return ['background-color: #e6ffe6'] * len(row)
                    else:
                        return [''] * len(row)
                
                # Apply styling hanya untuk display
                try:
                    styled_df = display_df.style.apply(highlight_rkp_pic, axis=1)
                    st.dataframe(
                        styled_df,
                        use_container_width=True,
                        height=400
                    )
                except:
                    # Fallback jika styling error
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        height=400
                    )
                
                # Download button untuk data merged
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl' if OPENPYXL_AVAILABLE else 'xlrd') as writer:
                    display_df.to_excel(writer, sheet_name='Overtime_Merged', index=False)
                output.seek(0)
                
                st.download_button(
                    label="📥 Download Merged Data",
                    data=output,
                    file_name="overtime_merged_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with tab2:
                st.subheader("Data Overtime Original")
                st.dataframe(overtime_df, use_container_width=True, height=300)
                
                st.subheader("Data Rekap Overtime Original")
                st.dataframe(rekap_df, use_container_width=True, height=300)
            
            with tab3:
                st.subheader("Summary Data Overtime")
                
                # Buat summary table
                summary_df = create_summary_table(overtime_merged)
                
                if not summary_df.empty:
                    # Tampilkan summary
                    st.dataframe(
                        summary_df,
                        use_container_width=True,
                        height=400
                    )
                    
                    # Statistik summary
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        total_work_days = summary_df['D/Work'].sum()
                        st.metric("Total Hari Kerja", int(total_work_days))
                    
                    with col2:
                        # Hitung total WT/Normal dari summary
                        wt_normal_total = 0
                        for wt_value in summary_df['WT/Normal']:
                            wt_normal_total += convert_to_hours(wt_value)
                        st.metric("Total WT/Normal", hours_to_hhmm(wt_normal_total))
                    
                    with col3:
                        # Hitung total RKP PIC dari summary
                        rkp_pic_total = 0
                        for rkp_value in summary_df['RKP PIC']:
                            rkp_pic_total += convert_to_hours(rkp_value)
                        st.metric("Total RKP PIC", hours_to_hhmm(rkp_pic_total))
                    
                    # Download button untuk summary
                    output_summary = io.BytesIO()
                    with pd.ExcelWriter(output_summary, engine='openpyxl' if OPENPYXL_AVAILABLE else 'xlrd') as writer:
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
        # Debug info
        with st.expander("🔧 Debug Information"):
            st.write(f"Error type: {type(e).__name__}")
            import traceback
            st.code(traceback.format_exc())

else:
    # Tampilan default ketika belum upload file
    st.info("👆 Silakan upload kedua file untuk memulai proses:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("File Overtime Data")
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
        - ✅ **Duration**: `Duration`, `Durasi`, `Lama Waktu`, `Total Waktu`
        
        *Nama kolom tidak case-sensitive*
        """)

# Footer
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
