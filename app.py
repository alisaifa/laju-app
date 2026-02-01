import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import io
import base64
import streamlit.components.v1 as components

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Laju Logistics", page_icon="🚚", layout="wide")

# --- STYLE, TEMA & ANIMASI ---
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = False

def local_css():
    if st.session_state['dark_mode']:
        bg_color, text_color, card_bg = "#1a1a2e", "#ffffff", "#16213e"
    else:
        bg_color, text_color, card_bg = "#fdfbf7", "#0f3460", "#ffffff"
    
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .stButton>button {{ background-color: #e94560; color: white; border-radius: 8px; border: none; width: 100%; }}
    .stButton>button:hover {{ background-color: #c72c41; }}
    div[data-testid="metric-container"] {{ background-color: {card_bg}; border: 1px solid #ddd; padding: 10px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }}
    .garansi-box {{ border: 2px solid #e94560; padding: 10px; border-radius: 5px; background-color: {card_bg}; }}
    
    /* ANIMASI KERETA */
    @keyframes drive {{
        from {{ transform: translateX(-100%); }}
        to {{ transform: translateX(100%); }}
    }}
    .train-container {{
        width: 100%;
        overflow: hidden;
        white-space: nowrap;
        margin-bottom: 20px;
        padding: 10px 0;
    }}
    .train-icon {{
        display: inline-block;
        font-size: 2.5rem;
        animation: drive 8s linear infinite;
        color: #e94560;
        font-weight: bold;
    }}
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- KONEKSI DATABASE ---
@st.cache_resource
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def get_data(sheet_name):
    return get_gspread_client().open_by_url(st.secrets["sheets_url"]).worksheet(sheet_name)

# --- HELPER FUNCTIONS ---
def generate_resi():
    # Format: LJ-TanggalJamMenitDetik (Biar unik)
    return f"LJ-{datetime.now().strftime('%d%H%M%S')}"

def generate_barcode(resi):
    rv = io.BytesIO()
    barcode.get_barcode_class('code128')(resi, writer=ImageWriter()).write(rv)
    return base64.b64encode(rv.getvalue()).decode()

# --- STATE MANAGEMENT ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'page' not in st.session_state: st.session_state['page'] = 'Login'
if 'form_data' not in st.session_state: st.session_state['form_data'] = {}
if 'show_resi' not in st.session_state: st.session_state['show_resi'] = False
if 'html_resi_cache' not in st.session_state: st.session_state['html_resi_cache'] = ""

# --- HALAMAN 1: LOGIN (DENGAN ANIMASI) ---
def login_page():
    # ANIMASI DISINI
    st.markdown("<div class='train-container'><div class='train-icon'>🚚 💨 LAJU LOGISTICS 💨 🚚</div></div>", unsafe_allow_html=True)
    
    st.title("Login Staff Laju")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk"):
                try:
                    sheet = get_data("User")
                    records = sheet.get_all_records()
                    df = pd.DataFrame(records)
                    
                    # Logic Anti-Gagal (String Conversion)
                    df['Nama'] = df['Nama'].astype(str).str.strip()
                    df['Password'] = df['Password'].astype(str).str.strip()
                    input_u = str(user).strip()
                    input_p = str(pw).strip()
                    
                    cek = df[(df['Nama'] == input_u) & (df['Password'] == input_p)]
                    
                    if not cek.empty:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = cek.iloc[0].to_dict()
                        st.session_state['page'] = 'Dashboard'
                        st.rerun()
                    else:
                        st.error("Username/Password salah!")
                except Exception as e:
                    st.error(f"Error Database: {e}")

# --- HALAMAN 2: DASHBOARD ---
def dashboard_page():
    user = st.session_state['user_info']
    st.write(f"Halo, **{user['Nama']}**! Semangat bekerja di Cabang **{user['Cabang']}**.")
    
    try:
        # Ambil data Active saja untuk dashboard harian
        df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        if not df.empty:
            df['Total_Ongkir'] = pd.to_numeric(df['Total_Ongkir'], errors='coerce').fillna(0)
            omzet = df['Total_Ongkir'].sum()
            total = len(df)
            transit = len(df[df['Status'].astype(str).str.contains("Transit")])
        else:
            omzet, total, transit = 0, 0, 0
    except: omzet, total, transit = 0, 0, 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Paket Aktif", total)
    m2.metric("Sedang Transit", transit)
    m3.metric("Omzet Pending", f"Rp {omzet:,.0f}")
    
    st.markdown("### Menu Cepat")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("📦 Input Baru"): st.session_state['page'] = 'Input'
    if c2.button("🚚 Transit/Scan"): st.session_state['page'] = 'Transit'
    if c3.button("🔍 Tracking"): st.session_state['page'] = 'Tracking'
    if c4.button("📊 Admin Lengkap"): st.session_state['page'] = 'Admin'

# --- HALAMAN 3: INPUT PENGIRIMAN ---
def input_page():
    st.header("📦 Input Pengiriman Baru")
    st.session_state['show_resi'] = False 

    with st.expander("1. Data Pengirim & Penerima", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            pengirim = st.text_input("Nama Pengirim", key="s_nama")
            telp_pengirim = st.text_input("HP Pengirim", key="s_hp")
            alamat_pengirim = st.text_area("Alamat Pengirim", height=100, key="s_almt")
        with c2:
            penerima = st.text_input("Nama Penerima", key="r_nama")
            telp_penerima = st.text_input("HP Penerima", key="r_hp")
            prov = st.text_input("Provinsi", key="r_prov")
            kota = st.text_input("Kota/Kabupaten", key="r_kota")
            detail = st.text_area("Detail Alamat", height=100, key="r_det")
            kodepos = st.text_input("Kode Pos", key="r_pos")

    st.markdown("---")
    st.subheader("2. Detail Paket & Layanan")
    col_a, col_b = st.columns(2)
    with col_a:
        berat = st.number_input("Berat (Kg)", min_value=1.0, value=1.0, step=0.5)
        panjang = st.number_input("Panjang (cm)", 0)
        lebar = st.number_input("Lebar (cm)", 0)
        tinggi = st.number_input("Tinggi (cm)", 0)
        qty = st.number_input("Qty (Koli)", 1)
        volume = panjang * lebar * tinggi
        berat_vol = volume / 6000
        berat_fix = max(berat, berat_vol)
        if volume > 0: st.caption(f"Dimensi: {volume} cm³ | Berat Fix: {berat_fix:.2f} Kg")

    with col_b:
        layanan = st.selectbox("Pilih Layanan", ["Express", "Cargo", "Makanan"])
        harga_per_kg = 17000 if layanan == "Express" else 5000 if layanan == "Makanan" else 4000
        min_kg = 10 if layanan == "Cargo" else 1
        surcharge = 0
        if layanan == "Cargo" and volume > 64000: surcharge = ((volume-64000)/250)*1500
        
        berat_charge = max(min_kg, berat_fix)
        ongkir_dasar = (berat_charge * harga_per_kg) + surcharge
        st.info(f"Ongkir Dasar: **Rp {ongkir_dasar:,.0f}**")

        pake_garansi = st.checkbox("Tambah Asuransi/Garansi?")
        biaya_garansi = 0
        harga_barang = 0
        if pake_garansi:
            harga_barang = st.number_input("Harga Barang (Rp)", min_value=0, step=10000)
            if layanan == "Makanan": biaya_garansi = 5000
            elif layanan == "Express": biaya_garansi = harga_barang * 0.005
            else: biaya_garansi = harga_barang * 0.003
            st.success(f"Biaya Garansi: Rp {biaya_garansi:,.0f}")

    total_sementara = ongkir_dasar + biaya_garansi
    st.write(f"### Total Estimasi: Rp {total_sementara:,.0f}")
    
    if st.button("Lanjut ke Pembayaran ➡️"):
        if not pengirim or not penerima: st.warning("Isi Data Pengirim & Penerima dulu!")
        else:
            st.session_state['form_data'] = {
                "Resi": generate_resi(), "Pengirim": pengirim, "Telp_Pengirim": telp_pengirim, "Alamat_Pengirim": alamat_pengirim,
                "Penerima": penerima, "Telp_Penerima": telp_penerima, "Provinsi": prov, "Kota": kota, "Detail_Alamat": detail, "Kode_Pos": kodepos,
                "Berat": berat_fix, "Qty": qty, "Layanan": layanan, "Ongkir": ongkir_dasar, "Harga_Barang": harga_barang, "Biaya_Garansi": biaya_garansi
            }
            st.session_state['page'] = 'Pembayaran'
            st.rerun()

# --- HALAMAN 4: PEMBAYARAN ---
def pembayaran_page():
    st.header("💰 Pembayaran & Cetak Resi")
    
    if st.session_state['show_resi']:
        st.success("✅ Transaksi Berhasil!")
        components.html(st.session_state['html_resi_cache'], height=600, scrolling=True)
        if st.button("❌ TRANSAKSI BARU"):
            st.session_state['show_resi'] = False
            st.session_state['html_resi_cache'] = ""
            st.session_state['form_data'] = {}
            st.session_state['page'] = 'Input'
            st.rerun()
        return
    
    data = st.session_state['form_data']
    total_sys = data['Ongkir'] + data['Biaya_Garansi']
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"**Layanan:** {data['Layanan']}")
        st.write(f"Ongkir: Rp {data['Ongkir']:,.0f}")
        st.write(f"Garansi: Rp {data['Biaya_Garansi']:,.0f}")
        metode = st.radio("Metode", ["Prepaid (Lunas)", "COD (Bayar Tujuan)"])
        biaya_admin = total_sys * 0.05 if metode.startswith("COD") and total_sys < 100000 else total_sys * 0.025 if metode.startswith("COD") else 0
        grand_total = total_sys + biaya_admin
        st.markdown(f"### TOTAL: Rp {grand_total:,.0f}")
    
    with c2:
        sub_metode = st.selectbox("Jenis Pembayaran", ["Cash", "Transfer", "QRIS"]) if metode.startswith("Prepaid") else "Cash on Delivery"
        lunas_msg = "LUNAS" if metode.startswith("Prepaid") else "BELUM LUNAS"
        
        if st.button("🖨️ SIMPAN & CETAK"):
            try:
                row = [data['Resi'], str(datetime.now()), data['Pengirim'], data['Telp_Pengirim'], data['Alamat_Pengirim'],
                       data['Penerima'], data['Telp_Penerima'], data['Provinsi'], data['Kota'], "-", "-", data['Kode_Pos'], data['Detail_Alamat'],
                       "Diproses", "-", "-", "-", "-", data['Berat'], data['Qty'], data['Layanan'], data['Harga_Barang'], data['Biaya_Garansi'],
                       grand_total, metode, sub_metode, lunas_msg, "", "Pusat"]
                
                get_data("Data ( Active )").append_row(row)
                
                b64_code = generate_barcode(data['Resi'])
                html_resi = f"""
                <div style="width:300px;border:2px solid black;padding:10px;font-family:monospace;margin:auto;">
                    <h2 style="text-align:center;">LAJU LOGISTICS</h2>
                    <p style="text-align:center;">{data['Resi']}</p>
                    <div style="text-align:center;"><img src="data:image/png;base64,{b64_code}" style="width:80%;"></div>
                    <p><b>Dari:</b> {data['Pengirim']}<br><b>Ke:</b> {data['Penerima']}<br>{data['Kota']}</p>
                    <hr><p>Total: Rp {grand_total:,.0f}<br>{metode}</p>
                    <button onclick="window.print()" style="width:100%;background:black;color:white;padding:10px;">CETAK</button>
                </div>"""
                
                st.session_state['html_resi_cache'] = html_resi
                st.session_state['show_resi'] = True
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- HALAMAN 5: TRANSIT (ADA KAMERA & SEARCH) ---
def transit_page():
    st.header("🚚 Menu Transit")
    
    st.info("ℹ️ Masukkan Resi. Gunakan Scanner USB agar cepat, atau ketik manual.")
    resi = st.text_input("Scan/Ketik Resi:", help="Tekan Enter setelah scan")
    
    if resi:
        try:
            sheet = get_data("Data ( Active )")
            df = pd.DataFrame(sheet.get_all_records())
            df['No_Resi'] = df['No_Resi'].astype(str)
            item = df[df['No_Resi'] == resi]
            
            if not item.empty:
                idx = item.index[0] + 2
                d = item.iloc[0]
                st.success(f"📦 {d['Nama_Penerima']} - {d['Kota']}")
                st.table(item[['Status', 'Posisi_Terakhir']])
                
                c1, c2 = st.columns(2)
                cabang = st.session_state['user_info']['Cabang']
                
                with c1:
                    if st.button(f"📍 Sampai di {cabang}"):
                        sheet.update_cell(idx, 14, f"Transit di {cabang}")
                        sheet.update_cell(idx, 29, cabang)
                        st.success("Status Updated!")
                
                with c2:
                    st.write("**Konfirmasi Diterima (Upload Bukti)**")
                    # FITUR KAMERA MUNCUL DISINI
                    foto = st.camera_input("Ambil Foto Bukti")
                    if foto:
                        if st.button("✅ Selesai & Arsipkan"):
                            # Upload Mock
                            sheet.update_cell(idx, 14, "Diterima Customer")
                            sheet.update_cell(idx, 28, "https://link-foto-bukti-disini.com")
                            
                            row = sheet.row_values(idx)
                            row.append(str(datetime.now()))
                            get_data("Arsip Data").append_row(row)
                            sheet.delete_rows(idx)
                            st.balloons()
                            st.success("Paket Selesai!")
            else: st.warning("Resi tidak ditemukan.")
        except Exception as e: st.error(f"Error: {e}")

# --- HALAMAN 6: TRACKING (CARI DI ACTIVE & ARSIP) ---
def tracking_page():
    st.header("🔍 Tracking Paket")
    resi = st.text_input("Masukkan No. Resi")
    if st.button("Lacak"):
        try:
            # Cari di Active
            df1 = pd.DataFrame(get_data("Data ( Active )").get_all_records())
            res1 = df1[df1['No_Resi'].astype(str) == resi]
            
            if not res1.empty:
                d = res1.iloc[0]
                st.info(f"Status: **{d['Status']}**")
                st.write(f"Posisi: {d['Posisi_Terakhir']}")
                st.progress(50)
            else:
                # Cari di Arsip
                df2 = pd.DataFrame(get_data("Arsip Data").get_all_records())
                res2 = df2[df2['No_Resi'].astype(str) == resi]
                if not res2.empty:
                    d = res2.iloc[0]
                    st.success(f"✅ PAKET DITERIMA (Arsip)")
                    st.write(f"Diterima Tgl: {d.get('Tanggal_Diterima', '-')}")
                    st.progress(100)
                else:
                    st.error("Resi Tidak Ditemukan.")
        except: st.error("Gagal mengambil data.")

# --- HALAMAN 7: ADMIN LENGKAP (TABS KEMBALI) ---
def admin_page():
    st.title("📊 Admin Dashboard")
    
    # MEMBUAT TABS SEPERTI REQUEST AWAL
    tab1, tab2, tab3 = st.tabs(["📦 Data Active", "🗄️ Arsip Data", "💰 Laporan Keuangan"])
    
    with tab1:
        st.subheader("Monitoring Paket Berjalan")
        df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        st.dataframe(df)
        
    with tab2:
        st.subheader("Arsip (Sudah Diterima)")
        try:
            df_arsip = pd.DataFrame(get_data("Arsip Data").get_all_records())
            st.dataframe(df_arsip)
            if not df_arsip.empty:
                csv = df_arsip.to_csv(index=False).encode('utf-8')
                st.download_button("Download CSV", csv, "arsip_laju.csv")
        except: st.write("Belum ada data arsip.")
        
    with tab3:
        st.subheader("Ringkasan Keuangan")
        try:
            # Gabung Data
            df_a = pd.DataFrame(get_data("Data ( Active )").get_all_records())
            df_b = pd.DataFrame(get_data("Arsip Data").get_all_records())
            df_all = pd.concat([df_a, df_b], ignore_index=True)
            
            if not df_all.empty:
                # Pastikan numerik
                df_all['Total_Ongkir'] = pd.to_numeric(df_all['Total_Ongkir'], errors='coerce').fillna(0)
                
                omzet = df_all['Total_Ongkir'].sum()
                cash = df_all[df_all['Metode_Bayar'].str.contains("Cash", case=False, na=False)]['Total_Ongkir'].sum()
                transfer = df_all[df_all['Metode_Bayar'].str.contains("Transfer", case=False, na=False)]['Total_Ongkir'].sum()
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Omzet", f"Rp {omzet:,.0f}")
                k2.metric("Total Cash", f"Rp {cash:,.0f}")
                k3.metric("Total Transfer", f"Rp {transfer:,.0f}")
                
                st.write("Rincian:")
                st.dataframe(df_all[['No_Resi', 'Total_Ongkir', 'Tipe_Pembayaran', 'Metode_Bayar', 'Status']])
        except Exception as e: st.error(f"Gagal hitung keuangan: {e}")

# --- MAIN NAVIGATION ---
if st.session_state['logged_in']:
    pg = st.session_state['page']
    with st.sidebar:
        st.title("Laju App")
        if st.button("🏠 Dashboard"): st.session_state['page'] = 'Dashboard'
        if st.button("📦 Input Paket"): st.session_state['page'] = 'Input'
        if st.button("🚚 Transit"): st.session_state['page'] = 'Transit'
        if st.button("🔍 Tracking"): st.session_state['page'] = 'Tracking'
        if st.button("📊 Admin"): st.session_state['page'] = 'Admin'
        if st.button("🚪 Logout"): 
            st.session_state['logged_in'] = False
            st.rerun()
            
    if pg == 'Dashboard': dashboard_page()
    elif pg == 'Input': input_page()
    elif pg == 'Pembayaran': pembayaran_page()
    elif pg == 'Transit': transit_page()
    elif pg == 'Tracking': tracking_page()
    elif pg == 'Admin': admin_page()
else:
    login_page()
