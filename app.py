import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io
import re

# Konfigurasi halaman
st.set_page_config(
    page_title="Sistem Absen & Overtime",
    page_icon="📊",
    layout="wide"
)

def normalize_column_name(col):
    """Normalisasi nama kolom untuk matching yang lebih baik"""
    if not isinstance(col, str):
        return str(col)
    
    # Normalisasi: lowercase, hapus spasi, karakter khusus
    col = col.lower().strip()
    col = re.sub(r'[^\w]', '', col)  # Hapus karakter non-alphanumeric
    col = re.sub(r'\s+', '', col)    # Hapus spasi
    
    # Mapping nama kolom yang umum
    column_mapping = {
        # Employee name variations
        'employeename': 'employeename',
        'employee': 'employeename',
        'empname': 'employeename',
        'name': 'employeename',
        'nama': 'employeename',
        'namakaryawan': 'employeename',
        'staffname': 'employeename',
        
        # Date variations
        'date': 'date',
        'tanggal': 'date',
        'workdate': 'date',
        'dates': 'date',
        'periode': 'date',
        'day': 'date',
        
        # Job position variations
        'jobposition': 'jobposition',
        'position': 'jobposition',
        'job': 'jobposition',
        'jabatan': 'jobposition',
        'posisi': 'jobposition',
        'role': 'jobposition',
        
        # Shift variations
        'shift': 'shift',
        'shifts': 'shift',
        'workshift': 'shift',
        'jadwal': 'shift',
        
        # Duration variations
        'duration': 'duration',
        'durasi': 'duration',
        'lama': 'duration',
        'totalhours': 'duration',
        'hours': 'duration',
        'jam': 'duration',
        'overtimehours': 'duration',
        
        # WT/Normal variations
        'wtnormal': 'wtnormal',
        'wt': 'wtnormal',
        'normal': 'wtnormal',
        'workingtime': 'wtnormal',
        'worktime': 'wtnormal',
        'waktukerja': 'wtnormal',
        'regularhours': 'wtnormal',
        'normalhours': 'wtnormal',
        
        # RKP PIC variations
        'rkppic': 'rkppic',
        'rkp': 'rkppic',
        'pic': 'rkppic',
        'rekap': 'rkppic',
        'project': 'rkppic',
        
        # Work Area variations
        'workarea': 'workarea',
        'area': 'workarea',
        'department': 'workarea',
        'dept': 'workarea',
        'bagian': 'workarea',
        'lokasi': 'workarea'
    }
    
    return column_mapping.get(col, col)

def clean_dataframe(df):
    """Membersihkan dataframe: normalisasi nama kolom dan data"""
    # Normalize column names
    df.columns = [normalize_column_name(col) for col in df.columns]
    
    # Clean string data
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].astype(str).str.lower().str.strip()
    
    return df

def detect_wt_normal_column(df, available_columns):
    """Mendeteksi kolom yang bisa digunakan sebagai WT/Normal"""
    wt_normal_patterns = [
        'totalproject', 'totalplant', 'volume', 'project', 'plant',
        'task', 'action', 'work', 'production', 'output'
    ]
    
    for col in available_columns:
        col_normalized = normalize_column_name(col)
        for pattern in wt_normal_patterns:
            if pattern in col_normalized:
                return col
    return None

def process_attendance_data(df):
    """Memproses data absensi"""
    df = clean_dataframe(df)
    
    st.write("🔍 Kolom yang terdeteksi di file absen:", list(df.columns))
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['employeename', 'date', 'shift']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Kolom yang tidak ditemukan dalam file absen: {missing_cols}")
        return None
    
    # Konversi tanggal
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
    except Exception as e:
        st.error(f"Error konversi tanggal: {e}")
        return None
    
    st.success("✅ Data absen berhasil diproses")
    return df

def process_overtime_data(df):
    """Memproses data overtime"""
    df = clean_dataframe(df)
    
    st.write("🔍 Kolom yang terdeteksi di file overtime:", list(df.columns))
    
    # Pastikan kolom dasar ada
    required_cols = ['employeename', 'date']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ Kolom yang tidak ditemukan dalam file overtime: {missing_cols}")
        return None
    
    # Deteksi kolom duration
    if 'duration' not in df.columns:
        st.warning("⚠️ Kolom 'duration' tidak ditemukan, menggunakan nilai default 0")
        df['duration'] = 0
    else:
        df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(0)
    
    # Deteksi kolom WT/Normal
    if 'wtnormal' not in df.columns:
        available_cols = list(df.columns)
        wt_normal_col = detect_wt_normal_column(df, available_cols)
        
        if wt_normal_col:
            st.info(f"🎯 Menggunakan kolom '{wt_normal_col}' sebagai WT/Normal")
            # Coba konversi ke numeric, jika tidak bisa gunakan count
            df['wtnormal'] = pd.to_numeric(df[wt_normal_col], errors='coerce')
            if df['wtnormal'].isna().all():
                # Jika tidak bisa dikonversi, gunakan count (1 untuk setiap entri)
                df['wtnormal'] = 1
            else:
                df['wtnormal'] = df['wtnormal'].fillna(0)
        else:
            st.warning("⚠️ Kolom WT/Normal tidak ditemukan, menggunakan nilai default 1")
            df['wtnormal'] = 1
    else:
        df['wtnormal'] = pd.to_numeric(df['wtnormal'], errors='coerce').fillna(0)
    
    # Konversi tanggal
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
    except Exception as e:
        st.error(f"Error konversi tanggal: {e}")
        return None
    
    st.success("✅ Data overtime berhasil diproses")
    return df

def merge_data(attendance_df, overtime_df):
    """Menggabungkan data absen dan overtime"""
    try:
        # Clean kedua dataframe
        attendance_df = clean_dataframe(attendance_df)
        overtime_df = clean_dataframe(overtime_df)
        
        st.write("🔄 Melakukan merge data...")
        st.write("Data absen columns:", list(attendance_df.columns))
        st.write("Data overtime columns:", list(overtime_df.columns))
        
        # Merge data berdasarkan Employee Name dan Date
        merged_df = pd.merge(
            attendance_df,
            overtime_df[['employeename', 'date', 'duration', 'wtnormal']],
            on=['employeename', 'date'],
            how='left',
            suffixes=('', '_overtime')
        )
        
        # Isi kolom RKP PIC dengan duration dari overtime
        merged_df['rkppic'] = merged_df['duration'].fillna(0)
        
        st.success("✅ Data berhasil di-merge")
        return merged_df
    
    except Exception as e:
        st.error(f"❌ Error merging data: {e}")
        return None

def calculate_summary(attendance_df, overtime_df):
    """Menghitung summary data"""
    try:
        # Clean data
        attendance_df = clean_dataframe(attendance_df)
        overtime_df = clean_dataframe(overtime_df)
        
        st.write("📊 Menghitung summary...")
        
        # Hitung hari kerja (D/Work) - exclude libur/off/cuti
        def count_work_days(shifts):
            work_shifts = ['pagi', 'siang', 'sore', 'malam', 'shift', 'normal', 
                          'morning', 'evening', 'day', 'night', 'kerja']
            non_work_shifts = ['off', 'libur', 'cuti', 'leave', 'absent', 'alpha']
            
            count = 0
            for shift in shifts:
                if isinstance(shift, str):
                    shift_lower = shift.lower()
                    # Jika mengandung kata kerja dan tidak mengandung kata non-kerja
                    if any(work in shift_lower for work in work_shifts) and \
                       not any(non_work in shift_lower for non_work in non_work_shifts):
                        count += 1
                elif pd.notna(shift):
                    # Jika bukan string tapi ada nilai, anggap sebagai hari kerja
                    count += 1
            return count
        
        # Group by employee untuk data absensi
        attendance_summary = attendance_df.groupby('employeename').agg({
            'jobposition': 'first',
            'shift': count_work_days
        }).reset_index()
        
        attendance_summary.columns = ['employeename', 'jobposition', 'dwork']
        
        # Group by employee untuk data overtime
        overtime_summary = overtime_df.groupby('employeename').agg({
            'wtnormal': 'sum',
            'duration': 'sum'
        }).reset_index()
        
        overtime_summary.columns = ['employeename', 'wtnormal', 'rkppic']
        
        # Gabungkan data summary
        summary_df = pd.merge(
            attendance_summary,
            overtime_summary,
            on='employeename',
            how='left'
        ).fillna(0)
        
        # Urutkan kolom sesuai permintaan
        summary_df = summary_df[['employeename', 'jobposition', 'dwork', 'wtnormal', 'rkppic']]
        
        # Tambahkan nomor urut
        summary_df.insert(0, 'no', range(1, len(summary_df) + 1))
        
        # Format kolom numeric
        summary_df['wtnormal'] = summary_df['wtnormal'].round(2)
        summary_df['rkppic'] = summary_df['rkppic'].round(2)
        
        st.success("✅ Summary berhasil dihitung")
        return summary_df
    
    except Exception as e:
        st.error(f"❌ Error calculating summary: {e}")
        return None

def main():
    st.title("📊 Sistem Management Absen & Overtime")
    st.markdown("**Normalisasi Otomatis Kolom** - Aplikasi akan mendeteksi kolom secara otomatis")
    
    # Upload files
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Upload File Absen")
        attendance_file = st.file_uploader(
            "Upload file absensi (Excel/CSV)", 
            type=['xlsx', 'xls', 'csv'],
            key="attendance"
        )
    
    with col2:
        st.subheader("⏰ Upload File Overtime")
        overtime_file = st.file_uploader(
            "Upload file rekap overtime (Excel/CSV)", 
            type=['xlsx', 'xls', 'csv'],
            key="overtime"
        )
    
    if attendance_file is not None and overtime_file is not None:
        try:
            # Baca file berdasarkan tipe
            if attendance_file.name.endswith('.csv'):
                attendance_df = pd.read_csv(attendance_file)
            else:
                attendance_df = pd.read_excel(attendance_file)
            
            if overtime_file.name.endswith('.csv'):
                overtime_df = pd.read_csv(overtime_file)
            else:
                overtime_df = pd.read_excel(overtime_file)
            
            # Tampilkan preview data mentah
            with st.expander("🔍 Preview Data Mentah"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Data Absen (Original):**")
                    st.dataframe(attendance_df.head(5))
                    st.write(f"Shape: {attendance_df.shape}")
                with col2:
                    st.write("**Data Overtime (Original):**")
                    st.dataframe(overtime_df.head(5))
                    st.write(f"Shape: {overtime_df.shape}")
            
            # Proses data
            with st.spinner("🔄 Memproses data..."):
                attendance_processed = process_attendance_data(attendance_df)
                overtime_processed = process_overtime_data(overtime_df)
                
                if attendance_processed is not None and overtime_processed is not None:
                    # Gabungkan data
                    merged_data = merge_data(attendance_processed, overtime_processed)
                    
                    if merged_data is not None:
                        # Hitung summary
                        summary_data = calculate_summary(attendance_processed, overtime_processed)
                        
                        # Tampilkan dalam tabs
                        tab1, tab2, tab3 = st.tabs(["📋 Data Absen", "⏰ Data Overtime", "📊 Summary"])
                        
                        with tab1:
                            st.subheader("Data Absen (Processed)")
                            st.dataframe(attendance_processed, use_container_width=True)
                            
                            # Download button untuk data absen
                            csv_attendance = attendance_processed.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Data Absen (CSV)",
                                data=csv_attendance,
                                file_name="data_absen_processed.csv",
                                mime="text/csv"
                            )
                        
                        with tab2:
                            st.subheader("Data Overtime (Merged)")
                            st.dataframe(merged_data, use_container_width=True)
                            
                            # Download button untuk data overtime merged
                            csv_overtime = merged_data.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Data Overtime Merged (CSV)",
                                data=csv_overtime,
                                file_name="data_overtime_merged.csv",
                                mime="text/csv"
                            )
                        
                        with tab3:
                            st.subheader("📈 Summary Data")
                            if summary_data is not None:
                                st.dataframe(summary_data, use_container_width=True)
                                
                                # Statistik ringkas
                                st.subheader("📊 Statistik Ringkas")
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("Total Karyawan", len(summary_data))
                                
                                with col2:
                                    total_dwork = summary_data['dwork'].sum()
                                    st.metric("Total Hari Kerja", int(total_dwork))
                                
                                with col3:
                                    total_wt = summary_data['wtnormal'].sum()
                                    st.metric("Total WT/Normal", f"{total_wt:.2f}")
                                
                                with col4:
                                    total_rkp = summary_data['rkppic'].sum()
                                    st.metric("Total RKP PIC", f"{total_rkp:.2f}")
                                
                                # Download button untuk summary
                                csv_summary = summary_data.to_csv(index=False)
                                st.download_button(
                                    label="📥 Download Summary (CSV)",
                                    data=csv_summary,
                                    file_name="summary_data.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.error("Gagal menghitung summary data")
                
        except Exception as e:
            st.error(f"❌ Error processing files: {str(e)}")
            st.info("💡 Pastikan file yang diupload formatnya benar (Excel/CSV) dan tidak corrupt")
    
    else:
        # Tampilkan panduan jika belum upload file
        st.info("""
        ### 📋 Panduan Upload File:
        
        **File Absen harus mengandung kolom:**
        - Employee Name (atau: nama, employee, empname, staffname)
        - Date (atau: tanggal, workdate)  
        - Shift (atau: shifts, workshift)
        
        **File Overtime harus mengandung kolom:**
        - Employee Name 
        - Date
        
        **Kolom Opsional yang akan dideteksi otomatis:**
        - Duration (atau: durasi, hours, jam, overtimehours)
        - WT/Normal (atau: wt, normal, workingtime, worktime)
        
        **Fitur Normalisasi:**
        - ✅ Auto-detect kolom berdasarkan pattern
        - ✅ Case-insensitive matching
        - ✅ Flexible column naming
        - ✅ Handle missing columns dengan nilai default
        - ✅ Preview data untuk debugging
        """)

if __name__ == "__main__":
    main()
