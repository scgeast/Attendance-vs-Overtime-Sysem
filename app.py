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
    
    # Tampilkan informasi kolom
    with st.expander("🔍 Informasi Kolom yang Terdeteksi"):
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
    
    # Tampilkan mapping kolom yang berhasil
    st.success("✅ Semua kolom berhasil terdeteksi!")
    with st.expander("📋 Mapping Kolom yang Ditemukan"):
        st.write(f"**Overtime:** Employee={emp_col_overtime}, Date={date_col_overtime}")
        st.write(f"**Rekap:** Employee={emp_col_rekap}, Date={date_col_rekap}, Duration={duration_col}")
    
    # Konversi kolom Date ke format datetime dengan format DD/MM/YYYY
    st.info("🔄 Mengkonversi format tanggal...")
    
    # Untuk file overtime
    overtime_df[date_col_overtime] = overtime_df[date_col_overtime].apply(parse_dd_mm_yyyy)
    
    # Untuk file rekap
    rekap_df[date_col_rekap] = rekap_df[date_col_rekap].apply(parse_dd_mm_yyyy)
    
    # Tampilkan sample tanggal setelah konversi
    with st.expander("📅 Sample Tanggal Setelah Konversi"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Overtime Dates:**")
            st.write(overtime_df[date_col_overtime].head())
        with col2:
            st.write("**Rekap Dates:**")
            st.write(rekap_df[date_col_rekap].head())
    
    # Konversi kolom Duration ke format jam (float)
    rekap_df['duration_hours'] = rekap_df[duration_col].apply(convert_to_hours)
    
    # Merge data untuk mengisi RKP PIC
    overtime_merged = overtime_df.copy()
    
    # Membuat mapping berdasarkan Employee Name dan Date
    rekap_mapping = rekap_df.set_index([emp_col_rekap, date_col_rekap])['duration_hours']
    
    def get_rkp_pic(row):
        employee = row[emp_col_overtime]
        date = row[date_col_overtime]
        
        if pd.isna(employee) or pd.isna(date):
            return 0.0
            
        try:
            # Cari data yang cocok
            match = rekap_mapping.get((employee, date), 0.0)
            return match
        except:
            return 0.0
    
    # Mengisi kolom RKP PIC dalam format jam (float)
    overtime_merged['rkppic_hours'] = overtime_merged.apply(get_rkp_pic, axis=1)
    
    # Tambahkan kolom RKP PIC dalam format HH:MM
    overtime_merged['RKP_PIC'] = overtime_merged['rkppic_hours'].apply(hours_to_hhmm)
    
    # Hitung statistik matching
    matched_count = (overtime_merged['rkppic_hours'] > 0).sum()
    total_count = len(overtime_merged)
    
    st.info(f"📊 Data berhasil diproses: {matched_count}/{total_count} record matching ({matched_count/total_count*100:.1f}%)")
    
    return overtime_df, rekap_df, overtime_merged

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
        
        # Hitung RKP PIC (total overtime)
        rkp_pic_hours = employee_data['rkppic_hours'].sum()
        
        # Ambil Job Position
        job_position = 'N/A'
        if job_col and job_col in employee_data.columns:
            job_positions = employee_data[job_col].dropna()
            if not job_positions.empty:
                job_position = job_positions.iloc[0]
        
        summary_data.append({
            'Employee Name': employee,
            'Job Position': job_position,
            'D/Work': work_days,
            'WT/Normal': hours_to_hhmm(wt_normal_hours),
            'RKP PIC': hours_to_hhmm(rkp_pic_hours)
        })
    
    summary_df = pd.DataFrame(summary_data)
    if not summary_df.empty:
        summary_df.insert(0, 'No', range(1, len(summary_df) + 1))
    
    return summary_df

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
                    filled_rkp = (overtime_merged['rkppic_hours'] > 0).sum()
                    st.metric("RKP PIC Terisi", f"{filled_rkp}/{total_records}")
                
                with col4:
                    total_overtime_hours = overtime_merged['rkppic_hours'].sum()
                    st.metric("Total Overtime (Jam)", round(total_overtime_hours, 2))
                
                # Tampilkan kolom yang relevan saja (sembunyikan kolom internal)
                display_columns = [col for col in overtime_merged.columns if col not in ['rkppic_hours']]
                display_df = overtime_merged[display_columns].copy()
                
                # Pastikan kolom RKP_PIC ada di posisi yang mudah dilihat
                if 'RKP_PIC' in display_df.columns:
                    cols = display_df.columns.tolist()
                    # Pindahkan RKP_PIC ke posisi lebih depan
                    if 'RKP_PIC' in cols:
                        cols.remove('RKP_PIC')
                        # Cari posisi setelah kolom tanggal
                        date_col = find_column(display_df, ['Date', 'Tanggal', 'Tgl'])
                        if date_col and date_col in cols:
                            date_idx = cols.index(date_col)
                            cols.insert(date_idx + 1, 'RKP_PIC')
                        else:
                            cols.insert(1, 'RKP_PIC')
                        display_df = display_df[cols]
                
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
                    
                    # Statistik summary dalam format jam
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        total_work_days = summary_df['D/Work'].sum()
                        st.metric("Total Hari Kerja", int(total_work_days))
                    
                    with col2:
                        # Convert WT/Normal back to hours for total
                        wt_normal_total = overtime_merged['rkppic_hours'].sum()  # Using the same calculation as before
                        st.metric("Total WT/Normal", hours_to_hhmm(wt_normal_total))
                    
                    with col3:
                        rkp_pic_total = overtime_merged['rkppic_hours'].sum()
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
        st.error(f"Terjadi error dalam memproses data: {e}")
        st.info("Pastikan format file sesuai dengan contoh yang diberikan.")

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
    "<div style='text-align: center; color: gray;'>Overtime Management System © 2024</div>",
    unsafe_allow_html=True
)
