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
                "Kategori": "Produkt",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "NORBIT Connect lansert",
                "Kort oppsummering": (
                    "Ny web-basert brukerflate for konfigurering og drift av ROV-sonarer. "
                    "Løsningen støtter fjernstyring og enklere operatørarbeid."
                ),
                "Betydning for caset": (
                    "Positiv produktutvikling i Oceans. Kan støtte mersalg og styrke "
                    "NORBITs posisjon hos ROV- og subsea-kunder."
                ),
                "Kilde": "NORBIT Newsroom",
                "Lenke": "https://norbit.com/newsroom/norbit-connect-new-web-based-user-interface-for-rov-operations",
            },
            {
                "Dato": "13.08.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Falcon Eye / NORBIT Security – Abu Dhabi",
                "Kort oppsummering": (
                    "NORBITs sikkerhetssonarer er valgt til undervannssikring av et "
                    "profilert waterfront-anlegg i Abu Dhabi."
                ),
                "Betydning for caset": (
                    "Strategisk viktig referanse innen sikring av kritisk infrastruktur. "
                    "Kan åpne nye muligheter mot havner, energi og forsvar."
                ),
                "Kilde": "NORBIT Newsroom",
                "Lenke": "https://norbit.com/newsroom/falcon-eye-technology-and-norbit-security-awarded-underwater-security-contract-for-an-internationally-renowned-venue-in-abu-dhabi",
            },
            {
                "Dato": "13.08.2026",
                "Kategori": "Resultat",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Q2 2026 – rekordomsetning og sterk margin",
                "Kort oppsummering": (
                    "Q2-omsetning på 831,6 MNOK, EBIT 205,2 MNOK og EBIT-margin 24,7 %."
                ),
                "Betydning for caset": (
                    "Bekrefter høy lønnsomhet og sterk vekst. Connectivity og PIR "
                    "driver veksten, mens Oceans opprettholder svært høy margin."
                ),
                "Kilde": "NORBIT Investor Relations",
                "Lenke": "https://norbit.com/investor",
            },
            {
                "Dato": "13.08.2026",
                "Kategori": "Strategi",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Strategisk og finansiell ambisjon 2026–2030",
                "Kort oppsummering": (
                    "NORBIT publiserte oppdatert strategisk og finansiell plan for 2026–2030."
                ),
                "Betydning for caset": (
                    "Gir tydelig ramme for å følge langsiktig omsetningsvekst, marginer "
                    "og kapitalavkastning."
                ),
                "Kilde": "NORBIT Investor Relations",
                "Lenke": "https://norbit.com/investor/reports-and-presentations",
            },
            {
                "Dato": "15.07.2026",
                "Kategori": "Produkt",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "Layered Media Detection lansert",
                "Kort oppsummering": (
                    "Ny funksjonalitet for hydrografiske undersøkelser i krevende sedimentforhold."
                ),
                "Betydning for caset": (
                    "Viser fortsatt innovasjon i Oceans og kan øke verdien av "
                    "WINGHEAD-plattformen mot eksisterende kunder."
                ),
                "Kilde": "NORBIT Newsroom",
                "Lenke": "https://norbit.com/newsroom",
            },
            {
                "Dato": "21.06.2026",
                "Kategori": "M&A",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Water Linked-avtalen annonsert",
                "Kort oppsummering": (
                    "NORBIT inngikk avtale om kjøp av Water Linked, som leverer DVL, "
                    "3D-sonar, undervannsmodemer og akustisk posisjonering."
                ),
                "Betydning for caset": (
                    "Styrker posisjonen mot ROV, AUV og autonome systemer og øker "
                    "muligheten for kryssalg i Oceans."
                ),
                "Kilde": "NORBIT Newsroom",
                "Lenke": "https://norbit.com/newsroom/norbit-and-water-linked-join-forces",
            },
        ],
        "upcoming_events": [
            {
                "Dato": "21–24.09.2026",
                "Hendelse": "OCEANS 2026",
                "Sted": "Monterey, USA",
                "Hvorfor følge": "Viktig Oceans-messe; produkt- og kundesignaler."
            },
            {
                "Dato": "22.09.2026",
                "Hendelse": "Nordic Defence and Security Conference 2026",
                "Sted": "Stjørdal, Norge",
                "Hvorfor følge": "Relevant for defence/security og nye kundemuligheter."
            },
            {
                "Dato": "23.09.2026",
                "Hendelse": "SpillAsia 2026",
                "Sted": "Singapore",
                "Hvorfor følge": "Relevant for maritime løsninger og internasjonal kundekontakt."
            },
            {
                "Dato": "12.11.2026",
                "Hendelse": "Q3 2026",
                "Sted": "Investor relations",
                "Hvorfor følge": "Neste kvartalsrapport; viktig for vekst, margin og kontantstrøm."
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
                "Prioritet": "🟢 Høy",
                "Mulighet": "Undervannsdroner / AUV / ROV OEM-kunder",
                "Segment": "Oceans + Water Linked",
                "Sannsynlighet": "Høy",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye OEM-avtaler, messer eller produktintegrasjoner",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Water Linked gir NORBIT DVL, 3D-sonar, modem og posisjonering. "
                    "Kombinasjonen øker muligheten for kryssalg til produsenter av "
                    "autonome undervannsfarkoster."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Undervannssikring av kritisk infrastruktur",
                "Segment": "Oceans / Security",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye havne-, energi- eller forsvarsanskaffelser",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Falcon Eye-kontrakten og eksisterende overvåkningssonarer gir "
                    "referanser mot havner, energi, forsvar og andre sikringsanlegg."
                ),
            },
            {
                "Prioritet": "🟡 Middels–høy",
                "Mulighet": "Nye defence & security-ordre i PIR",
                "Segment": "PIR",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye kundeordre eller økt produksjonskapasitet",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "PIR har sterk vekst fra forsvar og sikkerhet. Kapasitetsøkninger "
                    "kan støtte nye og større produksjonsordre."
                ),
            },
            {
                "Prioritet": "🟡 Middels",
                "Mulighet": "Flere GNSS OBU-ordre i Europa",
                "Segment": "Connectivity",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye volumordre fra europeiske bomoperatører",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Gjenta ordre fra Toll4Europe viser høy kundelojalitet og fortsatt "
                    "etterspørsel etter satellittbaserte bombrikker."
                ),
            },
        ],
        "valuation": {
            "reference_price": 162.0,
            "eps_2026": 8.0,
            "growth_bear": 7.0,
            "growth_base": 17.0,
            "growth_bull": 24.0,
            "pe_bear": 17.0,
            "pe_base": 21.0,
            "pe_bull": 25.0,
            "required_return": 10.0,
            "target_year": 2028,
            "note": (
                "Forutsetningene er våre arbeidsestimater og kan endres direkte i "
                "verdsettelsesfanen. De er ikke konsensusestimater."
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

    st.dataframe(oversikt, width="stretch", hide_index=True)

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
            f"{info['nibd_ebitda']:.1f}x".replace(".", ",").replace(".", ",")
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
                f"{info['h1']['revenue']:,.1f} MNOK".replace(",", " ").replace(".", ",")
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
                f"{info['nibd_ebitda']:.1f}x".replace(".", ",")
            )
            b3.metric(
                "FCF LTM",
                f"{info['fcf_ltm']:.0f} MNOK"
            )

            st.subheader("Selskapets guiding")
            for item in info["guidance"]:
                st.write(f"• {item}")

            st.subheader("Vår vurdering")
            v1, v2, v3 = st.columns(3)
            v1.metric("2026E EPS – arbeidsestimat", f"{info['valuation']['eps_2026']:.2f}".replace(".", ","))
            v2.metric("Base EPS-vekst", f"{info['valuation']['growth_base']:.0f}%")
            v3.metric("Base P/E", f"{info['valuation']['pe_base']:.0f}x")
            st.caption(
                "Dynamisk bear/base/bull-verdsettelse ligger under fanen Verdsettelse. "
                + info["valuation"]["note"]
            )

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
            st.subheader("Nøkkeltall – utvikling")

            key_rows = []
            for row in info["financials"]:
                key_rows.append({
                    "Periode": row["Periode"],
                    "Omsetning (MNOK)": row["Omsetning"],
                    "Vekst": row["Vekst"],
                    "EBIT (MNOK)": row["EBIT"],
                    "EBIT-margin": row["EBIT-margin"],
                    "EPS": row["EPS"],
                })

            df_fin = pd.DataFrame(key_rows)
            st.dataframe(
                df_fin,
                width="stretch",
                hide_index=True
            )

            st.caption(
                "Års- og kvartalstall vises samlet for rask sammenligning. "
                "Neste steg blir å legge inn 2026E–2028E som egne estimatkolonner."
            )

            st.subheader("Q2 2026 – segmenter")
            df_seg = pd.DataFrame(info["segments_q2"])
            st.dataframe(
                df_seg,
                width="stretch",
                hide_index=True
            )

            st.subheader("Kontantstrøm")
            cf1, cf2, cf3 = st.columns(3)
            cf1.metric(
                "FCF Q2",
                f"{info['q2']['fcf']:.1f} MNOK".replace(".", ",")
            )
            cf2.metric(
                "FCF H1",
                f"{info['h1']['fcf']:.1f} MNOK".replace(".", ",")
            )
            cf3.metric(
                "FCF LTM",
                f"{info['fcf_ltm']:.0f} MNOK"
            )

            cf4, cf5, cf6 = st.columns(3)
            cf4.metric(
                "OCF Q2",
                f"{info['q2']['ocf']:.1f} MNOK".replace(".", ",")
            )
            cf5.metric(
                "OCF H1",
                f"{info['h1']['ocf']:.1f} MNOK".replace(".", ",")
            )
            cf6.metric(
                "FCF Yield LTM",
                f"{info['fcf_yield']:.1f}%".replace(".", ",")
            )

            st.caption(
                "FCF = kontantstrøm fra drift minus investeringer i driftsmidler "
                "og immaterielle eiendeler."
            )

            st.subheader("Hva vi følger videre")
            st.markdown(
                """
- Omsetningsvekst mot 2030-målet
- EBIT-margin mot målintervallet 20–25 %
- EPS-vekst og kontantkonvertering
- Utvikling i ROCE
- Netto gjeld / EBITDA etter oppkjøp
- Segmentmiks mellom Oceans, Connectivity og PIR
                """
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
            st.subheader("Nyhetsmonitor")

            news_df = pd.DataFrame(info["news"])
            important_count = sum(
                1 for item in info["news"] if item["Viktighet"].startswith("🔴")
            )

            n1, n2, n3 = st.columns(3)
            n1.metric("Relevante saker", len(info["news"]))
            n2.metric("Viktige saker", important_count)
            n3.metric("Neste rapport", "12.11.2026")

            st.caption(
                "Nyhetsmonitoren skiller mellom resultater, kontrakter, strategi, "
                "M&A og produktnyheter. Målet er å vise hva som faktisk endrer investeringscaset."
            )

            st.subheader("Siste relevante nyheter")
            st.dataframe(
                news_df[
                    [
                        "Dato",
                        "Kategori",
                        "Viktighet",
                        "Hendelse",
                        "Kort oppsummering",
                        "Betydning for caset",
                        "Kilde",
                        "Lenke",
                    ]
                ],
                width="stretch",
                hide_index=True
            )

            st.subheader("Kommende hendelser")
            st.dataframe(
                pd.DataFrame(info["upcoming_events"]),
                width="stretch",
                hide_index=True
            )

            st.info(
                "Neste automatiseringssteg blir å hente nye saker løpende fra "
                "NORBITs IR-side, NewsWeb og utvalgte eksterne kilder."
            )

        # -------------------------------------------------
        # KONTRAKTER
        # -------------------------------------------------
        with tab5:
            known_contract_value = sum(
                item["Verdi (MNOK)"]
                for item in info["contracts"]
                if isinstance(item["Verdi (MNOK)"], (int, float))
            )
            active_opportunities = len(info["opportunities"])
            contract_segments = len({
                item["Segment"] for item in info["contracts"] + info["opportunities"]
            })

            st.subheader("Kontraktsmonitor")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Kjent annonsert verdi", f"{known_contract_value:,.0f} MNOK".replace(",", " "))
            c2.metric("Annonserte kontrakter", len(info["contracts"]))
            c3.metric("Aktive muligheter", active_opportunities)
            c4.metric("Segmenter overvåket", contract_segments)

            st.caption(
                "Kjent annonsert verdi summerer bare kontrakter der NORBIT har oppgitt verdi. "
                "Falcon Eye-kontrakten er derfor ikke inkludert i summen."
            )

            st.subheader("Annonserte kontrakter")
            df_contracts = pd.DataFrame(info["contracts"])
            st.dataframe(
                df_contracts,
                width="stretch",
                hide_index=True
            )

            st.subheader("Potensielle kontrakter og anbud")
            df_opp = pd.DataFrame(info["opportunities"])
            opp_cols = [
                "Prioritet",
                "Mulighet",
                "Segment",
                "Sannsynlighet",
                "Est. verdi (MNOK)",
                "Status",
                "Neste trigger",
                "Sist oppdatert",
                "Kommentar",
            ]
            st.dataframe(
                df_opp[opp_cols],
                width="stretch",
                hide_index=True
            )

            st.warning(
                "Potensielle kontrakter/anbud er vår analyse, ikke annonserte ordre. "
                "Estimert verdi står tom der vi ikke har et forsvarlig offentlig anslag."
            )

            st.subheader("Hva bør overvåkes nå?")
            st.markdown(
                """
- Nye AUV/ROV-OEM-avtaler etter Water Linked-integrasjonen
- Nye sikringsprosjekter for havner, energi og kritisk infrastruktur
- Nye defence & security-produksjonsordre i PIR
- Nye GNSS OBU-volumordre i Europa
                """
            )

        # -------------------------------------------------
        # VERDSETTELSE
        # -------------------------------------------------
        with tab6:
            st.subheader("Dynamisk verdsettelse")

            st.caption(
                "Modellen estimerer EPS frem til valgt målår og multipliserer med "
                "en P/E-multippel. Deretter beregnes total avkastning, årlig avkastning "
                "(CAGR) og nåverdi basert på valgt avkastningskrav."
            )

            with st.expander("Forutsetninger", expanded=True):
                a1, a2, a3, a4 = st.columns(4)

                reference_price = a1.number_input(
                    "Referansekurs (NOK)",
                    min_value=1.0,
                    value=float(info["valuation"]["reference_price"]),
                    step=1.0,
                    key="norbit_reference_price"
                )

                eps_2026 = a2.number_input(
                    "EPS 2026E",
                    min_value=0.1,
                    value=float(info["valuation"]["eps_2026"]),
                    step=0.1,
                    key="norbit_eps_2026"
                )

                target_year = a3.selectbox(
                    "Målår",
                    [2028, 2029, 2030],
                    index=[2028, 2029, 2030].index(info["valuation"]["target_year"]),
                    key="norbit_target_year"
                )

                required_return = a4.number_input(
                    "Avkastningskrav",
                    min_value=0.0,
                    max_value=30.0,
                    value=float(info["valuation"]["required_return"]),
                    step=0.5,
                    format="%.1f",
                    key="norbit_required_return"
                )

                st.markdown("**EPS-vekst per år**")
                g1, g2, g3 = st.columns(3)
                growth_bear = g1.number_input(
                    "Bear vekst",
                    min_value=-20.0,
                    max_value=50.0,
                    value=float(info["valuation"]["growth_bear"]),
                    step=1.0,
                    format="%.1f",
                    key="norbit_growth_bear"
                )
                growth_base = g2.number_input(
                    "Base vekst",
                    min_value=-20.0,
                    max_value=50.0,
                    value=float(info["valuation"]["growth_base"]),
                    step=1.0,
                    format="%.1f",
                    key="norbit_growth_base"
                )
                growth_bull = g3.number_input(
                    "Bull vekst",
                    min_value=-20.0,
                    max_value=60.0,
                    value=float(info["valuation"]["growth_bull"]),
                    step=1.0,
                    format="%.1f",
                    key="norbit_growth_bull"
                )

                st.markdown("**P/E i målåret**")
                p1, p2, p3 = st.columns(3)
                pe_bear = p1.number_input(
                    "Bear P/E",
                    min_value=5.0,
                    max_value=50.0,
                    value=float(info["valuation"]["pe_bear"]),
                    step=1.0,
                    key="norbit_pe_bear"
                )
                pe_base = p2.number_input(
                    "Base P/E",
                    min_value=5.0,
                    max_value=50.0,
                    value=float(info["valuation"]["pe_base"]),
                    step=1.0,
                    key="norbit_pe_base"
                )
                pe_bull = p3.number_input(
                    "Bull P/E",
                    min_value=5.0,
                    max_value=60.0,
                    value=float(info["valuation"]["pe_bull"]),
                    step=1.0,
                    key="norbit_pe_bull"
                )

            years = list(range(2026, 2031))

            scenario_rows = []
            for year in years:
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + growth_bear / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + growth_base / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + growth_bull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            target_row = eps_table.loc[eps_table["År"] == target_year].iloc[0]

            years_to_target = target_year - 2026

            bear_value = float(target_row["Bear EPS"]) * pe_bear
            base_value = float(target_row["Base EPS"]) * pe_base
            bull_value = float(target_row["Bull EPS"]) * pe_bull

            def scenario_metrics(target_value):
                total_return = (target_value / reference_price - 1) * 100

                if years_to_target > 0:
                    cagr = ((target_value / reference_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value

                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = scenario_metrics(bear_value)
            base_total, base_cagr, base_pv = scenario_metrics(base_value)
            bull_total, bull_cagr, bull_pv = scenario_metrics(bull_value)

            st.subheader(f"Estimert kurs i {target_year}")

            v1, v2, v3 = st.columns(3)
            v1.metric("🔴 Bear", f"{bear_value:.0f} NOK")
            v2.metric("🟡 Base", f"{base_value:.0f} NOK")
            v3.metric("🟢 Bull", f"{bull_value:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")

            r1, r2, r3 = st.columns(3)

            with r1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bear_pv:.0f} NOK**"
                )

            with r2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{base_pv:.0f} NOK**"
                )

            with r3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bull_pv:.0f} NOK**"
                )

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt "
                "avkastningskrav. Hvis nåverdien ligger over referansekursen, tilsier "
                "modellen at scenarioet gir mer enn avkastningskravet."
            )

            st.subheader("EPS-scenario 2026E–2030E")

            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )

            st.dataframe(
                display_eps,
                width="stretch",
                hide_index=True
            )

            base_target_eps = float(target_row["Base EPS"])
            st.subheader(f"P/E-sensitivitet – Base EPS {target_year}")

            pe_levels = [16, 18, 20, 22, 24, 26, 28]

            sensitivity_rows = []
            for pe in pe_levels:
                target_value = base_target_eps * pe
                total_return, cagr, present_value = scenario_metrics(target_value)

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        f"Kursmål {target_year}": f"{target_value:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                    }
                )

            sensitivity = pd.DataFrame(sensitivity_rows)

            st.dataframe(
                sensitivity,
                width="stretch",
                hide_index=True
            )

            st.subheader("Kontantstrømbasert sjekk")

            fcf_per_share = (
                info["fcf_ltm"] * 1_000_000 / info["shares_outstanding"]
            )

            f1, f2, f3 = st.columns(3)
            f1.metric(
                "FCF per aksje LTM",
                f"{fcf_per_share:.2f} NOK".replace(".", ",")
            )
            f2.metric(
                "FCF Yield LTM",
                f"{info['fcf_yield']:.1f}%".replace(".", ",")
            )
            f3.metric(
                "P/E LTM",
                f"{info['pe_ltm']:.1f}x".replace(".", ",")
            )

            st.caption(
                info["valuation"]["note"]
                + " Referansekurs brukes bare som sammenligningsgrunnlag i "
                "verdsettelsesfanen."
            )

            st.info(
                "Neste steg kan være en separat DCF-modell med omsetning, "
                "EBIT-margin, skatt, reinvesteringer, terminalvekst og diskonteringsrente."
            )

# =========================================================
# NØKKELTALL
# =========================================================

elif side == "Nøkkeltall":
    st.header("Nøkkeltall")

    norbit = companies["NORBIT"]
    st.subheader("NORBIT")

    df = pd.DataFrame(norbit["financials"])
    st.dataframe(df, width="stretch", hide_index=True)

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
    st.header("Nyhetsmonitor")

    norbit = companies["NORBIT"]

    n1, n2 = st.columns(2)
    n1.metric("Relevante saker", len(norbit["news"]))
    n2.metric(
        "Viktige saker",
        sum(1 for item in norbit["news"] if item["Viktighet"].startswith("🔴"))
    )

    st.subheader("NORBIT – siste relevante nyheter")
    st.dataframe(
        pd.DataFrame(norbit["news"])[
            [
                "Dato",
                "Kategori",
                "Viktighet",
                "Hendelse",
                "Kort oppsummering",
                "Betydning for caset",
                "Kilde",
                "Lenke",
            ]
        ],
        width="stretch",
        hide_index=True
    )

    st.subheader("Kommende hendelser")
    st.dataframe(
        pd.DataFrame(norbit["upcoming_events"]),
        width="stretch",
        hide_index=True
    )

# =========================================================
# KONTRAKTER
# =========================================================

elif side == "Kontrakter":
    st.header("Kontraktsmonitor")

    norbit = companies["NORBIT"]
    known_contract_value = sum(
        item["Verdi (MNOK)"]
        for item in norbit["contracts"]
        if isinstance(item["Verdi (MNOK)"], (int, float))
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("NORBIT – kjent annonsert verdi", f"{known_contract_value:,.0f} MNOK".replace(",", " "))
    c2.metric("Annonserte kontrakter", len(norbit["contracts"]))
    c3.metric("Aktive muligheter", len(norbit["opportunities"]))

    st.subheader("NORBIT – annonserte kontrakter")
    st.dataframe(
        pd.DataFrame(norbit["contracts"]),
        width="stretch",
        hide_index=True
    )

    st.subheader("NORBIT – potensielle kontrakter og anbud")
    df_opp = pd.DataFrame(norbit["opportunities"])
    st.dataframe(
        df_opp[
            [
                "Prioritet",
                "Mulighet",
                "Segment",
                "Sannsynlighet",
                "Est. verdi (MNOK)",
                "Status",
                "Neste trigger",
                "Sist oppdatert",
                "Kommentar",
            ]
        ],
        width="stretch",
        hide_index=True
    )
