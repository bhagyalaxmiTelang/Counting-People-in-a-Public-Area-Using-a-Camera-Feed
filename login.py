import streamlit as st

# Page config
st.set_page_config(
    page_title="Crowd Counting System",
    layout="centered"
)

# Theme selector (keep at top)
theme = st.selectbox("Choose Theme", ["Dark", "Light"])

# ================= CSS =================
if theme == "Dark":
    st.markdown("""
    <style>
    .stApp {
        background-color: #0f1117;
        color: #ffffff;
    }

    h1, h2, h3, p, label {
        color: #ffffff !important;
    }

    .login-card {
        background-color: #1c1e26;
        padding: 35px;
        border-radius: 14px;
        max-width: 420px;
        margin: auto;
        box-shadow: 0px 0px 20px rgba(0,0,0,0.6);
    }

    input {
        background-color: #2a2d3a !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #2a2d3a !important;
        color: white !important;
        border-radius: 8px;
        border: none !important;
    }

    button {
        background-color: #3b82f6 !important;
        color: white !important;
        border-radius: 10px !important;
        font-size: 18px !important;
        height: 45px;
    }
    </style>
    """, unsafe_allow_html=True)

else:
    st.markdown("""
    <style>
    .stApp {
        background-color: #f5f7fb;
        color: #000000;
    }

    h1, h2, h3, p, label {
        color: #000000 !important;
    }

    .login-card {
        background-color: #ffffff;
        padding: 35px;
        border-radius: 14px;
        max-width: 420px;
        margin: auto;
        box-shadow: 0px 0px 18px rgba(0,0,0,0.15);
    }

    input {
        background-color: #ffffff !important;
        color: black !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: black !important;
        border-radius: 8px;
        border: 1px solid #ccc !important;
    }

    button {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 10px !important;
        font-size: 18px !important;
        height: 45px;
    }
    </style>
    """, unsafe_allow_html=True)

# ================= UI =================
st.markdown("<h1 style='text-align:center;'>Crowd Counting System</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Login Portal</p>", unsafe_allow_html=True)
st.write("")

# Login Card
st.markdown("<div class='login-card'>", unsafe_allow_html=True)

st.subheader("Login")
username = st.text_input("Username")
password = st.text_input("Password", type="password")

if st.button("Login"):
    if username == "" or password == "":
        st.warning("Please enter username and password")
    else:
        st.success(f"Welcome {username}!")
        st.write("Crowd Counting System Loaded")

st.markdown("</div>", unsafe_allow_html=True)
