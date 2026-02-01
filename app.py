import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time
import barcode
from barcode.writer import ImageWriter
import io
import base64

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Laju Logistics", page_icon="🚚", layout="wide")

# --- STYLE & TEMA (Navy, Orange, Cream) ---
def local_css(dark_mode):
    if dark_mode:
        bg_color = "#1a1a2e" # Very Dark Navy
        text_color = "#ffffff"
        card_bg = "#16213e"
    else:
        bg_color = "#fdfbf7" # Cream
        text_color = "#0f3460" # Navy
        card_bg = "#ffffff"
    
    css = f"""
    <style>
    .stApp {{
        background-color: {bg_color};
        color: {text_color};
    }}
    /* Warna Utama Navy & Orange */
    :root {{
        --primary-navy: #0f3460;
        --accent-orange: #e94560;
    }}
    /* Tombol */
    .stButton>button {{
        background-color: #e94560;
        color: white;
        border-radius: 8px;
        border: none;
    }}
    .stButton>button:hover {{
        background-color: #c72c41;
    }}
    /* Header Styles */
    h1, h2, h3 {{
        color: #0f3460 !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: #0f3460;
    }}
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    /* Metric Cards */
    div[data-testid="metric-container"] {{
        background-color: {card_bg};
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }}
    
    /* Animasi Kereta */
    @keyframes drive {{
        from {{ transform: translateX(-100%); }}
        to {{ transform: translateX(100%); }}
    }}
    .train-container {{
        width: 100%;
        overflow: hidden;
        white-space: nowrap;
        margin-bottom: 20px;
    }}
    .train-icon {{
        display: inline-block;
        font-size: 2rem;
        animation: drive 10s linear infinite;
        color: #e94560;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --- KONEKSI GOOGLE SHEETS ---
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # Mengambil kredensial dari st.secrets
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

def get_data(sheet_name):
    client = get_gspread_client()
    # Ganti URL ini dengan URL Sheet Anda jika error, atau pastikan nama sheet benar
    sheet = client.open_by_url(st.secrets["sheets_url"]).worksheet(sheet_name)
    return sheet

# --- HELPER FUNCTIONS ---
def generate_resi():
    # Format: LJ-YYYYMMDD-HHMMSS
    return f"LJ-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

def generate_barcode(resi):
    rv = io.BytesIO()
    code128 = barcode.get_barcode_class('code128')
    code128(resi, writer=ImageWriter()).write(rv)
    return base64.b64encode(rv.getvalue()).decode()

def hitung_biaya(layanan, berat, panjang, lebar, tinggi, harga_barang, pakai_garansi):
    # Hitung Volume
    volume = panjang * lebar * tinggi
    berat_volumetrik = volume / 6000 # Standar logistik
    berat_akhir = max(berat, berat_volumetrik)
    
    biaya_kirim = 0
    surcharge = 0
    
    # Logika Ongkir
    if layanan == 'Express':
        berat_calc = max(1, berat_akhir)
        biaya_kirim = berat_calc * 17000
    elif layanan == 'Cargo':
        berat_calc = max(10, berat_akhir)
        biaya_kirim = berat_calc * 4000
        if volume > (40*40*40):
             # Surcharge +1500 per 250cm3 kelebihan (Simulasi sederhana)
             excess = volume - 64000
             surcharge = (excess / 250) * 1500
    elif layanan == 'Makanan':
        berat_calc = max(1, berat_akhir)
        biaya_kirim = berat_calc * 5000
        
    biaya_kirim += surcharge
    
    # Logika Garansi
    biaya_garansi = 0
    if pakai_garansi:
        if layanan == 'Express':
            biaya_garansi = harga_barang * 0.005
        elif layanan == 'Cargo':
            biaya_garansi = harga_barang * 0.003
        elif layanan == 'Makanan':
            biaya_garansi = 5000
            
    return biaya_kirim, biaya_garansi

# --- STATE MANAGEMENT ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = False
if 'page' not in st.session_state:
    st.session_state['page'] = 'Login'

local_css(st.session_state['dark_mode'])

# --- HALAMAN LOGIN ---
def login_page():
    st.markdown("<div class='train-container'><div class='train-icon'>🚚 💨 LAJU LOGISTICS 💨 🚚</div></div>", unsafe_allow_html=True)
    st.title("Login Laju App")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            try:
                sheet = get_data("User")
                users = sheet.get_all_records()
                df = pd.DataFrame(users)
                
                # Cek User
                user = df[(df['Nama'] == username) & (df['Password'] == str(password))]
                
                if not user.empty:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user.iloc[0].to_dict()
                    st.session_state['page'] = 'Dashboard'
                    st.success("Login Berhasil! Selamat datang di Laju.")
                    st.rerun()
                else:
                    st.error("Username/Password salah, silahkan coba lagi")
            except Exception as e:
                st.error(f"Gagal koneksi database: {e}")

# --- HALAMAN DASHBOARD ---
def dashboard_page():
    user = st.session_state['user_info']
    
    # Layout Header
    col1, col2 = st.columns([1, 4])
    with col1:
        # Placeholder foto jika kosong
        foto = user.get('Foto_URL', '')
        if not foto: foto = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
        st.image(foto, width=100)
    with col2:
        st.subheader(f"Halo, {user['Nama']}")
        st.text(f"{user['Jabatan']} - {user['Cabang']}")

    st.markdown("---")
    
    # Metrics
    try:
        df_active = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        total_paket = len(df_active)
        total_kirim = len(df_active[df_active['Status'] == 'Diproses'])
        total_transit = len(df_active[df_active['Status'].str.contains('Transit', na=False)])
        # Hitung Pendapatan (Simple Sum)
        pendapatan = df_active['Total_Ongkir'].sum() if not df_active.empty else 0
    except:
        total_paket, total_kirim, total_transit, pendapatan = 0, 0, 0, 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Paket Hari Ini", total_paket)
    m2.metric("Siap Kirim", total_kirim)
    m3.metric("Transit", total_transit)
    m4.metric("Pendapatan", f"Rp {pendapatan:,.0f}")
    
    st.markdown("### Menu Cepat")
    c1, c2, c3 = st.columns(3)
    if c1.button("📦 Input Pengiriman"): st.session_state['page'] = 'Input Pengiriman'
    if c2.button("truck Transit / Scan"): st.session_state['page'] = 'Transit'
    if c3.button("🔍 Tracking Publik"): st.session_state['page'] = 'Tracking'

# --- HALAMAN INPUT & PEMBAYARAN ---
def input_pengiriman_page():
    st.header("Formulir Input Pengiriman")
    
    if 'form_data' not in st.session_state:
        st.session_state['form_data'] = {}

    with st.form("input_form"):
        # Auto Gen Resi
        resi_baru = generate_resi()
        st.markdown(f"**No. Resi:** `{resi_baru}` (Auto)")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Data Pengirim")
            pengirim = st.text_input("Nama Pengirim")
            telp_pengirim = st.text_input("No. Telp Pengirim")
            alamat_pengirim = st.text_area("Alamat Pengirim")
        with c2:
            st.subheader("Data Penerima")
            penerima = st.text_input("Nama Penerima")
            telp_penerima = st.text_input("No. Telp Penerima")
            prov = st.text_input("Provinsi")
            kota = st.text_input("Kota/Kabupaten")
            kec = st.text_input("Kecamatan")
            kel = st.text_input("Kelurahan")
            kodepos = st.text_input("Kode Pos")
        
        st.markdown("---")
        st.subheader("Detail Paket")
        c3, c4 = st.columns(2)
        with c3:
            panjang = st.number_input("Panjang (cm)", min_value=1)
            lebar = st.number_input("Lebar (cm)", min_value=1)
            tinggi = st.number_input("Tinggi (cm)", min_value=1)
            berat = st.number_input("Berat (kg)", min_value=1.0)
            qty = st.number_input("Qty", min_value=1)
        with c4:
            layanan = st.selectbox("Layanan", ["Express", "Cargo", "Makanan"])
            pakai_garansi = st.checkbox("Tambah Layanan Garansi")
            harga_barang = 0.0
            biaya_garansi_val = 0.0
            
            # Logic Realtime (Streamlit rerun on checkbox change required usually, 
            # but inside form we calc on submit or use session state outside form. 
            # For simplicity, we create a sub-container logic if possible, but st.form limits interactivity.
            # We will ask user to input price, calc happens on 'Lanjut')
            
            if pakai_garansi:
                harga_barang = st.number_input("Harga Barang (Rp)", min_value=0.0)
                st.caption("Biaya garansi akan dihitung otomatis di halaman pembayaran.")

        submitted = st.form_submit_button("Lanjutkan ke Pembayaran")
        
        if submitted:
            # Hitung Biaya
            biaya_kirim, biaya_garansi = hitung_biaya(layanan, berat, panjang, lebar, tinggi, harga_barang, pakai_garansi)
            
            st.session_state['form_data'] = {
                "No_Resi": resi_baru,
                "Tanggal": str(datetime.now()),
                "Nama_Pengirim": pengirim, "Telp_Pengirim": telp_pengirim, "Alamat_Pengirim": alamat_pengirim,
                "Nama_Penerima": penerima, "Telp_Penerima": telp_penerima, 
                "Provinsi": prov, "Kota": kota, "Kecamatan": kec, "Kelurahan": kel, "Kode_Pos": kodepos,
                "Panjang": panjang, "Lebar": lebar, "Tinggi": tinggi, "Berat": berat, "Qty": qty,
                "Layanan": layanan, "Harga_Barang": harga_barang, "Biaya_Garansi": biaya_garansi,
                "Biaya_Kirim_Dasar": biaya_kirim,
                "Status": "Diproses"
            }
            st.session_state['page'] = 'Pembayaran'
            st.rerun()

def pembayaran_page():
    st.header("Halaman Pembayaran & Cetak Resi")
    data = st.session_state.get('form_data', {})
    
    if not data:
        st.warning("Data kosong, kembali ke input.")
        return

    # Hitung Total
    biaya_dasar = data['Biaya_Kirim_Dasar']
    garansi = data['Biaya_Garansi']
    total_awal = biaya_dasar + garansi
    
    # Pilih Pembayaran
    metode = st.radio("Pilihan Pembayaran", ["COD", "Prepaid (Transfer/Cash)"])
    
    biaya_admin = 0
    if metode == "COD":
        if total_awal < 100000:
            biaya_admin = total_awal * 0.05
        else:
            biaya_admin = total_awal * 0.025
    
    total_akhir = total_awal + biaya_admin
    
    # Tampilkan Rincian
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Rincian Biaya ({data['Layanan']})**")
        st.write(f"Ongkir Dasar: Rp {biaya_dasar:,.0f}")
        st.write(f"Garansi: Rp {garansi:,.0f}")
        st.write(f"Biaya Admin/COD: Rp {biaya_admin:,.0f}")
        st.markdown(f"### TOTAL: Rp {total_akhir:,.0f}")
    
    with col2:
        st.warning("Konfirmasi")
        
        # Logic Tombol
        btn_sudah_bayar = False
        btn_cetak = False
        
        if 'pembayaran_selesai' not in st.session_state:
            st.session_state['pembayaran_selesai'] = False
            
        if metode == "Prepaid (Transfer/Cash)":
            if not st.session_state['pembayaran_selesai']:
                if st.button("💰 Sudah Bayar"):
                    st.session_state['pembayaran_selesai'] = True
                    st.success("Pembayaran Diterima!")
                    st.rerun()
            else:
                st.success("Status: LUNAS")
                btn_cetak = True
        else: # COD
            st.info("Pembayaran dilakukan saat barang sampai.")
            btn_cetak = True
            
        if btn_cetak:
            if st.button("🖨️ Simpan Data & Cetak Resi"):
                # Simpan ke GSheets
                try:
                    sheet = get_data("Data ( Active )")
                    # Susun row sesuai urutan kolom sheet (simplified)
                    # ['No_Resi', 'Tanggal', 'Nama_Pengirim', ..., 'Total_Ongkir', 'Tipe_Pembayaran', 'Metode_Bayar', 'Sudah_Bayar']
                    row = [
                        data['No_Resi'], str(datetime.now().date()), 
                        data['Nama_Pengirim'], data['Telp_Pengirim'], data['Alamat_Pengirim'],
                        data['Nama_Penerima'], data['Telp_Penerima'], 
                        data['Provinsi'], data['Kota'], data['Kecamatan'], data['Kelurahan'], data['Kode_Pos'], "", # Detail
                        "Diproses", 
                        data['Panjang'], data['Lebar'], data['Tinggi'], 
                        (data['Panjang']*data['Lebar']*data['Tinggi']), 
                        data['Berat'], data['Qty'], 
                        data['Layanan'], data['Harga_Barang'], data['Biaya_Garansi'],
                        total_akhir, 
                        metode, "Cash" if metode=="COD" else "Transfer", 
                        "Ya" if metode != "COD" else "Belum",
                        "", "" # Foto & Posisi
                    ]
                    sheet.append_row(row)
                    st.success("Data Tersimpan!")
                    
                    # Tampilan Resi HTML
                    b64_code = generate_barcode(data['No_Resi'])
                    resi_html = f"""
                    <div style="border: 2px dashed #0f3460; padding: 20px; width: 300px; background: white; color: black;">
                        <h2 style="margin:0; text-align:center; color: #e94560;">LAJU</h2>
                        <hr>
                        <p><strong>Resi:</strong> {data['No_Resi']}</p>
                        <img src="data:image/png;base64,{b64_code}" width="100%">
                        <p><strong>Pengirim:</strong> {data['Nama_Pengirim']}<br>
                        <strong>Penerima:</strong> {data['Nama_Penerima']}</p>
                        <p><strong>Tujuan:</strong> {data['Kota']}, {data['Provinsi']}</p>
                        <p><strong>Layanan:</strong> {data['Layanan']} ({metode})</p>
                        <hr>
                        <h3 style="text-align:right">Rp {total_akhir:,.0f}</h3>
                    </div>
                    <button onclick="window.print()">Cetak Resi</button>
                    """
                    st.components.v1.html(resi_html, height=500)
                    
                    # Reset Form
                    if st.button("Buat Pengiriman Baru"):
                        del st.session_state['form_data']
                        st.session_state['pembayaran_selesai'] = False
                        st.session_state['page'] = 'Input Pengiriman'
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error menyimpan data: {e}")

# --- HALAMAN TRANSIT ---
def transit_page():
    st.header("Update Status & Transit")
    
    method = st.radio("Metode Input", ["Manual", "Scan Kamera"])
    resi_input = ""
    
    if method == "Manual":
        resi_input = st.text_input("Masukkan No. Resi")
    else:
        # Camera input return buffer, not string directly usually needs decoding logic
        # For simplicity in this demo, we assume manual mainly or simple text scan
        st.info("Fitur Scan Barcode membutuhkan library khusus JS, silakan ketik manual untuk demo ini.")
        resi_input = st.text_input("No Resi (dari Scanner)")

    if st.button("Cari Data"):
        sheet = get_data("Data ( Active )")
        try:
            records = sheet.get_all_records()
            df = pd.DataFrame(records)
            result = df[df['No_Resi'] == resi_input]
            
            if not result.empty:
                st.session_state['transit_data'] = result.iloc[0].to_dict()
                st.session_state['transit_idx'] = result.index[0] + 2 # +2 krn header & 0-index
            else:
                st.error("Resi tidak ditemukan")
        except:
            st.error("Gagal load database")

    if 'transit_data' in st.session_state:
        data = st.session_state['transit_data']
        idx = st.session_state['transit_idx']
        
        with st.expander("Detail Paket", expanded=True):
            st.write(data)
            
        c1, c2 = st.columns(2)
        cabang_user = st.session_state['user_info']['Cabang']
        
        with c1:
            if st.button(f"Transit di {cabang_user}"):
                sheet = get_data("Data ( Active )")
                sheet.update_cell(idx, 14, f"Transit di {cabang_user}") # Asumsi kol 14 Status
                sheet.update_cell(idx, 29, cabang_user) # Posisi Terakhir
                st.success(f"Status updated: Transit di {cabang_user}")
        
        with c2:
            st.subheader("Diterima Customer")
            uploaded_file = st.file_uploader("Foto Bukti Penerimaan", type=['jpg','png'])
            
            if st.button("Konfirmasi Diterima"):
                if uploaded_file:
                    # Di real app, upload ke GDrive/S3 dan dapatkan Link.
                    # Disini kita simulasi link
                    fake_link = f"https://drive.google.com/file/d/foto_{resi_input}"
                    
                    sheet = get_data("Data ( Active )")
                    
                    # 1. Update Status & Foto
                    sheet.update_cell(idx, 14, "Diterima Customer")
                    sheet.update_cell(idx, 28, fake_link)
                    
                    # 2. Pindah ke Arsip
                    # Ambil data row lagi
                    final_row = sheet.row_values(idx)
                    final_row.append(str(datetime.now())) # Tambah Tanggal Diterima
                    
                    arsip_sheet = get_data("Arsip Data")
                    arsip_sheet.append_row(final_row)
                    
                    # 3. Hapus dari Active
                    sheet.delete_rows(idx)
                    
                    st.success("Paket Selesai! Data dipindah ke Arsip.")
                    del st.session_state['transit_data']
                    st.rerun()
                else:
                    st.error("Wajib upload foto bukti!")

# --- HALAMAN TRACKING (PUBLIK) ---
def tracking_page():
    st.title("Lacak Paket Laju")
    resi = st.text_input("Masukkan No. Resi Anda")
    
    if st.button("Lacak Paket"):
        found = False
        data_found = None
        source = ""
        
        try:
            # Cek Active
            sheet1 = get_data("Data ( Active )")
            df1 = pd.DataFrame(sheet1.get_all_records())
            res1 = df1[df1['No_Resi'] == resi]
            if not res1.empty:
                found = True
                data_found = res1.iloc[0]
                source = "Active"
            
            # Jika tidak ada, Cek Arsip
            if not found:
                sheet2 = get_data("Arsip Data")
                df2 = pd.DataFrame(sheet2.get_all_records())
                res2 = df2[df2['No_Resi'] == resi]
                if not res2.empty:
                    found = True
                    data_found = res2.iloc[0]
                    source = "Arsip"
                    
            if found:
                st.success(f"Paket Ditemukan! Status: {data_found['Status']}")
                st.markdown(f"**Penerima:** {data_found['Nama_Penerima']}")
                st.markdown(f"**Tujuan:** {data_found['Kota']}")
                
                # Timeline Simple
                st.markdown("### Riwayat Perjalanan")
                st.info(f"📅 {data_found['Tanggal']} - Paket diinput (Diproses)")
                if "Transit" in data_found['Status']:
                    st.warning(f"🚚 Paket sedang Transit di {data_found.get('Posisi_Terakhir', '-')}")
                if source == "Arsip" or data_found['Status'] == "Diterima Customer":
                    st.success(f"✅ Paket Telah Diterima")
                    if data_found.get('Foto_Bukti'):
                        st.write("Bukti Foto (Simulasi Link):", data_found['Foto_Bukti'])
            else:
                st.error("Waduh, No. Resi tidak ditemukan. Coba cek lagi ya!")
                
        except Exception as e:
            st.error(f"Terjadi kesalahan pencarian: {e}")

# --- HALAMAN ADMIN ---
def admin_page():
    st.title("Admin Dashboard")
    tab1, tab2, tab3 = st.tabs(["Data Active", "Arsip Mingguan", "Keuangan"])
    
    with tab1:
        st.subheader("Monitoring Paket Aktif")
        df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        if not df.empty:
            # Filter
            filter_svc = st.multiselect("Filter Layanan", df['Layanan'].unique())
            if filter_svc:
                df = df[df['Layanan'].isin(filter_svc)]
            
            # Styling color
            def color_status(val):
                color = 'red'
                if val == 'Diproses': color = 'lightgreen'
                elif 'Transit' in val: color = 'orange'
                elif 'Diterima' in val: color = 'lightblue'
                return f'background-color: {color}; color: black'
            
            st.dataframe(df.style.applymap(color_status, subset=['Status']))
            
    with tab2:
        st.subheader("Arsip Data (7 Hari Terakhir)")
        df_arsip = pd.DataFrame(get_data("Arsip Data").get_all_records())
        if not df_arsip.empty:
            # Filter Logic Date
            df_arsip['Tanggal_Diterima_Dt'] = pd.to_datetime(df_arsip['Tanggal_Diterima'], errors='coerce')
            last_7_days = datetime.now() - timedelta(days=7)
            df_filtered = df_arsip[df_arsip['Tanggal_Diterima_Dt'] >= last_7_days]
            
            st.dataframe(df_filtered)
            
            # Download
            csv = df_filtered.to_csv(index=False).encode('utf-8')
            st.download_button("Download Excel/CSV", csv, "laporan_mingguan.csv")
            
    with tab3:
        st.subheader("Laporan Keuangan")
        # Gabung data active dan arsip untuk total
        df1 = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        df2 = pd.DataFrame(get_data("Arsip Data").get_all_records())
        df_all = pd.concat([df1, df2])
        
        if not df_all.empty:
             # Konversi ke numerik
            df_all['Total_Ongkir'] = pd.to_numeric(df_all['Total_Ongkir'], errors='coerce')
            
            total_omzet = df_all['Total_Ongkir'].sum()
            total_cash = df_all[df_all['Metode_Bayar'] == 'Cash']['Total_Ongkir'].sum()
            total_trf = df_all[df_all['Metode_Bayar'] == 'Transfer']['Total_Ongkir'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Omzet", f"Rp {total_omzet:,.0f}")
            k2.metric("Total Cash (COD)", f"Rp {total_cash:,.0f}")
            k3.metric("Total Transfer", f"Rp {total_trf:,.0f}")
            
            st.write("Rincian Transaksi:")
            st.dataframe(df_all[['No_Resi', 'Total_Ongkir', 'Tipe_Pembayaran', 'Metode_Bayar']])

# --- MAIN CONTROLLER ---
def main():
    # Sidebar Navigation
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/7542/7542186.png", width=50) # Logo Laju Placeholder
        st.title("Navigasi")
        
        # Dark Mode Toggle
        if st.checkbox("🌙 Mode Gelap", value=st.session_state['dark_mode']):
            st.session_state['dark_mode'] = True
        else:
            st.session_state['dark_mode'] = False
            
        st.markdown("---")
        
        if st.session_state['logged_in']:
            if st.button("🏠 Dashboard"): st.session_state['page'] = 'Dashboard'
            if st.button("📦 Input Pengiriman"): st.session_state['page'] = 'Input Pengiriman'
            if st.button("🚚 Menu Transit"): st.session_state['page'] = 'Transit'
            if st.button("📊 Admin & Keuangan"): st.session_state['page'] = 'Admin'
            if st.button("🚪 Log Out"): 
                st.session_state['logged_in'] = False
                st.session_state['page'] = 'Login'
                st.rerun()
        else:
            if st.button("🔐 Login Staff"): st.session_state['page'] = 'Login'
            if st.button("🔍 Tracking Publik"): st.session_state['page'] = 'Tracking'

    # Routing
    pg = st.session_state['page']
    
    if pg == 'Login':
        login_page()
    elif pg == 'Tracking':
        tracking_page()
    elif st.session_state['logged_in']:
        if pg == 'Dashboard': dashboard_page()
        elif pg == 'Input Pengiriman': input_pengiriman_page()
        elif pg == 'Pembayaran': pembayaran_page()
        elif pg == 'Transit': transit_page()
        elif pg == 'Admin': admin_page()
    else:
        st.warning("Silakan Login terlebih dahulu.")

if __name__ == "__main__":
    main()