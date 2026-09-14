import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Investeringsdashboard",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# DATA
# =========================================================

companies = {
    "NORBIT": {
        "ticker": "NORBT",
        "marked": "Oslo Børs",
        "sektor": "Teknologi / Ocean / Defence",
        "case": (
            "NORBIT er et teknologiselskap med tre segmenter: Oceans, Connectivity "
            "og Product Innovation & Realization (PIR). Investeringscaset bygger på "
            "høy organisk vekst, sterke marginer, økende forsvarseksponering og en "
            "stadig bredere posisjon innen sonar, undervannsnavigasjon, autonome "
            "farkoster og elektronikkproduksjon."
        ),
        "price": 162.00,
        "price_date": "11.09.2026",
        "market_cap": 10.36,
        "eps_ltm": 7.04,
        "pe_ltm": 23.0,
        "fcf_ltm": 478.0,
        "fcf_yield": 4.6,
        "roe_ltm": 38.2,
        "roce": 36.0,
        "nibd": 554.7,
        "nibd_ebitda": 0.7,
        "shares_outstanding": 63_981_154,
        "q2": {
            "revenue": 831.6,
            "growth": 22.0,
            "ebit": 205.2,
            "ebit_margin": 24.7,
            "eps": 2.45,
            "ocf": 275.2,
            "fcf": 219.4,
        },
        "h1": {
            "revenue": 1563.8,
            "growth": 30.0,
            "ebit": 361.1,
            "ebit_margin": 23.1,
            "eps": 4.18,
            "ocf": 487.8,
            "fcf": 375.6,
        },
        "financials": [
            {
                "Periode": "2024",
                "Omsetning": 1751.4,
                "Vekst": "15%",
                "EBIT": 341.7,
                "EBIT-margin": "20%",
                "EPS": 3.93,
            },
            {
                "Periode": "2025",
                "Omsetning": 2502.5,
                "Vekst": "43%",
                "EBIT": 555.4,
                "EBIT-margin": "22%",
                "EPS": 6.32,
            },
            {
                "Periode": "Q1 2026",
                "Omsetning": 732.1,
                "Vekst": "40%",
                "EBIT": 155.9,
                "EBIT-margin": "21%",
                "EPS": 1.73,
            },
            {
                "Periode": "Q2 2026",
                "Omsetning": 831.6,
                "Vekst": "22%",
                "EBIT": 205.2,
                "EBIT-margin": "25%",
                "EPS": 2.45,
            },
            {
                "Periode": "H1 2026",
                "Omsetning": 1563.8,
                "Vekst": "30%",
                "EBIT": 361.1,
                "EBIT-margin": "23%",
                "EPS": 4.18,
            },
        ],
        "segments_q2": [
            {
                "Segment": "Oceans",
                "Omsetning Q2": 236.2,
                "Vekst": "-1%",
                "EBIT": 79.0,
                "EBIT-margin": "33%",
            },
            {
                "Segment": "Connectivity",
                "Omsetning Q2": 250.0,
                "Vekst": "47%",
                "EBIT": 66.3,
                "EBIT-margin": "27%",
            },
            {
                "Segment": "PIR",
                "Omsetning Q2": 367.1,
                "Vekst": "25%",
                "EBIT": 81.7,
                "EBIT-margin": "22%",
            },
        ],
        "guidance": [
            "2026: Omsetning NOK 2,9–3,1 mrd.",
            "2026: EBIT-margin 20–23 %.",
            "2030: Organisk omsetning rundt NOK 6,0 mrd.",
            "2030: EBIT-margin 20–25 %.",
            "2030: ROCE over 30 %.",
        ],
        "news": [
            {
                "Dato": "25.08.2026",
                "Hendelse": "NORBIT Connect lansert",
                "Vurdering": "Positiv",
                "Kommentar": "Ny web-basert løsning for ROV-sonaroperasjoner."
            },
            {
                "Dato": "13.08.2026",
                "Hendelse": "Falcon Eye / NORBIT Security kontrakt i Abu Dhabi",
                "Vurdering": "Positiv",
                "Kommentar": "NORBIT-sonarer valgt til undervannssikring av et profilert anlegg."
            },
            {
                "Dato": "13.08.2026",
                "Hendelse": "Q2 2026",
                "Vurdering": "Sterk",
                "Kommentar": "Rekordomsetning og 25 % EBIT-margin."
            },
            {
                "Dato": "01.07.2026",
                "Hendelse": "Water Linked oppkjøp gjennomført",
                "Vurdering": "Strategisk positiv",
                "Kommentar": "Utvider tilbudet innen undervannsnavigasjon, 3D-sonar og autonomi."
            },
        ],
        "contracts": [
            {
                "Dato": "21.07.2026",
                "Segment": "Connectivity",
                "Kunde/prosjekt": "Toll4Europe – GNSS On-Board Units",
                "Verdi (MNOK)": 325,
                "Status": "Annonsert",
                "Levering": "Q4 2026 / hovedsakelig 2027",
            },
            {
                "Dato": "Q2 2026",
                "Segment": "Connectivity",
                "Kunde/prosjekt": "Toll4Europe – GNSS On-Board Units",
                "Verdi (MNOK)": 155,
                "Status": "Annonsert",
                "Levering": "Fra september 2026",
            },
            {
                "Dato": "12.06.2026",
                "Segment": "PIR",
                "Kunde/prosjekt": "Europeisk defence & security-kunde",
                "Verdi (MNOK)": 225,
                "Status": "Annonsert",
                "Levering": "H2 2026",
            },
            {
                "Dato": "Q2 2026",
                "Segment": "Oceans / Security",
                "Kunde/prosjekt": "To overvåkningssonarkontrakter",
                "Verdi (MNOK)": 50,
                "Status": "Annonsert",
                "Levering": "Hovedsakelig H2 2026",
            },
            {
                "Dato": "13.08.2026",
                "Segment": "Oceans / Security",
                "Kunde/prosjekt": "Falcon Eye – Abu Dhabi",
                "Verdi (MNOK)": None,
                "Status": "Annonsert",
                "Levering": "Ikke oppgitt",
            },
        ],
        "opportunities": [
            {
                "Mulighet": "Undervannsdroner / AUV / ROV OEM-kunder",
                "Segment": "Oceans + Water Linked",
                "Sannsynlighet": "Høy",
                "Kommentar": (
                    "Water Linked gir NORBIT DVL, 3D-sonar, modem og posisjonering. "
                    "Kombinasjonen øker muligheten for kryssalg til produsenter av "
                    "autonome undervannsfarkoster."
                ),
            },
            {
                "Mulighet": "Undervannssikring av kritisk infrastruktur",
                "Segment": "Oceans / Security",
                "Sannsynlighet": "Middels–høy",
                "Kommentar": (
                    "Falcon Eye-kontrakten og eksisterende overvåkningssonarer gir "
                    "referanser mot havner, energi, forsvar og andre sikringsanlegg."
                ),
            },
            {
                "Mulighet": "Nye defence & security-ordre i PIR",
                "Segment": "PIR",
                "Sannsynlighet": "Middels–høy",
                "Kommentar": (
                    "PIR har sterk vekst fra forsvar og sikkerhet. Kapasitetsøkninger "
                    "kan støtte nye og større produksjonsordre."
                ),
            },
            {
                "Mulighet": "Flere GNSS OBU-ordre i Europa",
                "Segment": "Connectivity",
                "Sannsynlighet": "Middels",
                "Kommentar": (
                    "Gjenta ordre fra Toll4Europe viser høy kundelojalitet og fortsatt "
                    "etterspørsel etter satellittbaserte bombrikker."
                ),
            },
        ],
        "valuation": {
            "bear": 145,
            "base": 210,
            "bull": 265,
            "note": (
                "Foreløpig scenarioverdsettelse. Bear/base/bull er ikke konsensusmål. "
                "Vi bør senere koble verdiene direkte til egne EPS-estimater og valgt P/E."
            )
        }
    },

    "Cambi": {
        "ticker": "CAMBI",
        "marked": "Euronext Growth Oslo",
        "sektor": "Miljøteknologi",
        "case": "Kommer i neste steg."
    },

    "Kitron": {
        "ticker": "KIT",
        "marked": "Oslo Børs",
        "sektor": "EMS / Elektronikk",
        "case": "Kommer i neste steg."
    },

    "NOTE": {
        "ticker": "NOTE",
        "marked": "Nasdaq Stockholm",
        "sektor": "EMS / Elektronikk",
        "case": "Kommer i neste steg."
    },

    "Protector": {
        "ticker": "PROT",
        "marked": "Oslo Børs",
        "sektor": "Forsikring",
        "case": "Kommer i neste steg."
    }
}

# =========================================================
# TOPP / MENY
# =========================================================

st.title("📊 Investeringsdashboard")
st.caption(
    "Selskaper • nøkkeltall • aksjonærer • nyheter • kontrakter • verdsettelse"
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

# =========================================================
# DASHBOARD
# =========================================================

if side == "Dashboard":

    st.header("Dashboard")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selskaper", len(companies))
    c2.metric("Nye nyheter", len(companies["NORBIT"]["news"]))
    c3.metric("Aksjonærendringer", "0")
    c4.metric("Annonserte kontrakter", len(companies["NORBIT"]["contracts"]))

    st.divider()
    st.subheader("Selskapsoversikt")

    oversikt = pd.DataFrame({
        "Selskap": ["NORBIT", "Cambi", "Kitron", "NOTE", "Protector"],
        "Kurs": ["162,00", "-", "-", "-", "-"],
        "EPS LTM": ["7,04", "-", "-", "-", "-"],
        "P/E LTM": ["23,0x", "-", "-", "-", "-"],
        "FCF Yield": ["4,6%", "-", "-", "-", "-"],
        "Status": ["Følg", "Følg", "Følg", "Følg", "Følg"]
    })

    st.dataframe(oversikt, use_container_width=True, hide_index=True)

    st.subheader("Dagens viktigste endringer")
    st.info(
        "NORBIT er nå lagt inn med faktiske Q2/H1 2026-tall, kontrakter, "
        "nyheter og foreløpige investeringsmuligheter. Automatisk oppdatering "
        "kobles til senere."
    )

# =========================================================
# SELSKAPER
# =========================================================

elif side == "Selskaper":

    selskap = st.selectbox("Velg selskap", list(companies.keys()))
    info = companies[selskap]

    st.header(selskap)
    st.caption(f"{info['ticker']} | {info['marked']} | {info['sektor']}")

    if selskap != "NORBIT":
        st.info(
            "Strukturen er klar. Dette selskapet fylles med faktiske data "
            "etter at NORBIT-siden er ferdigstilt."
        )
        st.subheader("Investeringscase")
        st.write(info["case"])

    else:
        # Toppnøkkeltall - verdsettelse
        k1, k2, k3 = st.columns(3)

        k1.metric(
            "Markedsverdi",
            f"{info['market_cap']:.2f} mrd. NOK".replace(".", ",")
        )
        k2.metric(
            "P/E LTM",
            f"{info['pe_ltm']:.1f}x".replace(".", ",")
        )
        k3.metric(
            "FCF Yield LTM",
            f"{info['fcf_yield']:.1f}%".replace(".", ",")
        )

        # Toppnøkkeltall - kvalitet og balanse
        k4, k5, k6 = st.columns(3)

        k4.metric(
            "ROE LTM",
            f"{info['roe_ltm']:.1f}%".replace(".", ",")
        )
        k5.metric(
            "ROCE",
            f"{info['roce']:.1f}%".replace(".", ",")
        )
        k6.metric(
            "Netto gjeld / EBITDA",
            f"{info['nibd_ebitda']:.1f}x".replace(".", ",")
        )

        st.divider()

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

        # -------------------------------------------------
        # OVERSIKT
        # -------------------------------------------------
        with tab1:
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader("Siste kvartal – Q2 2026")

            q1, q2, q3 = st.columns(3)
            q1.metric(
                "Omsetning",
                f"{info['q2']['revenue']:.1f} MNOK".replace(".", ",")
            )
            q2.metric(
                "Vekst",
                f"{info['q2']['growth']:.0f}%"
            )
            q3.metric(
                "EBIT-margin",
                f"{info['q2']['ebit_margin']:.1f}%".replace(".", ",")
            )

            q4, q5, q6 = st.columns(3)
            q4.metric(
                "EBIT",
                f"{info['q2']['ebit']:.1f} MNOK".replace(".", ",")
            )
            q5.metric(
                "EPS",
                f"{info['q2']['eps']:.2f}".replace(".", ",")
            )
            q6.metric(
                "FCF",
                f"{info['q2']['fcf']:.1f} MNOK".replace(".", ",")
            )

            st.subheader("H1 2026")

            h1, h2, h3 = st.columns(3)
            h1.metric(
                "Omsetning",
                f"{info['h1']['revenue']:.1f} MNOK".replace(".", ",")
            )
            h2.metric(
                "Vekst",
                f"{info['h1']['growth']:.0f}%"
            )
            h3.metric(
                "EBIT-margin",
                f"{info['h1']['ebit_margin']:.1f}%".replace(".", ",")
            )

            h4, h5, h6 = st.columns(3)
            h4.metric(
                "EBIT",
                f"{info['h1']['ebit']:.1f} MNOK".replace(".", ",")
            )
            h5.metric(
                "EPS",
                f"{info['h1']['eps']:.2f}".replace(".", ",")
            )
            h6.metric(
                "FCF",
                f"{info['h1']['fcf']:.1f} MNOK".replace(".", ",")
            )

            st.subheader("Balansestyrke og kontantstrøm")
            b1, b2, b3 = st.columns(3)
            b1.metric(
                "Netto rentebærende gjeld",
                f"{info['nibd']:.0f} MNOK"
            )
            b2.metric(
                "NIBD / EBITDA",
                f"{info['nibd_ebitda']:.1f}x"
            )
            b3.metric(
                "FCF LTM",
                f"{info['fcf_ltm']:.0f} MNOK"
            )

            st.subheader("Selskapets guiding")
            for item in info["guidance"]:
                st.write(f"• {item}")

            st.subheader("Vår vurdering")
            bear, base, bull = st.columns(3)
            bear.metric("🔴 Bear", f"{info['valuation']['bear']} NOK")
            base.metric("🟡 Base", f"{info['valuation']['base']} NOK")
            bull.metric("🟢 Bull", f"{info['valuation']['bull']} NOK")
            st.caption(info["valuation"]["note"])

            st.subheader("Siste utvikling")
            st.success(
                "Sterk H1 2026 med 30 % omsetningsvekst. Connectivity og PIR "
                "driver veksten, mens Oceans fortsatt har svært høy lønnsomhet. "
                "Water Linked styrker NORBITs posisjon innen undervannsautonomi."
            )

        # -------------------------------------------------
        # NØKKELTALL
        # -------------------------------------------------
        with tab2:
            st.subheader("Historiske nøkkeltall")
            df_fin = pd.DataFrame(info["financials"])
            st.dataframe(df_fin, use_container_width=True, hide_index=True)

            st.subheader("Segmenter – Q2 2026")
            df_seg = pd.DataFrame(info["segments_q2"])
            st.dataframe(df_seg, use_container_width=True, hide_index=True)

            st.subheader("Kontantstrøm")
            cf1, cf2, cf3, cf4 = st.columns(4)
            cf1.metric("OCF Q2", f"{info['q2']['ocf']:.1f} MNOK".replace(".", ","))
            cf2.metric("FCF Q2", f"{info['q2']['fcf']:.1f} MNOK".replace(".", ","))
            cf3.metric("OCF H1", f"{info['h1']['ocf']:.1f} MNOK".replace(".", ","))
            cf4.metric("FCF H1", f"{info['h1']['fcf']:.1f} MNOK".replace(".", ","))

            st.caption(
                "FCF her er beregnet som kontantstrøm fra drift minus investeringer "
                "i driftsmidler og immaterielle eiendeler."
            )

        # -------------------------------------------------
        # AKSJONÆRER
        # -------------------------------------------------
        with tab3:
            st.subheader("Aksjonærendringer")
            st.info(
                "Neste automatiseringssteg blir å lagre en daglig aksjonærliste "
                "og sammenligne den med dagen før, siste uke og siste måned."
            )

            a1, a2, a3 = st.columns(3)
            a1.metric("Direkte aksjonærer Q2", "ca. 9 000")
            a2.metric("Topp 20 eierandel", "58,9%")
            a3.metric("Utestående aksjer", f"{info['shares_outstanding']:,}".replace(",", " "))

        # -------------------------------------------------
        # NYHETER
        # -------------------------------------------------
        with tab4:
            st.subheader("Siste relevante nyheter")
            df_news = pd.DataFrame(info["news"])
            st.dataframe(df_news, use_container_width=True, hide_index=True)

            st.caption(
                "Senere henter vi denne listen automatisk fra børsmeldinger, "
                "NORBITs IR-side og relevante eksterne kilder."
            )

        # -------------------------------------------------
        # KONTRAKTER
        # -------------------------------------------------
        with tab5:
            st.subheader("Annonserte kontrakter")
            df_contracts = pd.DataFrame(info["contracts"])
            st.dataframe(df_contracts, use_container_width=True, hide_index=True)

            st.subheader("Mulige kommende kontrakter / vekstområder")
            df_opp = pd.DataFrame(info["opportunities"])
            st.dataframe(df_opp, use_container_width=True, hide_index=True)

            st.warning(
                "Tabellen over muligheter er vår analyse, ikke annonserte kontrakter. "
                "Sannsynlighet og mulig verdi skal oppdateres når ny informasjon kommer."
            )

        # -------------------------------------------------
        # VERDSETTELSE
        # -------------------------------------------------
        with tab6:
            st.subheader("Verdsettelse")

            v1, v2, v3 = st.columns(3)
            v1.metric("Bear case", f"{info['valuation']['bear']} NOK")
            v2.metric("Base case", f"{info['valuation']['base']} NOK")
            v3.metric("Bull case", f"{info['valuation']['bull']} NOK")

            st.write("**Nåværende multipler**")
            m1, m2, m3 = st.columns(3)
            m1.metric("P/E LTM", f"{info['pe_ltm']:.1f}x".replace(".", ","))
            m2.metric("FCF yield LTM", f"{info['fcf_yield']:.1f}%".replace(".", ","))
            m3.metric("ROE LTM", f"{info['roe_ltm']:.1f}%".replace(".", ","))

            st.info(
                "Neste steg er å bygge en egen verdsettelsesmodell med "
                "2026E–2030E EPS, P/E-scenarioer og DCF. Da beregnes "
                "bear/base/bull automatisk i stedet for å være faste tall."
            )

# =========================================================
# NØKKELTALL
# =========================================================

elif side == "Nøkkeltall":
    st.header("Nøkkeltall")

    norbit = companies["NORBIT"]
    st.subheader("NORBIT")

    df = pd.DataFrame(norbit["financials"])
    st.dataframe(df, use_container_width=True, hide_index=True)

# =========================================================
# AKSJONÆRER
# =========================================================

elif side == "Aksjonærer":
    st.header("Aksjonærendringer")
    st.write(
        "Her bygger vi den daglige sammenligningen av aksjonærlister i neste steg."
    )

# =========================================================
# NYHETER
# =========================================================

elif side == "Nyheter":
    st.header("Nyheter")

    st.subheader("NORBIT")
    st.dataframe(
        pd.DataFrame(companies["NORBIT"]["news"]),
        use_container_width=True,
        hide_index=True
    )

# =========================================================
# KONTRAKTER
# =========================================================

elif side == "Kontrakter":
    st.header("Kontraktsmonitor")

    st.subheader("NORBIT – annonserte kontrakter")
    st.dataframe(
        pd.DataFrame(companies["NORBIT"]["contracts"]),
        use_container_width=True,
        hide_index=True
    )

    st.subheader("NORBIT – mulige kommende kontrakter")
    st.dataframe(
        pd.DataFrame(companies["NORBIT"]["opportunities"]),
        use_container_width=True,
        hide_index=True
    )
