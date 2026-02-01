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

# --- STYLE & TEMA ---
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
    return f"LJ-{datetime.now().strftime('%d%H%M%S')}"

def generate_barcode(resi):
    rv = io.BytesIO()
    barcode.get_barcode_class('code128')(resi, writer=ImageWriter()).write(rv)
    return base64.b64encode(rv.getvalue()).decode()

# --- STATE MANAGEMENT ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'page' not in st.session_state: st.session_state['page'] = 'Login'
if 'form_data' not in st.session_state: st.session_state['form_data'] = {}
# STATE BARU UNTUK RESI AGAR TIDAK HILANG
if 'show_resi' not in st.session_state: st.session_state['show_resi'] = False
if 'html_resi_cache' not in st.session_state: st.session_state['html_resi_cache'] = ""

# --- HALAMAN 1: LOGIN ---
def login_page():
    st.title("🚚 LAJU LOGISTICS")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            st.subheader("Login Staff")
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Masuk"):
                try:
                    sheet = get_data("User")
                    records = sheet.get_all_records()
                    df = pd.DataFrame(records)
                    
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
    st.write(f"Selamat Datang, **{user['Nama']}** ({user['Cabang']})")
    
    try:
        df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
        omzet = df['Total_Ongkir'].sum() if not df.empty else 0
        total = len(df)
    except: omzet, total = 0, 0
    
    m1, m2 = st.columns(2)
    m1.metric("Paket Aktif", total)
    m2.metric("Omzet Harian", f"Rp {omzet:,.0f}")
    
    st.markdown("### Menu Utama")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("📦 Input Baru"): st.session_state['page'] = 'Input'
    if c2.button("🚚 Transit"): st.session_state['page'] = 'Transit'
    if c3.button("🔍 Tracking"): st.session_state['page'] = 'Tracking'
    if c4.button("📊 Admin"): st.session_state['page'] = 'Admin'

# --- HALAMAN 3: INPUT PENGIRIMAN ---
def input_page():
    st.header("📦 Input Pengiriman Baru")
    
    # Pastikan state resi bersih saat masuk sini
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
        if volume > 0:
            st.caption(f"Dimensi: {volume} cm³ | Berat Vol: {berat_vol:.2f} Kg | **Dipakai: {berat_fix:.2f} Kg**")

    with col_b:
        layanan = st.selectbox("Pilih Layanan", ["Express", "Cargo", "Makanan"])
        
        harga_per_kg = 0
        min_kg = 1
        surcharge = 0
        
        if layanan == "Express": harga_per_kg = 17000
        elif layanan == "Makanan": harga_per_kg = 5000
        elif layanan == "Cargo": 
            harga_per_kg = 4000
            min_kg = 10
            if volume > 64000:
                excess = volume - 64000
                surcharge = (excess/250) * 1500
        
        berat_charge = max(min_kg, berat_fix)
        ongkir_dasar = (berat_charge * harga_per_kg) + surcharge
        
        st.info(f"Ongkir Dasar: **Rp {ongkir_dasar:,.0f}**")

        pake_garansi = st.checkbox("Tambah Asuransi/Garansi?")
        biaya_garansi = 0
        harga_barang = 0
        
        if pake_garansi:
            harga_barang = st.number_input("Masukkan Harga Barang (Rp)", min_value=0, step=10000)
            if layanan == "Makanan": biaya_garansi = 5000
            elif layanan == "Express": biaya_garansi = harga_barang * 0.005
            else: biaya_garansi = harga_barang * 0.003
            
            st.markdown(f"""
            <div class="garansi-box">
                Biaya Garansi: <b>Rp {biaya_garansi:,.0f}</b>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    total_sementara = ongkir_dasar + biaya_garansi
    st.write(f"### Total Estimasi: Rp {total_sementara:,.0f}")
    
    if st.button("Lanjut ke Pembayaran ➡️"):
        if not pengirim or not penerima:
            st.warning("Nama Pengirim dan Penerima wajib diisi!")
        else:
            st.session_state['form_data'] = {
                "Resi": generate_resi(),
                "Pengirim": pengirim, "Telp_Pengirim": telp_pengirim, "Alamat_Pengirim": alamat_pengirim,
                "Penerima": penerima, "Telp_Penerima": telp_penerima, "Provinsi": prov, "Kota": kota,
                "Detail_Alamat": detail, "Kode_Pos": kodepos,
                "Berat": berat_fix, "Qty": qty, "Dimensi": f"{panjang}x{lebar}x{tinggi}",
                "Layanan": layanan, "Ongkir": ongkir_dasar,
                "Harga_Barang": harga_barang, "Biaya_Garansi": biaya_garansi
            }
            st.session_state['page'] = 'Pembayaran'
            st.rerun()

# --- HALAMAN 4: PEMBAYARAN & CETAK (FIX LOGIC) ---
def pembayaran_page():
    st.header("💰 Pembayaran & Cetak Resi")
    
    # 1. CEK APAKAH RESI SUDAH DICETAK?
    if st.session_state['show_resi']:
        st.success("✅ Transaksi Berhasil Disimpan!")
        st.info("Silakan cetak resi di bawah ini. Jika sudah, klik tombol 'Selesai' di paling bawah.")
        
        # Tampilkan HTML dari Memory
        components.html(st.session_state['html_resi_cache'], height=600, scrolling=True)
        
        if st.button("❌ SELESAI / TRANSAKSI BARU"):
            # Reset semua data
            st.session_state['show_resi'] = False
            st.session_state['html_resi_cache'] = ""
            st.session_state['form_data'] = {}
            st.session_state['page'] = 'Input' # Balik ke menu input
            st.rerun()
        return # BERHENTI DISINI AGAR BAWAHNYA TIDAK MUNCUL
    
    # 2. JIKA BELUM DICETAK, TAMPILKAN FORM BAYAR
    data = st.session_state['form_data']
    
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Rincian Biaya")
        st.write(f"Layanan: {data['Layanan']}")
        st.write(f"Ongkir: Rp {data['Ongkir']:,.0f}")
        st.write(f"Garansi: Rp {data['Biaya_Garansi']:,.0f}")
        
        total_sys = data['Ongkir'] + data['Biaya_Garansi']
        
        metode_utama = st.radio("Sistem Pembayaran", ["Prepaid (Bayar Sekarang)", "COD (Bayar Tujuan)"])
        
        biaya_admin = 0
        jenis_bayar = "-"
        status_bayar = "Belum Lunas"
        
        if metode_utama == "COD (Bayar Tujuan)":
            if total_sys < 100000: biaya_admin = total_sys * 0.05
            else: biaya_admin = total_sys * 0.025
            jenis_bayar = "Cash on Delivery"
        else:
            sub_metode = st.selectbox("Metode Bayar", ["Cash (Tunai di Kantor)", "Transfer Bank BNI", "QRIS"])
            jenis_bayar = sub_metode
            status_bayar = "LUNAS"
            
        grand_total = total_sys + biaya_admin
        
        st.markdown(f"""
        <div style="background-color: #e94560; color: white; padding: 15px; border-radius: 10px;">
            <h3>TOTAL TAGIHAN: Rp {grand_total:,.0f}</h3>
            <small>Termasuk Admin COD: Rp {biaya_admin:,.0f}</small>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.subheader("Konfirmasi")
        enable_print = True
        
        if metode_utama.startswith("Prepaid"):
            # Pake Checkbox aja biar gak refresh halaman
            if st.checkbox("✅ Pembayaran Diterima dari Customer"):
                st.success("Lunas!")
            else:
                enable_print = False
                st.warning("Pastikan customer sudah bayar sebelum cetak resi.")
        
        if enable_print:
            if st.button("🖨️ SIMPAN & CETAK RESI"):
                try:
                    # 1. Simpan ke GSheets
                    row = [
                        data['Resi'], str(datetime.now()), 
                        data['Pengirim'], data['Telp_Pengirim'], data['Alamat_Pengirim'],
                        data['Penerima'], data['Telp_Penerima'], 
                        data['Provinsi'], data['Kota'], "-", "-", data['Kode_Pos'], data['Detail_Alamat'],
                        "Diproses", "-", "-", "-", "-", data['Berat'], data['Qty'],
                        data['Layanan'], data['Harga_Barang'], data['Biaya_Garansi'],
                        grand_total, metode_utama, jenis_bayar, status_bayar, "", "Kantor Pusat"
                    ]
                    
                    sheet = get_data("Data ( Active )")
                    sheet.append_row(row)
                    
                    # 2. GENERATE HTML RESI & SIMPAN KE MEMORI (SESSION STATE)
                    b64_code = generate_barcode(data['Resi'])
                    html_resi = f"""
                    <div style="width: 300px; border: 2px solid black; padding: 10px; font-family: monospace; background: white; color: black; margin: auto;">
                        <h2 style="text-align: center; margin: 0;">LAJU LOGISTICS</h2>
                        <p style="text-align: center;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                        <hr style="border-top: 2px dashed black;">
                        <div style="text-align: center;">
                            <img src="data:image/png;base64,{b64_code}" style="width: 80%;">
                            <h3>{data['Resi']}</h3>
                        </div>
                        <hr style="border-top: 2px dashed black;">
                        <p><b>Pengirim:</b> {data['Pengirim']}<br>{data['Telp_Pengirim']}</p>
                        <p><b>Penerima:</b> {data['Penerima']}<br>{data['Detail_Alamat']}<br>{data['Kota']}, {data['Provinsi']}</p>
                        <hr style="border-top: 2px dashed black;">
                        <p>Layanan: {data['Layanan']}<br>
                        Berat: {data['Berat']} Kg ({data['Qty']} Koli)<br>
                        Isi: Rp {data['Harga_Barang']:,.0f}</p>
                        <hr style="border-top: 2px dashed black;">
                        <h2 style="text-align: right;">TOTAL: Rp {grand_total:,.0f}</h2>
                        <p style="text-align: center;">{metode_utama} ({status_bayar})</p>
                        <br>
                        <button onclick="window.print()" style="width: 100%; padding: 10px; background: black; color: white; font-weight: bold; cursor: pointer;">CETAK SEKARANG</button>
                    </div>
                    """
                    
                    # SIMPAN KE STATE
                    st.session_state['html_resi_cache'] = html_resi
                    st.session_state['show_resi'] = True # Trigger agar tampilan berubah
                    st.rerun() # Refresh halaman untuk memunculkan resi
                    
                except Exception as e:
                    st.error(f"Gagal Simpan: {e}")

# --- HALAMAN 5: TRANSIT ---
def transit_page():
    st.header("🚚 Update Status Transit")
    resi = st.text_input("Scan/Ketik No. Resi disini", help="Tekan Enter setelah scan")
    
    if resi:
        try:
            sheet = get_data("Data ( Active )")
            df = pd.DataFrame(sheet.get_all_records())
            df['No_Resi'] = df['No_Resi'].astype(str)
            item = df[df['No_Resi'] == resi]
            
            if not item.empty:
                idx = item.index[0] + 2 
                data = item.iloc[0]
                st.success(f"Paket Ditemukan: {data['Nama_Penerima']} - {data['Kota']}")
                st.json(data.to_dict())
                
                c1, c2 = st.columns(2)
                user_cabang = st.session_state['user_info']['Cabang']
                
                with c1:
                    if st.button(f"📍 Sampai di {user_cabang}"):
                        sheet.update_cell(idx, 14, f"Transit di {user_cabang}") 
                        sheet.update_cell(idx, 29, user_cabang)
                        st.success("Status Updated!")
                
                with c2:
                    st.write("📸 **Bukti Diterima Customer**")
                    foto = st.camera_input("Ambil Foto Penyerahan")
                    if foto:
                        if st.button("✅ Selesai & Arsipkan"):
                            # Upload Mock
                            link_foto = "https://via.placeholder.com/bukti" 
                            sheet.update_cell(idx, 14, "Diterima Customer")
                            sheet.update_cell(idx, 28, link_foto)
                            
                            row_vals = sheet.row_values(idx)
                            row_vals.append(str(datetime.now()))
                            get_data("Arsip Data").append_row(row_vals)
                            sheet.delete_rows(idx)
                            st.balloons()
                            st.success("Paket Berhasil Diselesaikan!")
            else:
                st.warning("Resi tidak ditemukan.")
        except Exception as e:
            st.error(f"Error: {e}")

# --- HALAMAN 6: TRACKING & ADMIN ---
def tracking_page():
    st.header("🔍 Lacak Paket")
    resi = st.text_input("Masukkan No. Resi")
    if st.button("Cari"):
        st.info("Fitur pencarian aktif...")

def admin_page():
    st.header("📊 Admin Dashboard")
    df = pd.DataFrame(get_data("Data ( Active )").get_all_records())
    st.dataframe(df)

# --- MAIN NAVIGATION ---
if st.session_state['logged_in']:
    pg = st.session_state['page']
    with st.sidebar:
        st.title("Menu")
        if st.button("Dashboard"): st.session_state['page'] = 'Dashboard'
        if st.button("Input Paket"): st.session_state['page'] = 'Input'
        if st.button("Transit"): st.session_state['page'] = 'Transit'
        if st.button("Tracking"): st.session_state['page'] = 'Tracking'
        if st.button("Logout"): 
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
