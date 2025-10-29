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
        return col.lower().replace(' ', '').replace('/', '').strip()
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
    
    # Mapping nama kolom yang mungkin berbeda
    column_mapping = {
        'employee': 'employeename',
        'name': 'employeename',
        'empname': 'employeename',
        'position': 'jobposition',
        'job': 'jobposition',
        'workdate': 'date',
        'tanggal': 'date'
    }
    
    # Rename columns jika ada yang match
    df.columns = [column_mapping.get(col, col) for col in df.columns]
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['employeename', 'date', 'shift']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"Kolom yang tidak ditemukan: {missing_cols}")
        st.info(f"Kolom yang tersedia: {list(df.columns)}")
        return None
    
    # Konversi tanggal
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
    except Exception as e:
        st.error(f"Error konversi tanggal: {e}")
        return None
    
    return df

def process_overtime_data(df):
    """Memproses data overtime"""
    df = clean_dataframe(df)
    
    # Mapping nama kolom
    column_mapping = {
        'employee': 'employeename',
        'name': 'employeename',
        'empname': 'employeename',
        'workdate': 'date',
        'tanggal': 'date',
        'durasi': 'duration',
        'wt': 'wtnormal',
        'normal': 'wtnormal'
    }
    
    # Rename columns jika ada yang match
    df.columns = [column_mapping.get(col, col) for col in df.columns]
    
    # Pastikan kolom yang diperlukan ada
    required_cols = ['employeename', 'date']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"Kolom yang tidak ditemukan: {missing_cols}")
        st.info(f"Kolom yang tersedia: {list(df.columns)}")
        return None
    
    # Konversi tanggal
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
    except Exception as e:
        st.error(f"Error konversi tanggal: {e}")
        return None
    
    # Konversi numeric columns jika ada
    if 'duration' in df.columns:
        df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(0)
    
    if 'wtnormal' in df.columns:
        df['wtnormal'] = pd.to_numeric(df['wtnormal'], errors='coerce').fillna(0)
    
    return df

def merge_data(attendance_df, overtime_df):
    """Menggabungkan data absen dan overtime"""
    try:
        # Clean kedua dataframe
        attendance_df = clean_dataframe(attendance_df)
        overtime_df = clean_dataframe(overtime_df)
        
        # Merge data berdasarkan Employee Name dan Date
        merged_df = pd.merge(
            attendance_df,
            overtime_df,
            on=['employeename', 'date'],
            how='left',
            suffixes=('', '_overtime')
        )
        
        # Isi kolom RKP PIC dengan duration dari overtime
        if 'duration' in merged_df.columns:
            merged_df['rkppic'] = merged_df['duration'].fillna(0)
        else:
            merged_df['rkppic'] = 0
        
        return merged_df
    
    except Exception as e:
        st.error(f"Error merging data: {e}")
        return None

def calculate_summary(attendance_df, overtime_df):
    """Menghitung summary data"""
    try:
        # Clean data
        attendance_df = clean_dataframe(attendance_df)
        overtime_df = clean_dataframe(overtime_df)
        
        # Hitung hari kerja (D/Work) - exclude libur/off/cuti
        def count_work_days(shifts):
            # Anggap shift yang bukan 'off', 'libur', 'cuti', 'leave' sebagai hari kerja
            work_shifts = ['pagi', 'siang', 'sore', 'malam', 'shift', 'normal', 'morning', 'evening', 'day', 'night']
            count = 0
            for shift in shifts:
                if isinstance(shift, str) and any(work in shift.lower() for work in work_shifts):
                    count += 1
            return count
        
        # Group by employee untuk data absensi
        attendance_summary = attendance_df.groupby('employeename').agg({
            'jobposition': 'first',
            'shift': count_work_days
        }).reset_index()
        
        attendance_summary.columns = ['employeename', 'jobposition', 'dwork']
        
        # Group by employee untuk data overtime
        overtime_agg = {}
        if 'wtnormal' in overtime_df.columns:
            overtime_agg['wtnormal'] = 'sum'
        if 'duration' in overtime_df.columns:
            overtime_agg['duration'] = 'sum'
        
        if overtime_agg:
            overtime_summary = overtime_df.groupby('employeename').agg(overtime_agg).reset_index()
            
            # Rename columns sesuai kebutuhan
            if 'wtnormal' in overtime_summary.columns:
                overtime_summary = overtime_summary.rename(columns={'wtnormal': 'wtnormal_sum'})
            if 'duration' in overtime_summary.columns:
                overtime_summary = overtime_summary.rename(columns={'duration': 'rkppic'})
        else:
            # Buat dataframe kosong jika tidak ada kolom overtime
            overtime_summary = pd.DataFrame(columns=['employeename', 'wtnormal_sum', 'rkppic'])
        
        # Gabungkan data summary
        summary_df = pd.merge(
            attendance_summary,
            overtime_summary,
            on='employeename',
            how='left'
        ).fillna(0)
        
        # Pastikan kolom yang diperlukan ada
        if 'wtnormal_sum' not in summary_df.columns:
            summary_df['wtnormal_sum'] = 0
        if 'rkppic' not in summary_df.columns:
            summary_df['rkppic'] = 0
        
        # Urutkan kolom sesuai permintaan
        summary_df = summary_df[['employeename', 'jobposition', 'dwork', 'wtnormal_sum', 'rkppic']]
        summary_df.columns = ['employeename', 'jobposition', 'dwork', 'wtnormal', 'rkppic']
        
        # Tambahkan nomor urut
        summary_df.insert(0, 'no', range(1, len(summary_df) + 1))
        
        return summary_df
    
    except Exception as e:
        st.error(f"Error calculating summary: {e}")
        return None

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
            with st.expander("Preview Data Mentah"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Data Absen (Original):")
                    st.dataframe(attendance_df.head(3))
                with col2:
                    st.write("Data Overtime (Original):")
                    st.dataframe(overtime_df.head(3))
            
            # Proses data
            with st.spinner("Memproses data..."):
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
                            if summary_data is not None:
                                st.dataframe(summary_data, use_container_width=True)
                                
                                # Statistik ringkas
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
            st.error(f"Error processing files: {str(e)}")
            st.info("Pastikan file yang diupload formatnya benar (Excel/CSV) dan tidak corrupt")
    
    else:
        # Tampilkan panduan jika belum upload file
        st.info("""
        ### 📋 Panduan Upload File:
        
        **File Absen harus mengandung kolom:**
        - Employee Name (atau nama, employee, empname)
        - Date (atau tanggal, workdate)  
        - Shift
        - Job Position (opsional)
        
        **File Overtime harus mengandung kolom:**
        - Employee Name (atau nama, employee, empname)
        - Date (atau tanggal, workdate)
        - Duration (opsional)
        - WT/Normal (opsional)
        
        **Fitur yang tersedia:**
        - ✅ Auto-merge data berdasarkan Employee Name dan Date
        - ✅ Auto-fill RKP PIC dari Duration
        - ✅ Summary otomatis dengan kolom yang diminta
        - ✅ Case-insensitive matching
        - ✅ Flexible column naming
        - ✅ Download hasil processing
        """)

if __name__ == "__main__":
    main()
