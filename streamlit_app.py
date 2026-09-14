import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Investeringsdashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Investeringsdashboard")
st.caption(
    "Oversikt over selskaper, nøkkeltall, aksjonærer, nyheter og kontrakter"
)

st.sidebar.title("Meny")

side = st.sidebar.radio(
    "Velg side",
    [
        "Dashboard",
        "Selskaper",
        "Nøkkeltall",
        "Aksjonærer",
        "Nyheter",
        "Kontrakter"
    ]
)

companies = [
    "NORBIT",
    "Cambi",
    "Kitron",
    "NOTE",
    "Protector"
]

if side == "Dashboard":

    st.header("Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Selskaper", "5")
    col2.metric("Nye nyheter", "0")
    col3.metric("Aksjonærendringer", "0")
    col4.metric("Mulige kontrakter", "0")

    st.divider()

    st.subheader("Selskapsoversikt")

    data = {
        "Selskap": companies,
        "Kurs": ["-", "-", "-", "-", "-"],
        "EPS 2026E": ["-", "-", "-", "-", "-"],
        "P/E": ["-", "-", "-", "-", "-"],
        "FCF Yield": ["-", "-", "-", "-", "-"],
        "Status": ["Følg", "Følg", "Følg", "Følg", "Følg"]
    }

    df = pd.DataFrame(data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Dagens viktigste endringer")

    st.info(
        "Ingen automatiske oppdateringer er koblet til ennå. "
        "Dette bygger vi inn senere."
    )

elif side == "Selskaper":

    st.header("Selskaper")

    selskap = st.selectbox(
        "Velg selskap",
        companies
    )

    st.subheader(selskap)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Kurs", "-")
    col2.metric("EPS", "-")
    col3.metric("P/E", "-")
    col4.metric("FCF Yield", "-")

    st.divider()

    st.subheader("Investeringscase")
    st.write("Her legger vi inn vår analyse av selskapet.")

    st.subheader("Siste utvikling")
    st.write("Her kommer nyheter og viktige endringer.")

elif side == "Nøkkeltall":

    st.header("Nøkkeltall")

    st.write(
        "Her skal vi samle kvartals- og årsdata "
        "for alle selskapene."
    )

elif side == "Aksjonærer":

    st.header("Aksjonærendringer")

    st.write(
        "Her skal programmet sammenligne dagens "
        "aksjonærliste med tidligere dager."
    )

elif side == "Nyheter":

    st.header("Nyheter")

    st.write(
        "Her skal vi hente børsmeldinger, "
        "IR-nyheter og relevante eksterne nyheter."
    )

elif side == "Kontrakter":

    st.header("Mulige kontrakter")

    st.write(
        "Her skal vi følge mulige anbud, "
        "prosjekter og kontraktsmuligheter."
    )