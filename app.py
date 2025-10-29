import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

# Konfigurasi halaman
st.set_page_config(
    page_title="Sistem Absen & Overtime",
    page_icon="📊",
    layout="wide"
)

def clean_column_name(col):
    """Membersihkan nama kolom: lowercase, hapus spasi berlebih"""
    if isinstance(col, str):
        return col.lower().replace(' ', '').strip()
    return col

def clean_dataframe(df):
    """Membersihkan dataframe: nama kolom dan data"""
    # Clean column names
    df.columns = [clean_column_name(col) for col in df.columns]
    
    # Clean string data
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].astype(str).str.lower().str.strip()
    
    return df

def process_attendance_data(df):
    """Memproses data absensi"""
    df = clean_dataframe(df)
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['employeename', 'date', 'shift', 'jobposition']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Kolom {col} tidak ditemukan dalam file absen. Kolom yang tersedia: {list(df.columns)}")
            return None
    
    # Konversi tanggal
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    
    return df

def process_overtime_data(df):
    """Memproses data overtime"""
    df = clean_dataframe(df)
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['employeename', 'date', 'duration', 'wt/normal']
    for col in required_cols:
        if col not in df.columns:
            st.error(f"Kolom {col} tidak ditemukan dalam file overtime. Kolom yang tersedia: {list(df.columns)}")
            return None
    
    # Konversi tanggal
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date'])
    
    # Konversi numeric columns
    df['duration'] = pd.to_numeric(df['duration'], errors='coerce')
    df['wt/normal'] = pd.to_numeric(df['wt/normal'], errors='coerce')
    
    return df

def merge_data(attendance_df, overtime_df):
    """Menggabungkan data absen dan overtime"""
    # Clean kedua dataframe
    attendance_df = clean_dataframe(attendance_df)
    overtime_df = clean_dataframe(overtime_df)
    
    # Merge data berdasarkan Employee Name dan Date
    merged_df = pd.merge(
        attendance_df,
        overtime_df[['employeename', 'date', 'duration', 'wt/normal']],
        on=['employeename', 'date'],
        how='left',
        suffixes=('', '_overtime')
    )
    
    # Isi kolom RKP PIC dengan duration dari overtime
    merged_df['rkppic'] = merged_df['duration'].fillna(0)
    
    return merged_df

def calculate_summary(attendance_df, overtime_df):
    """Menghitung summary data"""
    # Clean data
    attendance_df = clean_dataframe(attendance_df)
    overtime_df = clean_dataframe(overtime_df)
    
    # Group by employee untuk data absensi
    attendance_summary = attendance_df.groupby('employeename').agg({
        'jobposition': 'first',
        'shift': lambda x: x.count()  # Hitung hari kerja
    }).reset_index()
    
    attendance_summary.columns = ['employeename', 'jobposition', 'd/work']
    
    # Group by employee untuk data overtime
    overtime_summary = overtime_df.groupby('employeename').agg({
        'wt/normal': 'sum',
        'duration': 'sum'
    }).reset_index()
    
    overtime_summary.columns = ['employeename', 'wt/normal', 'rkppic']
    
    # Gabungkan data summary
    summary_df = pd.merge(
        attendance_summary,
        overtime_summary,
        on='employeename',
        how='left'
    ).fillna(0)
    
    # Urutkan kolom sesuai permintaan
    summary_df = summary_df[['employeename', 'jobposition', 'd/work', 'wt/normal', 'rkppic']]
    
    # Tambahkan nomor urut
    summary_df.insert(0, 'no', range(1, len(summary_df) + 1))
    
    return summary_df

def main():
    st.title("📊 Sistem Management Absen & Overtime")
    
    # Upload files
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload File Absen")
        attendance_file = st.file_uploader(
            "Upload file absensi (Excel/CSV)", 
            type=['xlsx', 'xls', 'csv'],
            key="attendance"
        )
    
    with col2:
        st.subheader("Upload File Overtime")
        overtime_file = st.file_uploader(
            "Upload file rekap overtime (Excel/CSV)", 
            type=['xlsx', 'xls', 'csv'],
            key="overtime"
        )
    
    if attendance_file and overtime_file:
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
            
            # Proses data
            with st.spinner("Memproses data..."):
                attendance_processed = process_attendance_data(attendance_df)
                overtime_processed = process_overtime_data(overtime_df)
                
                if attendance_processed is not None and overtime_processed is not None:
                    # Gabungkan data
                    merged_data = merge_data(attendance_processed, overtime_processed)
                    
                    # Hitung summary
                    summary_data = calculate_summary(attendance_processed, overtime_processed)
                    
                    # Tampilkan dalam tabs
                    tab1, tab2, tab3 = st.tabs(["Data Absen", "Data Overtime", "Summary"])
                    
                    with tab1:
                        st.subheader("Data Absen")
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
                        st.subheader("Summary Data")
                        st.dataframe(summary_data, use_container_width=True)
                        
                        # Statistik ringkas
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Total Karyawan", len(summary_data))
                        
                        with col2:
                            total_dwork = summary_data['d/work'].sum()
                            st.metric("Total Hari Kerja", int(total_dwork))
                        
                        with col3:
                            total_wt = summary_data['wt/normal'].sum()
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
                
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")
    
    else:
        # Tampilkan panduan jika belum upload file
        st.info("""
        ### 📋 Panduan Upload File:
        
        **File Absen harus mengandung kolom:**
        - Employee Name
        - Date
        - Shift
        - Job Position
        
        **File Overtime harus mengandung kolom:**
        - Employee Name
        - Date
        - Duration
        - WT/Normal
        
        **Fitur yang tersedia:**
        - ✅ Auto-merge data berdasarkan Employee Name dan Date
        - ✅ Auto-fill RKP PIC dari Duration
        - ✅ Summary otomatis dengan kolom: No, Employee Name, Job Position, D/Work, WT/Normal, RKP PIC
        - ✅ Case-insensitive matching (tidak peduli huruf besar/kecil)
        - ✅ Download hasil processing
        """)

if __name__ == "__main__":
    main()
