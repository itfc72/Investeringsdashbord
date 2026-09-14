import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Investeringsdashboard",
    page_icon="📊",
    layout="wide"
)

# --------------------------------------------------
# SELSKAPSDATA
# --------------------------------------------------

companies = {
    "NORBIT": {
        "ticker": "NORBT",
        "marked": "Oslo Børs",
        "sektor": "Teknologi / Ocean",
        "case": (
            "Teknologiselskap med eksponering mot blant annet Ocean, "
            "Connectivity og produktutvikling. Vi følger spesielt utviklingen "
            "innen sonar, subsea, autonome fartøy og forsvarsrelaterte muligheter."
        )
    },

    "Cambi": {
        "ticker": "CAMBI",
        "marked": "Euronext Growth Oslo",
        "sektor": "Miljøteknologi",
        "case": (
            "Ledende leverandør av termisk hydrolyse og løsninger for behandling "
            "av avløpsslam. Ordrebok, nye THP-anlegg og internasjonale anbud er "
            "viktige drivere."
        )
    },

    "Kitron": {
        "ticker": "KIT",
        "marked": "Oslo Børs",
        "sektor": "EMS / Elektronikk",
        "case": (
            "Elektronikkprodusent med betydelig eksponering mot forsvar, industri, "
            "medisinsk teknologi og elektrifisering."
        )
    },

    "NOTE": {
        "ticker": "NOTE",
        "marked": "Nasdaq Stockholm",
        "sektor": "EMS / Elektronikk",
        "case": (
            "Nordisk EMS-selskap med produksjon i Europa og eksponering mot "
            "industri, defence, medtech og annen avansert elektronikk."
        )
    },

    "Protector": {
        "ticker": "PROT",
        "marked": "Oslo Børs",
        "sektor": "Forsikring",
        "case": (
            "Skadeforsikringsselskap med historisk god lønnsomhet, sterk vekst "
            "og fokus på combined ratio og avkastning på investeringsporteføljen."
        )
    }
}

# --------------------------------------------------
# TOPP
# --------------------------------------------------

st.title("📊 Investeringsdashboard")

st.caption(
    "Selskaper • nøkkeltall • aksjonærer • nyheter • kontrakter • verdsettelse"
)

# --------------------------------------------------
# MENY
# --------------------------------------------------

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

# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if side == "Dashboard":

    st.header("Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Selskaper", len(companies))
    c2.metric("Nye nyheter", "0")
    c3.metric("Aksjonærendringer", "0")
    c4.metric("Mulige kontrakter", "0")

    st.divider()

    st.subheader("Selskapsoversikt")

    oversikt = pd.DataFrame({
        "Selskap": list(companies.keys()),
        "Kurs": ["-", "-", "-", "-", "-"],
        "EPS LTM": ["-", "-", "-", "-", "-"],
        "EPS 2026E": ["-", "-", "-", "-", "-"],
        "P/E": ["-", "-", "-", "-", "-"],
        "FCF Yield": ["-", "-", "-", "-", "-"],
        "Status": ["Følg"] * 5
    })

    st.dataframe(
        oversikt,
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Dagens viktigste endringer")

    st.info(
        "Senere skal denne delen automatisk vise nye børsmeldinger, "
        "aksjonærendringer, kontrakter og andre viktige hendelser."
    )


# --------------------------------------------------
# SELSKAPER
# --------------------------------------------------

elif side == "Selskaper":

    selskap = st.selectbox(
        "Velg selskap",
        list(companies.keys())
    )

    info = companies[selskap]

    st.header(selskap)

    st.caption(
        f"{info['ticker']}  |  {info['marked']}  |  {info['sektor']}"
    )

    # Topp-nøkkeltall
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    k1.metric("Kurs", "-")
    k2.metric("Markedsverdi", "-")
    k3.metric("EPS LTM", "-")
    k4.metric("P/E", "-")
    k5.metric("FCF Yield", "-")
    k6.metric("ROE", "-")

    st.divider()

    # Faner
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Oversikt",
            "Nøkkeltall",
            "Aksjonærer",
            "Nyheter",
            "Kontrakter",
            "Verdsettelse"
        ]
    )

    # --------------------------------------------------
    # OVERSIKT
    # --------------------------------------------------

    with tab1:

        st.subheader("Investeringscase")
        st.write(info["case"])

        st.subheader("Siste kvartal")

        q1, q2, q3, q4, q5 = st.columns(5)

        q1.metric("Omsetning", "-")
        q2.metric("Vekst", "-")
        q3.metric("EBIT", "-")
        q4.metric("EBIT-margin", "-")
        q5.metric("EPS", "-")

        st.subheader("Vår vurdering")

        bear, base, bull = st.columns(3)

        with bear:
            st.markdown("#### 🔴 Bear")
            st.write("Ikke beregnet")

        with base:
            st.markdown("#### 🟡 Base")
            st.write("Ikke beregnet")

        with bull:
            st.markdown("#### 🟢 Bull")
            st.write("Ikke beregnet")

        st.subheader("Siste utvikling")

        st.info(
            "Her skal systemet vise de viktigste endringene siden forrige analyse."
        )


    # --------------------------------------------------
    # NØKKELTALL
    # --------------------------------------------------

    with tab2:

        st.subheader("Historiske nøkkeltall")

        tall = pd.DataFrame({
            "Periode": [
                "2024",
                "2025",
                "Q1 2026",
                "Q2 2026",
                "2026E",
                "2027E",
                "2028E"
            ],
            "Omsetning": ["-"] * 7,
            "Vekst": ["-"] * 7,
            "EBIT": ["-"] * 7,
            "EBIT-margin": ["-"] * 7,
            "EPS": ["-"] * 7,
            "FCF": ["-"] * 7
        })

        st.dataframe(
            tall,
            use_container_width=True,
            hide_index=True
        )


    # --------------------------------------------------
    # AKSJONÆRER
    # --------------------------------------------------

    with tab3:

        st.subheader("Aksjonærendringer")

        a1, a2, a3 = st.columns(3)

        a1.metric("Nye aksjonærer", "0")
        a2.metric("Økt beholdning", "0")
        a3.metric("Redusert beholdning", "0")

        st.write(
            "Senere sammenligner vi dagens aksjonærliste med gårsdagen, "
            "forrige uke og forrige måned."
        )


    # --------------------------------------------------
    # NYHETER
    # --------------------------------------------------

    with tab4:

        st.subheader("Nyheter")

        st.write(
            "Her kommer børsmeldinger, IR-nyheter og relevante "
            "eksterne nyheter."
        )

        st.info("Ingen nyheter registrert ennå.")


    # --------------------------------------------------
    # KONTRAKTER
    # --------------------------------------------------

    with tab5:

        st.subheader("Kontraktsmonitor")

        kontrakter = pd.DataFrame({
            "Prosjekt / kunde": [],
            "Land": [],
            "Est. verdi": [],
            "Status": [],
            "Sannsynlighet": [],
            "Sist oppdatert": []
        })

        st.dataframe(
            kontrakter,
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            "Her følger vi både annonserte kontrakter og mulige kommende kontrakter."
        )


    # --------------------------------------------------
    # VERDSETTELSE
    # --------------------------------------------------

    with tab6:

        st.subheader("Verdsettelse")

        v1, v2, v3 = st.columns(3)

        v1.metric("Bear case", "-")
        v2.metric("Base case", "-")
        v3.metric("Bull case", "-")

        st.write("Verdsettelsesmetoder")

        st.checkbox("P/E-basert verdsettelse")
        st.checkbox("DCF")
        st.checkbox("FCF yield")
        st.checkbox("Graham")
        st.checkbox("EV/EBIT")


# --------------------------------------------------
# NØKKELTALL
# --------------------------------------------------

elif side == "Nøkkeltall":

    st.header("Nøkkeltall")

    st.write(
        "Her skal vi senere sammenligne alle selskapene på samme nøkkeltall."
    )


# --------------------------------------------------
# AKSJONÆRER
# --------------------------------------------------

elif side == "Aksjonærer":

    st.header("Aksjonærendringer")

    selskap = st.selectbox(
        "Velg selskap",
        list(companies.keys())
    )

    st.write(
        f"Daglige aksjonærendringer for {selskap} kommer her."
    )


# --------------------------------------------------
# NYHETER
# --------------------------------------------------

elif side == "Nyheter":

    st.header("Nyheter")

    st.write(
        "Samlet nyhetsstrøm for alle selskapene vi følger."
    )


# --------------------------------------------------
# KONTRAKTER
# --------------------------------------------------

elif side == "Kontrakter":

    st.header("Kontraktsmonitor")

    st.write(
        "Oversikt over annonserte kontrakter, anbud og potensielle kontrakter."
    )
    