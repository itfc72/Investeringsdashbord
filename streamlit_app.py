import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import re
import copy
import base64
import urllib.request
import urllib.error
import urllib.parse

st.set_page_config(
    page_title="Investeringsdashboard",
    page_icon="📊",
    layout="wide"
)


def _read_shareholder_csv(uploaded_file):
    """Les CSV fra ulike eksportformater og separatorer."""
    attempts = [
        {"encoding": "utf-8-sig"},
        {"encoding": "utf-8"},
        {"encoding": "latin1"},
    ]

    last_error = None
    for params in attempts:
        try:
            uploaded_file.seek(0)
            return pd.read_csv(
                uploaded_file,
                sep=None,
                engine="python",
                **params
            )
        except Exception as exc:
            last_error = exc

    raise ValueError(f"Kunne ikke lese CSV-filen: {last_error}")


def _find_shareholder_column(columns, candidates):
    normalized = {
        str(col).strip().lower()
        .replace("_", " ")
        .replace("-", " "): col
        for col in columns
    }

    for candidate in candidates:
        candidate = candidate.lower()
        if candidate in normalized:
            return normalized[candidate]

    for normalized_name, original in normalized.items():
        for candidate in candidates:
            if candidate.lower() in normalized_name:
                return original

    return None


def _standardize_shareholder_df(df, shares_outstanding):
    owner_col = _find_shareholder_column(
        df.columns,
        [
            "aksjonær",
            "aksjonaer",
            "shareholder",
            "eier",
            "investor",
            "navn",
            "name",
        ],
    )

    shares_col = _find_shareholder_column(
        df.columns,
        [
            "antall aksjer",
            "aksjer",
            "shares",
            "beholdning",
            "holding",
            "antall",
            "quantity",
            "qty",
        ],
    )

    if owner_col is None or shares_col is None:
        raise ValueError(
            "Fant ikke kolonnene for aksjonær og antall aksjer. "
            "Bruk helst kolonnene 'Aksjonær' og 'Antall aksjer'."
        )

    clean = df[[owner_col, shares_col]].copy()
    clean.columns = ["Aksjonær", "Antall aksjer"]

    clean["Aksjonær"] = (
        clean["Aksjonær"]
        .astype(str)
        .str.strip()
    )

    clean["Antall aksjer"] = (
        clean["Antall aksjer"]
        .astype(str)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    clean["Antall aksjer"] = pd.to_numeric(
        clean["Antall aksjer"],
        errors="coerce"
    )

    clean = clean.dropna(subset=["Antall aksjer"])
    clean = clean[clean["Aksjonær"].ne("")]
    clean = clean[clean["Aksjonær"].str.lower().ne("nan")]

    clean = (
        clean.groupby("Aksjonær", as_index=False)["Antall aksjer"]
        .sum()
    )

    clean["Antall aksjer"] = clean["Antall aksjer"].round().astype(int)
    clean["Eierandel"] = clean["Antall aksjer"] / shares_outstanding * 100

    return clean


def render_shareholder_monitor(info, key_prefix="norbit"):
    st.subheader("Aksjonærmonitor")

    st.caption(
        "Du kan nå legge inn aksjonærlistene direkte på siden. "
        "Senere kobler vi dette til automatisk daglig innhenting."
    )

    mode = st.radio(
        "Hvordan vil du legge inn aksjonærlistene?",
        ["Direkte på siden", "Last opp CSV"],
        horizontal=True,
        key=f"{key_prefix}_shareholder_mode",
    )

    previous = None
    current = None

    if mode == "Direkte på siden":
        st.info(
            "Du kan skrive inn radene manuelt eller lime inn flere rader fra Excel/nettside "
            "direkte i tabellene. Bruk + nederst i tabellen for å legge til flere rader."
        )

        empty_rows = pd.DataFrame(
            {
                "Aksjonær": [""] * 12,
                "Antall aksjer": [None] * 12,
            }
        )

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Forrige aksjonærliste**")
            previous_input = st.data_editor(
                empty_rows.copy(),
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                key=f"{key_prefix}_previous_editor",
                column_config={
                    "Aksjonær": st.column_config.TextColumn("Aksjonær"),
                    "Antall aksjer": st.column_config.NumberColumn(
                        "Antall aksjer",
                        min_value=0,
                        step=1,
                        format="%d",
                    ),
                },
            )

        with c2:
            st.markdown("**Dagens aksjonærliste**")
            current_input = st.data_editor(
                empty_rows.copy(),
                num_rows="dynamic",
                width="stretch",
                hide_index=True,
                key=f"{key_prefix}_current_editor",
                column_config={
                    "Aksjonær": st.column_config.TextColumn("Aksjonær"),
                    "Antall aksjer": st.column_config.NumberColumn(
                        "Antall aksjer",
                        min_value=0,
                        step=1,
                        format="%d",
                    ),
                },
            )

        previous_input = previous_input[
            previous_input["Aksjonær"].astype(str).str.strip().ne("")
        ].copy()

        current_input = current_input[
            current_input["Aksjonær"].astype(str).str.strip().ne("")
        ].copy()

        if not previous_input.empty:
            previous = _standardize_shareholder_df(
                previous_input,
                info["shares_outstanding"],
            )

        if not current_input.empty:
            current = _standardize_shareholder_df(
                current_input,
                info["shares_outstanding"],
            )

    else:
        template = (
            pd.DataFrame(
                {
                    "Aksjonær": ["Eksempel Investor AS"],
                    "Antall aksjer": [100000],
                }
            )
            .to_csv(index=False, sep=";")
            .encode("utf-8-sig")
        )

        st.download_button(
            "Last ned CSV-mal",
            data=template,
            file_name="aksjonaerliste-mal.csv",
            mime="text/csv",
            key=f"{key_prefix}_shareholder_template",
        )

        u1, u2 = st.columns(2)

        previous_file = u1.file_uploader(
            "Forrige aksjonærliste (CSV)",
            type=["csv"],
            key=f"{key_prefix}_shareholders_previous",
        )

        current_file = u2.file_uploader(
            "Dagens aksjonærliste (CSV)",
            type=["csv"],
            key=f"{key_prefix}_shareholders_current",
        )

        if previous_file is not None:
            try:
                previous_raw = _read_shareholder_csv(previous_file)
                previous = _standardize_shareholder_df(
                    previous_raw,
                    info["shares_outstanding"],
                )
            except Exception as exc:
                st.error(f"Forrige liste: {exc}")

        if current_file is not None:
            try:
                current_raw = _read_shareholder_csv(current_file)
                current = _standardize_shareholder_df(
                    current_raw,
                    info["shares_outstanding"],
                )
            except Exception as exc:
                st.error(f"Dagens liste: {exc}")

    if previous is None or current is None or previous.empty or current.empty:
        st.info(
            "Legg inn både forrige og dagens aksjonærliste for å beregne endringer."
        )

        a1, a2 = st.columns(2)
        a1.metric(
            "Utestående aksjer",
            f"{info['shares_outstanding']:,}".replace(",", " "),
        )
        a2.metric(
            "Automatisk historikk",
            "Neste steg",
        )
        return

    comparison = current.merge(
        previous,
        on="Aksjonær",
        how="outer",
        suffixes=("_i_dag", "_forrige"),
    )

    comparison["Antall aksjer_i_dag"] = (
        comparison["Antall aksjer_i_dag"]
        .fillna(0)
        .astype(int)
    )

    comparison["Antall aksjer_forrige"] = (
        comparison["Antall aksjer_forrige"]
        .fillna(0)
        .astype(int)
    )

    comparison["Endring"] = (
        comparison["Antall aksjer_i_dag"]
        - comparison["Antall aksjer_forrige"]
    )

    comparison["Eierandel i dag"] = (
        comparison["Antall aksjer_i_dag"]
        / info["shares_outstanding"]
        * 100
    )

    def status(row):
        if row["Antall aksjer_forrige"] == 0 and row["Antall aksjer_i_dag"] > 0:
            return "Ny"
        if row["Antall aksjer_i_dag"] == 0 and row["Antall aksjer_forrige"] > 0:
            return "Utgått"
        if row["Endring"] > 0:
            return "Økt"
        if row["Endring"] < 0:
            return "Redusert"
        return "Uendret"

    comparison["Status"] = comparison.apply(status, axis=1)

    new_count = int((comparison["Status"] == "Ny").sum())
    exited_count = int((comparison["Status"] == "Utgått").sum())
    increased_count = int((comparison["Endring"] > 0).sum())
    reduced_count = int((comparison["Endring"] < 0).sum())

    top20 = (
        current.sort_values("Antall aksjer", ascending=False)
        .head(20)["Antall aksjer"]
        .sum()
        / info["shares_outstanding"]
        * 100
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Økt beholdning", increased_count)
    m2.metric("Redusert beholdning", reduced_count)
    m3.metric("Nye på listen", new_count)
    m4.metric("Utgått fra listen", exited_count)
    m5.metric("Topp 20 eierandel", f"{top20:.1f}%".replace(".", ","))

    st.subheader("Største endringer")

    changed = comparison[comparison["Endring"] != 0].copy()
    changed["Absolutt endring"] = changed["Endring"].abs()

    changed = changed.sort_values(
        "Absolutt endring",
        ascending=False,
    )

    change_view = changed[
        [
            "Aksjonær",
            "Antall aksjer_i_dag",
            "Antall aksjer_forrige",
            "Endring",
            "Eierandel i dag",
            "Status",
        ]
    ].copy()

    change_view.columns = [
        "Aksjonær",
        "Aksjer i dag",
        "Aksjer forrige",
        "Endring",
        "Eierandel i dag",
        "Status",
    ]

    change_view["Eierandel i dag"] = change_view["Eierandel i dag"].map(
        lambda x: f"{x:.2f}%".replace(".", ",")
    )

    st.dataframe(
        change_view,
        width="stretch",
        hide_index=True,
    )

    st.subheader("Største kjøp og salg")

    b1, b2 = st.columns(2)

    buys = (
        comparison[comparison["Endring"] > 0]
        .sort_values("Endring", ascending=False)
        .head(10)
        [["Aksjonær", "Endring", "Antall aksjer_i_dag"]]
        .copy()
    )
    buys.columns = ["Aksjonær", "Kjøpt", "Aksjer i dag"]

    sells = (
        comparison[comparison["Endring"] < 0]
        .sort_values("Endring", ascending=True)
        .head(10)
        [["Aksjonær", "Endring", "Antall aksjer_i_dag"]]
        .copy()
    )
    sells["Endring"] = sells["Endring"].abs()
    sells.columns = ["Aksjonær", "Solgt", "Aksjer i dag"]

    with b1:
        st.markdown("**Største kjøp**")
        st.dataframe(
            buys,
            width="stretch",
            hide_index=True,
        )

    with b2:
        st.markdown("**Største salg**")
        st.dataframe(
            sells,
            width="stretch",
            hide_index=True,
        )

    st.subheader("Dagens største aksjonærer")

    current_top = (
        current.sort_values("Antall aksjer", ascending=False)
        .head(30)
        .copy()
    )

    current_top["Eierandel"] = current_top["Eierandel"].map(
        lambda x: f"{x:.2f}%".replace(".", ",")
    )

    st.dataframe(
        current_top,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Neste versjon lagrer daglige lister automatisk, slik at vi kan vise "
        "endringer siste 1, 7 og 30 dager uten manuell opplasting."
    )


def metric_with_yoy(container, label, value, yoy_text):
    """Vis KPI med liten YoY-kommentar under tallet."""
    container.metric(label, value)
    if yoy_text:
        container.caption(f"({yoy_text})")


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
        "dashboard_5y": {
            "revenue_cagr": 32.2,
            "eps_cagr": 67.5,
            "fcf_yield_avg": 4.6,
            "ebit_margin_avg": 16.5,
        },
        "q2": {
            "revenue": 831.6,
            "growth": 22.0,
            "ebit": 205.2,
            "ebit_margin": 24.7,
            "eps": 2.45,
            "ocf": 275.2,
            "fcf": 219.4,
        },
        "q2_yoy": {
            "revenue": "+22% mot i fjor",
            "ocf": "+41% mot i fjor",
            "ebit_margin": "-0,8 pp mot i fjor",
            "ebit": "+18% mot i fjor",
            "eps": "+19% mot i fjor",
            "fcf": "+46% mot i fjor",
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
        "h1_yoy": {
            "revenue": "+30% mot i fjor",
            "ocf": "+60% mot i fjor",
            "ebit_margin": "-1,9 pp mot i fjor",
            "ebit": "+20% mot i fjor",
            "eps": "+20% mot i fjor",
            "fcf": "+77% mot i fjor",
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
        "what_follow": [
            "Omsetningsvekst mot 2030-målet.",
            "EBIT-margin mot målintervallet 20–25 %.",
            "EPS-vekst og kontantkonvertering.",
            "Utvikling i ROCE.",
            "Netto gjeld / EBITDA etter oppkjøp.",
            "Segmentmiks mellom Oceans, Connectivity og PIR.",
        ],
        "latest_development": (
            "Sterk H1 2026 med 30 % omsetningsvekst. Connectivity og PIR "
            "driver veksten, mens Oceans fortsatt har svært høy lønnsomhet. "
            "Water Linked styrker NORBITs posisjon innen undervannsautonomi."
        ),
        "news_next_report": "12.11.2026",
        "news_auto_source": (
            "Neste automatiseringssteg blir å hente nye saker løpende fra "
            "NORBITs IR-side, NewsWeb og utvalgte eksterne kilder."
        ),
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
        "contract_value_metric_label": "Kjent annonsert verdi",
        "contract_value_caption": (
            "Kjent annonsert verdi summerer bare kontrakter der NORBIT har oppgitt "
            "konkret verdi. Falcon Eye-kontrakten er derfor ikke inkludert i summen."
        ),
        "contract_watchlist": [
            "Nye AUV/ROV-OEM-avtaler etter Water Linked-integrasjonen.",
            "Nye sikringsprosjekter for havner, energi og kritisk infrastruktur.",
            "Nye defence & security-produksjonsordre i PIR.",
            "Nye GNSS OBU-volumordre i Europa.",
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
            "dcf_revenue_2026": 3000.0,
            "dcf_revenue_2030": 6000.0,
            "dcf_ebit_margin_2026": 22.0,
            "dcf_ebit_margin_2030": 23.0,
            "dcf_tax_rate": 22.0,
            "dcf_conversion": 85.0,
            "dcf_wacc": 9.5,
            "dcf_terminal_growth": 3.0,
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
        "sektor": "Miljøteknologi / Vann / Biogass",
        "case": (
            "Cambi er en global markedsleder innen termisk hydrolyse (THP) for "
            "avløpsslam og organisk avfall. Investeringscaset bygger på en stor og "
            "voksende installert base, strukturell etterspørsel etter mer effektiv "
            "slambehandling, høy aktivitet i Storbritannias AMP8-program, nye markeder "
            "som India, New Zealand og Egypt, samt økende tilbakevendende inntekter "
            "fra service og Grønn Vekst. Resultatene kan variere mye mellom kvartaler "
            "fordi store prosjekter inntektsføres etter fremdrift."
        ),
        "price": 24.40,
        "price_date": "11.09.2026",
        "market_cap": 3.90,
        "eps_ltm": 0.39,
        "pe_ltm": 63.2,
        "fcf_ltm": 363.9,
        "fcf_yield": 9.3,
        "roe_ltm": 13.2,
        "roce": 18.7,
        "nibd": -388.4,
        "nibd_ebitda": -3.2,
        "shares_outstanding": 160_030_000,
        "dashboard_5y": {
            "revenue_cagr": 23.8,
            # EPS var negativt i deler av perioden; CAGR blir derfor misvisende.
            "eps_cagr": None,
            "fcf_yield_avg": 4.2,
            "ebit_margin_avg": 11.7,
        },
        "q2": {
            "revenue": 264.9,
            "growth": -22.5,
            "ebit": 20.7,
            "ebit_margin": 7.8,
            "eps": 0.10,
            "ocf": 156.1,
            "fcf": 154.0,
        },
        "q2_yoy": {
            "revenue": "-22% mot i fjor",
            "ocf": "+45% mot i fjor",
            "ebit_margin": "-12,9 pp mot i fjor",
            "ebit": "-71% mot i fjor",
            "eps": "-83% mot i fjor",
            "fcf": "+49% mot i fjor",
        },
        "h1": {
            "revenue": 443.6,
            "growth": -21.7,
            "ebit": 39.5,
            "ebit_margin": 8.9,
            "eps": 0.13,
            "ocf": 151.9,
            "fcf": 148.0,
        },
        "h1_yoy": {
            "revenue": "-22% mot i fjor",
            "ocf": "+177% mot i fjor",
            "ebit_margin": "-4,7 pp mot i fjor",
            "ebit": "-49% mot i fjor",
            "eps": "-79% mot i fjor",
            "fcf": "+203% mot i fjor",
        },
        "financials": [
            {
                "Periode": "2024",
                "Omsetning": 1033.0,
                "Vekst": "6%",
                "EBIT": 199.6,
                "EBIT-margin": "19%",
                "EPS": 0.94,
            },
            {
                "Periode": "2025",
                "Omsetning": 1068.0,
                "Vekst": "3%",
                "EBIT": 142.2,
                "EBIT-margin": "13%",
                "EPS": 0.84,
            },
            {
                "Periode": "Q1 2026",
                "Omsetning": 178.7,
                "Vekst": "-21%",
                "EBIT": 18.8,
                "EBIT-margin": "11%",
                "EPS": 0.03,
            },
            {
                "Periode": "Q2 2026",
                "Omsetning": 264.9,
                "Vekst": "-23%",
                "EBIT": 20.7,
                "EBIT-margin": "8%",
                "EPS": 0.10,
            },
            {
                "Periode": "H1 2026",
                "Omsetning": 443.6,
                "Vekst": "-22%",
                "EBIT": 39.5,
                "EBIT-margin": "9%",
                "EPS": 0.13,
            },
        ],
        "segments_q2": [
            {
                "Segment": "Technology",
                "Omsetning Q2": 169.0,
                "Vekst": "-31%",
                "EBIT": 5.4,
                "EBIT-margin": "3%",
            },
            {
                "Segment": "Solutions",
                "Omsetning Q2": 96.0,
                "Vekst": "-2%",
                "EBIT": 15.3,
                "EBIT-margin": "16%",
            },
        ],
        "order_kpis": {
            "Ordreinngang Q2": "554 MNOK",
            "Ordrebok Q2": "1 479 MNOK",
            "Technology backlog": "836 MNOK",
            "Solutions backlog": "643 MNOK",
        },
        "guidance": [
            "2026: Driftsresultatet ventes fortsatt å bli lavere enn i 2025.",
            "Ordrebok ved Q2 2026: NOK 1,479 mrd., 58 % høyere enn Q2 2025.",
            "25 % av ordreboken ventes levert i H2 2026, 29 % i 2027 og 46 % i 2028 eller senere.",
            "Selskapet uttrykker fortsatt tillit til den langsiktige veksten.",
        ],
        "what_follow": [
            "Ordreinngang og utvikling mot en ordrebok på rundt NOK 2 mrd.",
            "Konvertering av engineering-avtaler til full produksjon og levering.",
            "AMP8-kontrakter i Storbritannia frem mot 2030.",
            "Marginnormalisering i Technology etter svakt H1 2026.",
            "Lønnsomhet og tilbakevendende inntekter i Solutions / Grønn Vekst.",
            "Kontantkonvertering, som kan variere betydelig med prosjektmilepæler.",
        ],
        "latest_development": (
            "Ordreboken har styrket seg kraftig gjennom 2026. Etter Q2 har Cambi "
            "blant annet vunnet en ny biosolidskontrakt i Eidsvoll og en major "
            "THP-kontrakt i Alexandria, Egypt. Kort sikt preges fortsatt av lavere "
            "resultatbidrag fra Technology, mens den kommersielle aktiviteten er sterk."
        ),
        "news_next_report": "04.11.2026",
        "news_auto_source": (
            "Neste automatiseringssteg blir å hente nye saker løpende fra Cambis "
            "IR-side, Euronext/NewsWeb og utvalgte eksterne kilder."
        ),
        "news": [
            {
                "Dato": "09.09.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Major THP-kontrakt i Alexandria, Egypt",
                "Kort oppsummering": (
                    "Cambi skal levere fire THP-systemer og tilhørende utstyr til "
                    "Alexandria West renseanlegg. Kontrakten starter med engineering."
                ),
                "Betydning for caset": (
                    "Ny geografisk referanse og kontrakt i kategorien Major (>200 MNOK). "
                    "Styrker vekstmulighetene i Midtøsten og Nord-Afrika."
                ),
                "Kilde": "Euronext / Cambi",
                "Lenke": "https://live.euronext.com/en/product/equities/NO0010078850-MERK/company-information",
            },
            {
                "Dato": "21.08.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "Grønn Vekst tildelt Eidsvoll-kontrakt",
                "Kort oppsummering": (
                    "Avtale for håndtering av biosolids fra Bårlidalen renseanlegg, "
                    "med tre faste år og opptil syv ettårige opsjoner."
                ),
                "Betydning for caset": (
                    "Ny tilbakevendende Solutions-inntekt og ytterligere styrking av "
                    "Grønn Veksts kommunale kontraktsportefølje."
                ),
                "Kilde": "Euronext / Cambi",
                "Lenke": "https://live.euronext.com/en/product/equities/NO0010078850-MERK/company-information",
            },
            {
                "Dato": "18.08.2026",
                "Kategori": "Resultat",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Q2 2026 – ordrebok opp til 1,479 mrd.",
                "Kort oppsummering": (
                    "Omsetning 264,9 MNOK, EBIT 20,7 MNOK, ordreinngang 554 MNOK "
                    "og operasjonell kontantstrøm 156,1 MNOK."
                ),
                "Betydning for caset": (
                    "Svakere resultat på kort sikt, men vesentlig bedre ordrebok og "
                    "sterk kontantstrøm fra prosjektmilepæler."
                ),
                "Kilde": "Cambi Investor Relations",
                "Lenke": "https://www.investors.cambi.com/results-and-reports",
            },
            {
                "Dato": "03.07.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "Ringsend – levetidsforlengelse av THP-anlegg",
                "Kort oppsummering": (
                    "Cambi skal modernisere kontrollsystemer og erstatte utstyr på "
                    "to eldre THP-linjer i Dublin."
                ),
                "Betydning for caset": (
                    "Viser verdien av den installerte basen og potensialet for service, "
                    "oppgraderinger og levetidsforlengelser."
                ),
                "Kilde": "Euronext / Cambi",
                "Lenke": "https://live.euronext.com/en/products/equities/company-news/2026-07-03-cambi-signs-small-contract-extending-operating-life-two",
            },
            {
                "Dato": "09.06.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Grønn Vekst beholder Bergen Vann-kontrakten",
                "Kort oppsummering": (
                    "Fem års fast avtale med tre ettårige opsjoner. Total potensiell "
                    "verdi er i Cambis Major-kategori, over 200 MNOK."
                ),
                "Betydning for caset": (
                    "Grønn Veksts største kontrakt noensinne og viktig bidrag til "
                    "langsiktig, tilbakevendende Solutions-backlog."
                ),
                "Kilde": "Euronext / Cambi",
                "Lenke": "https://live.euronext.com/en/products/equities/company-news/2026-06-09-gronn-vekst-retains-major-contract-municipal-biosolids",
            },
            {
                "Dato": "29.04.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Rosedale THP-prosjekt i Auckland",
                "Kort oppsummering": (
                    "Engineering-avtale for to THP-systemer. Total prosjektverdi er "
                    "klassifisert som Large (100–200 MNOK)."
                ),
                "Betydning for caset": (
                    "Strategisk viktig referanse i New Zealand med mulig produksjonsfase "
                    "etter senere notice to proceed."
                ),
                "Kilde": "Euronext / Cambi",
                "Lenke": "https://live.euronext.com/en/products/equities/company-news/2026-04-29-cambi-signs-contract-thp-rosedale-wastewater-treatment",
            },
        ],
        "upcoming_events": [
            {
                "Dato": "16.09.2026",
                "Hendelse": "Pareto Securities Energy Conference",
                "Sted": "Oslo, Norge",
                "Hvorfor følge": "Mulige oppdateringer om marked, pipeline og kapitalallokering."
            },
            {
                "Dato": "04.11.2026",
                "Hendelse": "Q3 2026",
                "Sted": "Investor relations",
                "Hvorfor følge": "Viktig for ordreinngang, backlog, Technology-margin og kontantstrøm."
            },
        ],
        "contracts": [
            {
                "Dato": "09.09.2026",
                "Segment": "Technology",
                "Kunde/prosjekt": "Alexandria West, Egypt – 4 THP-systemer",
                "Verdi (MNOK)": 200,
                "Kategori": "Major, 200+",
                "Status": "Signert / engineering",
                "Levering": "Produksjon etter notice to proceed",
            },
            {
                "Dato": "21.08.2026",
                "Segment": "Solutions",
                "Kunde/prosjekt": "Eidsvoll – biosolids management",
                "Verdi (MNOK)": 15,
                "Kategori": "Small, 15–50",
                "Status": "Tildelt",
                "Levering": "Oppstart 01.11.2026",
            },
            {
                "Dato": "03.07.2026",
                "Segment": "Technology / Services",
                "Kunde/prosjekt": "Ringsend, Dublin – levetidsforlengelse",
                "Verdi (MNOK)": 15,
                "Kategori": "Small, 15–50",
                "Status": "Signert",
                "Levering": "2027",
            },
            {
                "Dato": "09.06.2026",
                "Segment": "Solutions",
                "Kunde/prosjekt": "Bergen Vann – biosolids management",
                "Verdi (MNOK)": 200,
                "Kategori": "Major, 200+",
                "Status": "Tildelt / igangsatt",
                "Levering": "5 år + 3 opsjonsår",
            },
            {
                "Dato": "29.04.2026",
                "Segment": "Technology",
                "Kunde/prosjekt": "Rosedale, Auckland – 2 THP-systemer",
                "Verdi (MNOK)": 100,
                "Kategori": "Large, 100–200",
                "Status": "Engineering signert",
                "Levering": "Utstyr 2028 / drift 2030",
            },
            {
                "Dato": "07.04.2026",
                "Segment": "Technology",
                "Kunde/prosjekt": "Malad, Mumbai – 2 THP-systemer",
                "Verdi (MNOK)": 50,
                "Kategori": "Medium, 50–100",
                "Status": "Signert",
                "Levering": "2027",
            },
            {
                "Dato": "06.03.2026",
                "Segment": "Technology",
                "Kunde/prosjekt": "Blackburn bioresources hub, UK",
                "Verdi (MNOK)": 100,
                "Kategori": "Large, 100–200",
                "Status": "Signert",
                "Levering": "Sent 2027 / drift 2028",
            },
            {
                "Dato": "02.03.2026",
                "Segment": "Technology",
                "Kunde/prosjekt": "Ellesmere Port bioresources hub, UK",
                "Verdi (MNOK)": 100,
                "Kategori": "Large, 100–200",
                "Status": "Signert",
                "Levering": "Sent 2027 / drift 2028",
            },
        ],
        "contract_value_metric_label": "Minimum annonsert kontraktsverdi 2026",
        "contract_value_caption": (
            "Summen bruker nedre grense i Cambis annonserte verdikategorier. "
            "Faktisk kontraktsverdi er derfor høyere enn tallet som vises."
        ),
        "opportunities": [
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Clarkson WRRF – Peel Region, Ontario",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Aktivt anbud",
                "Neste dato": "02.10.2026",
                "Dato-type": "Tilbudsfrist",
                "Neste trigger": "Tilbudsfrist / deretter overvåke award-notice",
                "Sist oppdatert": "15.09.2026",
                "Sist kontrollert": "15.09.2026",
                "Kilde": "Region of Peel – 2026-005P",
                "Kommentar": (
                    "Region of Peel har lyst ut pre-purchase av Thermal Hydrolysis "
                    "Process-utstyr og hjelpekomponenter til Clarkson WRRF biosolids expansion. "
                    "Dette er en konkret THP-anskaffelse og derfor svært relevant for Cambi."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Beckton STW THP Upgrade – Thames Water",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Planlagt anskaffelse / overvåkes",
                "Neste dato": "01.12.2026",
                "Dato-type": "Indikativ kontraktstildeling",
                "Neste trigger": "Live tender notice / leverandørvalg / oppdatert Thames Water-pipeline",
                "Sist oppdatert": "16.09.2026",
                "Sist kontrollert": "16.09.2026",
                "Kilde": "Thames Water – S39830 / Find a Tender",
                "Kommentar": (
                    "Thames Water beskriver S39830 som en oppgradering med én ny THP-enhet "
                    "og oppgradering av eksisterende THP. Total indikativ prosjektverdi er "
                    "£130m eks. mva.; dette er totalprosjektet og ikke et verdiestimat for Cambi."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "West Central Bio-Resource / Daldowie – Scottish Water",
                "Segment": "Technology",
                "Sannsynlighet": "Høy",
                "Est. verdi (MNOK)": None,
                "Status": "Cambi teknologileverandør / designfase",
                "Neste dato": "04.2027",
                "Dato-type": "Planlagt byggestart",
                "Neste trigger": "Planleggingssøknad / Gate 80 / Phase 2 / Cambi-kontrakt",
                "Sist oppdatert": "16.09.2026",
                "Sist kontrollert": "16.09.2026",
                "Kilde": "Scottish Water / Find a Tender – SW25/CDC/1477",
                "Kommentar": (
                    "Scottish Water har valgt Daldowie som foretrukket lokasjon og beskriver "
                    "Cambi som designated technology provider i designfasen. Total prosjektverdi "
                    "er oppgitt til £265–415m; dette er totalprosjektet og ikke et verdiestimat "
                    "for Cambis leveranse."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Netheridge STW THP – Severn Trent",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Preliminary market engagement / avventer tender",
                "Neste dato": "Ikke offentlig",
                "Dato-type": "Neste procurement-steg",
                "Neste trigger": "UK4 tender notice / UK6 award / leverandørvalg",
                "Sist oppdatert": "16.09.2026",
                "Sist kontrollert": "16.09.2026",
                "Kilde": "Find a Tender 2025/S 000-022304 – OCID ocds-h6vhtk-051607",
                "Kommentar": (
                    "Severn Trent har gjennomført preliminary market engagement for levering, "
                    "installasjon og commissioning av et THP-system ved Netheridge STW. "
                    "Offentlig dokumentasjon angir levering tidlig 2027, installasjon innen "
                    "midten av 2027 og commissioning innen utgangen av 2027. "
                    "Ingen offentlig Cambi-tildeling er identifisert."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Roundhill STW THP – Severn Trent",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Planlagt AMP8 THP-anlegg / overvåkes",
                "Neste dato": "Ikke offentlig",
                "Dato-type": "Neste procurement-steg",
                "Neste trigger": "UK4 tender notice / planning / UK6 award / leverandørvalg",
                "Sist oppdatert": "16.09.2026",
                "Sist kontrollert": "16.09.2026",
                "Kilde": "Severn Trent PR24 – SVE4.34 Bioresources Botex+",
                "Kommentar": (
                    "Severn Trent opplyser i PR24-materialet at AMP8-planen inkluderer to nye "
                    "THP-anlegg ved Netheridge og Roundhill, samt utvidelser ved Wanlip og Derby. "
                    "Ingen offentlig Cambi-tildeling er identifisert."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Flere AMP8 THP-huber i Storbritannia",
                "Segment": "Technology",
                "Sannsynlighet": "Høy",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye AMP8-tildelinger / engineering-avtaler",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "UK er Cambis sterkeste nærmarked og AMP8-investeringene varer "
                    "frem mot 2030. Flere hub-prosjekter kan komme."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Rosedale – notice to proceed til produksjon",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Engineering pågår",
                "Neste trigger": "Notice to proceed fra Watercare",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Totalprosjektet er klassifisert som Large. Produksjon starter først "
                    "etter senere ordre om å gå videre."
                ),
            },
            {
                "Prioritet": "🟡 Middels–høy",
                "Mulighet": "Engineering-prosjekt i Sør-Amerika → full THP-leveranse",
                "Segment": "Technology",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Tidlig fase",
                "Neste trigger": "Full kontrakt / notice to proceed",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Cambi opplyste i Q1 at en engineering-avtale var inngått i "
                    "Sør-Amerika. En full leveranse vil være en ny viktig markedsreferanse."
                ),
            },
            {
                "Prioritet": "🟡 Middels–høy",
                "Mulighet": "Flere THP-prosjekter i India",
                "Segment": "Technology",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Aktiv markedsutvikling",
                "Neste trigger": "Nye indiske anbud / kontrakter",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Cambi bygger lokal organisasjon og produksjonskapasitet i India, "
                    "som kan forbedre konkurransekraft og skalerbarhet."
                ),
            },
            {
                "Prioritet": "🟡 Middels",
                "Mulighet": "Nye kommunale biosolidskontrakter i Norge",
                "Segment": "Solutions",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye offentlige anbud",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Bergen og Eidsvoll viser fortsatt etterspørsel etter Grønn Veksts "
                    "logistikk- og sluttbehandlingsløsninger."
                ),
            },
        ],
        "contract_watchlist": [
            "Clarkson WRRF / Peel Region: tilbudsfrist 02.10.2026 og deretter award-notice.",
            "Beckton S39830: overvåke live tender notice, leverandørvalg og endringer i indikativ tidsplan.",
            "Daldowie / West Central: planleggingssøknad, Gate 80, Phase 2 og eventuell Cambi-kontrakt.",
            "Netheridge: UK4 tender notice, UK6 award notice og leverandørvalg.",
            "Roundhill: UK4 tender notice, planlegging/tillatelser, UK6 award og leverandørvalg.",
            "Flere AMP8-prosjekter i Storbritannia.",
            "Notice to proceed for Rosedale i New Zealand og Alexandria i Egypt.",
            "Konvertering av Sør-Amerika-engineering til full kontrakt.",
            "Nye THP-anbud i India og andre fremvoksende markeder.",
            "Nye kommunale biosolids- og jordkontrakter for Grønn Vekst.",
        ],
        "valuation": {
            "reference_price": 24.4,
            "eps_2026": 0.65,
            "growth_bear": 30.0,
            "growth_base": 52.0,
            "growth_bull": 71.0,
            "pe_bear": 16.0,
            "pe_base": 20.0,
            "pe_bull": 24.0,
            "max_pe_underway": 40.0,
            "required_return": 10.0,
            "target_year": 2028,

            # Cambi bruker direkte estimater i stedet for CAGR fra et svakt 2026-år.
            "cambi_eps_2026_bear": 0.60,
            "cambi_eps_2026_base": 0.65,
            "cambi_eps_2026_bull": 0.70,

            "cambi_revenue_2027_bear": 1150.0,
            "cambi_revenue_2027_base": 1300.0,
            "cambi_revenue_2027_bull": 1450.0,
            "cambi_margin_2027_bear": 12.0,
            "cambi_margin_2027_base": 15.0,
            "cambi_margin_2027_bull": 17.0,
            "cambi_eps_2027_bear": 0.85,
            "cambi_eps_2027_base": 1.10,
            "cambi_eps_2027_bull": 1.35,

            "cambi_revenue_2028_bear": 1250.0,
            "cambi_revenue_2028_base": 1500.0,
            "cambi_revenue_2028_bull": 1750.0,
            "cambi_margin_2028_bear": 14.0,
            "cambi_margin_2028_base": 17.0,
            "cambi_margin_2028_bull": 20.0,
            "cambi_eps_2028_bear": 1.10,
            "cambi_eps_2028_base": 1.50,
            "cambi_eps_2028_bull": 1.90,

            "dcf_revenue_2026": 1000.0,
            "dcf_revenue_2030": 2400.0,
            "dcf_ebit_margin_2026": 12.0,
            "dcf_ebit_margin_2030": 20.0,
            "dcf_tax_rate": 22.0,
            "dcf_conversion": 80.0,
            "dcf_wacc": 10.0,
            "dcf_terminal_growth": 3.0,
            "note": (
                "Forutsetningene er arbeidsestimater og ikke konsensus. Cambis "
                "prosjektmiks og arbeidskapital gjør både EPS og FCF volatile fra år til år."
            )
        }
    },

    "Kitron": {
        "ticker": "KIT",
        "marked": "Oslo Børs",
        "sektor": "EMS / Elektronikk / Defence & Aerospace",
        "currency": "NOK",
        "financial_currency": "EUR",
        "cashflow_unit": "MEUR",
        "cashflow_fx_to_share_currency": 11.6,
        "valuation_fx_to_share_currency": 11.6,
        "case": (
            "Kitron er et skandinavisk EMS-selskap med produksjon i Europa, USA og Asia. "
            "Investeringscaset bygger på sterk strukturell vekst innen Defence & Aerospace, "
            "regionalisering av forsyningskjeder, høyere aktivitet innen elektrifisering og "
            "datasentre, samt bedre skala og kapitalutnyttelse. DeltaNordic/Kitron Eltech "
            "styrker forsvarsposisjonen ytterligere. Viktigste risikoer er komponentmangel, "
            "høyere verdsettelse etter sterk kursoppgang og gjennomføring av rask kapasitetsvekst."
        ),
        "price": 93.70,
        "price_date": "14.09.2026",
        "market_cap": 20.49,
        "eps_ltm": 3.61,
        "pe_ltm": 25.9,
        "fcf_ltm": 102.9,
        "fcf_yield": 5.6,
        "ocf_ltm": 114.3,
        "ocf_yield_ltm": 6.3,
        "roe_ltm": 23.8,
        "roce": 18.3,
        "nibd": 30.5,
        "nibd_ebitda": 0.29,
        "shares_outstanding": 218_702_471,
        "dashboard_5y": {
            "revenue_cagr": 14.4,
            "eps_cagr": 15.4,
            "fcf_yield_avg": 4.7,
            "ebit_margin_avg": 7.7,
        },
        "q2": {
            "revenue": 295.7,
            "growth": 71.7,
            "ebit": 28.3,
            "ebit_margin": 9.6,
            "eps": 0.10,
            "ocf": 47.1,
            "fcf": 41.3,
        },
        "q2_yoy": {
            "revenue": "+72% mot i fjor",
            "ocf": "+144% mot i fjor",
            "ebit_margin": "+0,9 pp mot i fjor",
            "ebit": "+89% mot i fjor",
            "eps": "+100% mot i fjor",
            "fcf": "+139% mot i fjor",
        },
        "h1": {
            "revenue": 568.4,
            "growth": 68.7,
            "ebit": 53.9,
            "ebit_margin": 9.5,
            "eps": 0.19,
            "ocf": 52.1,
            "fcf": -21.1,
        },
        "h1_yoy": {
            "revenue": "+69% mot i fjor",
            "ocf": "+66% mot i fjor",
            "ebit_margin": "+1,3 pp mot i fjor",
            "ebit": "+96% mot i fjor",
            "eps": "+111% mot i fjor",
            "fcf": "N/M – fra positiv til negativ",
        },
        "cashflow_note": (
            "H1 fri kontantstrøm er påvirket av oppkjøpet av DeltaNordic/Kitron Eltech. "
            "Operasjonell kontantstrøm var EUR 52,1m i H1 og EUR 47,1m i Q2. "
            "LTM FCF brukes som et mer representativt mål på løpende kontantgenerering."
        ),
        "financials": [
            {
                "Periode": "2024",
                "Omsetning": 647.2,
                "Vekst": "-17%",
                "EBIT": 48.0,
                "EBIT-margin": "7,4%",
                "EPS": 0.14,
            },
            {
                "Periode": "2025",
                "Omsetning": 738.3,
                "Vekst": "14%",
                "EBIT": 64.5,
                "EBIT-margin": "8,7%",
                "EPS": 0.22,
            },
            {
                "Periode": "Q1 2026",
                "Omsetning": 272.7,
                "Vekst": "66%",
                "EBIT": 25.6,
                "EBIT-margin": "9,4%",
                "EPS": 0.09,
            },
            {
                "Periode": "Q2 2026",
                "Omsetning": 295.7,
                "Vekst": "72%",
                "EBIT": 28.3,
                "EBIT-margin": "9,6%",
                "EPS": 0.10,
            },
            {
                "Periode": "H1 2026",
                "Omsetning": 568.4,
                "Vekst": "69%",
                "EBIT": 53.9,
                "EBIT-margin": "9,5%",
                "EPS": 0.19,
            },
        ],
        "segments_q2": [
            {
                "Segment": "Defence & Aerospace",
                "Omsetning Q2 (MEUR)": 154.2,
                "Vekst": "+234%",
                "Kommentar": "Klart største vekstmotor; missiler, luftvern, ubemannede systemer og forsvarselektronikk.",
            },
            {
                "Segment": "Electrification",
                "Omsetning Q2 (MEUR)": 47.2,
                "Vekst": "+7%",
                "Kommentar": "Støttes av kraftnett, power conversion og datasenterrelatert etterspørsel.",
            },
            {
                "Segment": "Industry",
                "Omsetning Q2 (MEUR)": 45.5,
                "Vekst": "+13%",
                "Kommentar": "Bedre ordreinngang; AI/datasenter trekker også gjennom underleverandørkjeden.",
            },
            {
                "Segment": "Connectivity",
                "Omsetning Q2 (MEUR)": 35.1,
                "Vekst": "+18%",
                "Kommentar": "Sensorer, IoT og 5G bidrar til ny vekstfase.",
            },
            {
                "Segment": "Medical Devices",
                "Omsetning Q2 (MEUR)": 13.7,
                "Vekst": "+15%",
                "Kommentar": "Bred vekst innen diagnostikk og avansert medisinsk utstyr.",
            },
        ],
        "order_kpis": {
            "Ordrebok Q2": "794 MEUR",
            "Ordreinngang Q2": "284 MEUR",
            "Defence backlog": "473 MEUR",
            "ROOC Q2": "39%",
        },
        "guidance": [
            "2026: Omsetning EUR 1,05–1,15 mrd.",
            "2026: EBIT EUR 97–112m.",
            "Guidingen ble oppjustert 24. august 2026 etter sterk etterspørsel og bedre komponentvisibilitet.",
            "Q3 2026 rapporteres 22. oktober 2026.",
            "Defence & Aerospace er den klart viktigste vekstmotoren.",
        ],
        "what_follow": [
            "Konvertering av ordrebok på EUR 794m til omsetning og resultat.",
            "EBIT-margin mot 10 % og videre skalaeffekter.",
            "Defence & Aerospace-backlog på EUR 473m og nye programvinn.",
            "Komponenttilgang i H2 og eventuell fortsatt oppjustering av guiding.",
            "Kontantstrøm, arbeidskapital og kapitaldisiplin etter DeltaNordic-oppkjøpet.",
            "Kapasitetsutnyttelse i Longum, Sverige og ny planlagt fabrikk i Horsens.",
        ],
        "latest_development": (
            "Kitron oppjusterte 2026-guidingen 24. august til EUR 1,05–1,15 mrd. "
            "i omsetning og EUR 97–112m i EBIT. Longum-fabrikken ble åpnet 25. august, "
            "og 1. september annonserte selskapet planer om ny fabrikk i Horsens, Danmark."
        ),
        "news_next_report": "22.10.2026",
        "news_auto_source": (
            "Neste automatiseringssteg blir å hente nye saker løpende fra Kitrons IR-side, "
            "NewsWeb og utvalgte eksterne kilder."
        ),
        "news": [
            {
                "Dato": "01.09.2026",
                "Kategori": "Kapasitet",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "Ny fabrikk planlegges i Horsens, Danmark",
                "Kort oppsummering": (
                    "Kitron planlegger en ny fabrikk for å møte forventet vekst og økt "
                    "etterspørsel etter lokal produksjon og industrialisering."
                ),
                "Betydning for caset": (
                    "Bekrefter høy etterspørsel og at selskapet investerer foran videre vekst."
                ),
                "Kilde": "Kitron Investor Relations",
                "Lenke": "https://www.kitron.com/",
            },
            {
                "Dato": "25.08.2026",
                "Kategori": "Kapasitet",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Longum-fabrikken åpnet",
                "Kort oppsummering": (
                    "Ny produksjonskapasitet utenfor Arendal er offisielt åpnet, "
                    "med særlig relevans for sterk forsvarsetterspørsel."
                ),
                "Betydning for caset": (
                    "Øker norsk kapasitet og reduserer risikoen for at produksjonskapasitet "
                    "blir en flaskehals i forsvarsveksten."
                ),
                "Kilde": "Kitron Investor Relations",
                "Lenke": "https://www.kitron.com/",
            },
            {
                "Dato": "24.08.2026",
                "Kategori": "Guiding",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "2026-guiding oppjustert",
                "Kort oppsummering": (
                    "Omsetningsguiding økt til EUR 1,05–1,15 mrd. og EBIT til EUR 97–112m."
                ),
                "Betydning for caset": (
                    "Sterkere etterspørsel og bedre forsyningskjedevisibilitet enn ved Q2."
                ),
                "Kilde": "Kitron Investor Relations",
                "Lenke": "https://www.kitron.com/",
            },
            {
                "Dato": "10.07.2026",
                "Kategori": "Resultat",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Q2 2026 – rekordresultat",
                "Kort oppsummering": (
                    "Omsetning EUR 295,7m (+72 %), EBIT EUR 28,3m og EBIT-margin 9,6 %. "
                    "Ordreboken steg 56 % til EUR 794,3m."
                ),
                "Betydning for caset": (
                    "Bekrefter kraftig resultatvekst, særlig innen Defence & Aerospace."
                ),
                "Kilde": "Kitron Q2 2026",
                "Lenke": "https://www.kitron.com/",
            },
            {
                "Dato": "09.04.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "EUR 42m Defence/Aerospace-ordre",
                "Kort oppsummering": (
                    "Produksjon og levering av systemer til en lagdelt forsvarsarkitektur. "
                    "Leveranser er planlagt i 2026."
                ),
                "Betydning for caset": (
                    "Synliggjør Kitrons direkte eksponering mot europeisk luftvern og forsvarsteknologi."
                ),
                "Kilde": "Kitron Investor Relations",
                "Lenke": "https://www.kitron.com/",
            },
        ],
        "upcoming_events": [
            {
                "Dato": "12–14.10.2026",
                "Hendelse": "AUSA 2026",
                "Sted": "Washington, USA",
                "Hvorfor følge": "Stor forsvarsmesse og relevant for nye Defence/Aerospace-kunder og programmer.",
            },
            {
                "Dato": "22.10.2026",
                "Hendelse": "Q3 2026",
                "Sted": "Investor relations",
                "Hvorfor følge": "Viktig test av oppjustert guiding, margin, ordrebok og komponenttilgang.",
            },
        ],
        "contracts": [
            {
                "Dato": "09.04.2026",
                "Segment": "Defence & Aerospace",
                "Kunde/prosjekt": "Layered defence architecture",
                "Verdi (MNOK)": 42,
                "Status": "Tildelt",
                "Levering": "2026",
            },
        ],
        "opportunities": [
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Nye Defence & Aerospace-programmer",
                "Segment": "Defence & Aerospace",
                "Sannsynlighet": "Høy",
                "Est. verdi (MNOK)": None,
                "Status": "Aktiv pipeline",
                "Neste trigger": "Nye programvinn / ordreannonseringer",
                "Sist oppdatert": "15.09.2026",
                "Kommentar": (
                    "Defence-backloggen er EUR 473m. Nye kunder og programmer inkluderer "
                    "autonomous defence, ruggedized edge computing og quantum security."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Videre skalering av nye forsvarsteknologikunder",
                "Segment": "Defence & Aerospace",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Ramping",
                "Neste trigger": "Konvertering fra utvikling/industrialisering til serieproduksjon",
                "Sist oppdatert": "15.09.2026",
                "Kommentar": (
                    "Kitron fikk syv nye 'new defence tech'-kunder i 2025, og flere programmer "
                    "er fortsatt i tidlige industrialiseringsfaser."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Datasenter og kraftinfrastruktur",
                "Segment": "Electrification / Industry",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Voksende etterspørsel",
                "Neste trigger": "Nye større ordre og videre kapasitetsutvidelser",
                "Sist oppdatert": "15.09.2026",
                "Kommentar": (
                    "AI-datasentre driver etterspørsel etter power infrastructure, "
                    "energistyring og avanserte industrielle systemer."
                ),
            },
            {
                "Prioritet": "🟡 Middels–høy",
                "Mulighet": "Connectivity / 5G og Industrial IoT",
                "Segment": "Connectivity",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Ny vekstfase",
                "Neste trigger": "Større programvinn eller backlog-vekst",
                "Sist oppdatert": "15.09.2026",
                "Kommentar": "Ny kundeaktivitet innen 5G, sensorer og AI-enabled industrial IoT.",
            },
            {
                "Prioritet": "🟡 Middels",
                "Mulighet": "Kitron Eltech / DeltaNordic kryssalg",
                "Segment": "Defence / Industry",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Integrasjon",
                "Neste trigger": "Nye felles kundeprogrammer",
                "Sist oppdatert": "15.09.2026",
                "Kommentar": (
                    "Oppkjøpet tilfører sterke relasjoner innen forsvar, mining og infrastruktur."
                ),
            },
        ],
        "contract_value_metric_label": "Kjent kontraktsverdi 2026",
        "contract_value_caption": (
            "Kjent verdi inkluderer den annonserte Defence/Aerospace-ordren på EUR 42m. "
            "Mange Kitron-programmer ligger under selskapets terskel for børsmelding og "
            "inngår derfor i ordrebok/pipeline uten separat offentlig kontraktsverdi."
        ),
        "contract_watchlist": [
            "Nye Defence & Aerospace-ordre knyttet til missiler, luftvern og ubemannede systemer.",
            "Konvertering av Defence-backlog på EUR 473m til produksjon.",
            "Nye programmer innen datasenter, power infrastructure og electrification.",
            "Kryssalg og nye ordre via Kitron Eltech/DeltaNordic.",
            "Kapasitetsutnyttelse i Longum, Sverige og planlagt Horsens-fabrikk.",
        ],
        "valuation": {
            "reference_price": 93.70,
            "eps_2026": 4.40,
            "growth_bear": 10.0,
            "growth_base": 20.0,
            "growth_bull": 25.0,
            "pe_bear": 15.0,
            "pe_base": 18.0,
            "pe_bull": 22.0,
            "required_return": 10.0,
            "target_year": 2028,
            "dcf_revenue_2026": 1100.0,
            "dcf_revenue_2030": 2000.0,
            "dcf_ebit_margin_2026": 9.5,
            "dcf_ebit_margin_2030": 12.0,
            "dcf_tax_rate": 20.6,
            "dcf_conversion": 80.0,
            "dcf_wacc": 9.5,
            "dcf_terminal_growth": 3.0,
            "note": (
                "Forutsetningene er arbeidsestimater, ikke konsensus. EPS 2026E er satt "
                "nær konsensus om lag EUR 0,38 per aksje omregnet til NOK. DCF-en beregnes "
                "i EUR og konverteres til NOK per aksje."
            ),
        },
    },

    "NOTE": {
        "ticker": "NOTE",
        "marked": "Nasdaq Stockholm",
        "sektor": "EMS / Elektronikk / Defence",
        "currency": "SEK",
        "case": (
            "NOTE er en europeisk EMS-partner som produserer avanserte PCBA-er, "
            "subassemblies og komplette box-build-løsninger. Investeringscaset bygger "
            "på regionalisering av elektronikkproduksjon, sterk vekst innen Security & "
            "Defence, økt kapasitet i Norden og Storbritannia, samt oppkjøpene av STI "
            "og Kasdon. NOTE har også fått en ny inngang mot AI-datasentre. De viktigste "
            "risikofaktorene er høyere gjeld etter STI-oppkjøpet, komponentmangel og "
            "svakere kontantstrøm når arbeidskapital bygges opp."
        ),
        "price": 181.00,
        "price_date": "11.09.2026",
        "market_cap": 5.17,
        "eps_ltm": 8.72,
        "pe_ltm": 20.8,
        "fcf_ltm": 183.4,
        "fcf_yield": 3.6,
        "ocf_ltm": 189.0,
        "ocf_yield_ltm": 3.7,
        "roe_ltm": 14.8,
        "roce": 13.1,
        "nibd": 1640.0,
        "nibd_ebitda": 3.3,
        "shares_outstanding": 28_550_000,
        "dashboard_5y": {
            "revenue_cagr": 15.3,
            "eps_cagr": 19.2,
            "fcf_yield_avg": 4.9,
            "ebit_margin_avg": 9.6,
        },
        "q2": {
            "revenue": 1175.0,
            "growth": 20.0,
            "ebit": 90.0,
            "ebit_margin": 7.7,
            "eps": 1.95,
            "ocf": -34.0,
            "fcf": -34.0,
        },
        "q2_yoy": {
            "revenue": "+20% mot i fjor",
            "ocf": "N/M – fra positiv til negativ",
            "ebit_margin": "-2,6 pp mot i fjor",
            "ebit": "-11% mot i fjor",
            "eps": "-26% mot i fjor",
            "fcf": "N/M – fra positiv til negativ",
        },
        "h1": {
            "revenue": 2137.0,
            "growth": 8.0,
            "ebit": 174.0,
            "ebit_margin": 8.1,
            "eps": 3.78,
            "ocf": 12.0,
            "fcf": -810.0,
        },
        "h1_yoy": {
            "revenue": "+8% mot i fjor",
            "ocf": "-95% mot i fjor",
            "ebit_margin": "-1,6 pp mot i fjor",
            "ebit": "-10% mot i fjor",
            "eps": "-23% mot i fjor",
            "fcf": "N/M – fra positiv til negativ",
        },
        "cashflow_note": (
            "H1 totalt kontantstrøm etter investeringer på -810 MSEK er kraftig påvirket "
            "av oppkjøpet av STI. Justert operasjonell kontantstrøm var +12 MSEK i H1. "
            "LTM operasjonell kontantstrøm er beregnet til ca. 189 MSEK."
        ),
        "financials": [
            {
                "Periode": "2024",
                "Omsetning": 3901.0,
                "Vekst": "-8%",
                "EBIT": 352.0,
                "EBIT-margin": "9,0%",
                "EPS": 8.61,
            },
            {
                "Periode": "2025",
                "Omsetning": 3814.0,
                "Vekst": "-2%",
                "EBIT": 381.0,
                "EBIT-margin": "10,0%",
                "EPS": 9.89,
            },
            {
                "Periode": "Q1 2026",
                "Omsetning": 962.0,
                "Vekst": "-4%",
                "EBIT": 84.0,
                "EBIT-margin": "8,7%",
                "EPS": 1.83,
            },
            {
                "Periode": "Q2 2026",
                "Omsetning": 1175.0,
                "Vekst": "20%",
                "EBIT": 90.0,
                "EBIT-margin": "7,7%",
                "EPS": 1.95,
            },
            {
                "Periode": "H1 2026",
                "Omsetning": 2137.0,
                "Vekst": "8%",
                "EBIT": 174.0,
                "EBIT-margin": "8,1%",
                "EPS": 3.78,
            },
        ],
        "segments_q2": [
            {
                "Segment": "Security & Defence",
                "Utvikling Q2": "Sterk vekst",
                "Kommentar": (
                    "STI og Kasdon bidrar betydelig, samtidig som NOTE rapporterer "
                    "god organisk vekst i segmentet."
                ),
            },
            {
                "Segment": "Industrial",
                "Utvikling Q2": "God vekst",
                "Kommentar": "Største kundesegment og positiv organisk utvikling.",
            },
            {
                "Segment": "Communications",
                "Utvikling Q2": "Bedring",
                "Kommentar": (
                    "Svært sterk ordrebok, men komponentmangel begrenser leveranser. "
                    "Ledelsen forventer vekst fra Q3."
                ),
            },
            {
                "Segment": "GreenTech",
                "Utvikling Q2": "Stabil / svak",
                "Kommentar": "Rundt 13 % av salget; foreløpig ingen tydelig veksttrend.",
            },
            {
                "Segment": "Medtech",
                "Utvikling Q2": "Svak",
                "Kommentar": (
                    "Lavere volumer fra største kunden, men sammenligningstallene "
                    "blir gradvis lettere fra Q3."
                ),
            },
        ],
        "order_kpis": {
            "Ordrebok inneværende år": "+11% YoY LFL",
            "Q2 omsetning": "1 175 MSEK",
            "Justert EBIT-margin Q2": "9,6%",
            "Egenkapitalandel Q2": "37%",
        },
        "guidance": [
            "2026: Driftsmargin forventes i intervallet 9,5–10,5 %.",
            "Andre halvår: gradvis økende organisk vekst, i tillegg til STI-volumer.",
            "STI ventes å bidra med om lag SEK 550–600m i resten av 2026.",
            "Selskapet forventer fortsatt sterk operasjonell kontantstrøm for helåret 2026.",
            "Ordreboken for inneværende år var 11 % høyere enn året før ved utgangen av Q2, like-for-like.",
        ],
        "what_follow": [
            "Organisk vekst i H2 2026 og hvor raskt Communications normaliseres.",
            "Utviklingen i underliggende EBIT-margin mot 9,5–10,5 %-målet.",
            "Security & Defence-vekst og nye programmer via STI og Kasdon.",
            "Arbeidskapital og bedring i operasjonell kontantstrøm i H2.",
            "Netto gjeld / EBITDA etter det store STI-oppkjøpet.",
            "Oppskalering av AI-datasenterkunden fra Q1 2027.",
        ],
        "latest_development": (
            "NOTE vant 3. september en Security & Defence-kontrakt på rundt 160 MSEK "
            "over tre år. Tidligere i sommer fikk selskapet en ny AI-datasenterkunde "
            "med potensial for en årlig omsetningsrate rundt 100 MSEK i 2028. "
            "Q2 ga rekordomsetning på 1 175 MSEK."
        ),
        "news_next_report": "23.10.2026",
        "news_auto_source": (
            "Neste automatiseringssteg blir å hente nye saker løpende fra NOTEs "
            "IR-side, Nasdaq Stockholm og utvalgte eksterne kilder."
        ),
        "news": [
            {
                "Dato": "03.09.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Security & Defence-kontrakt på ca. 160 MSEK",
                "Kort oppsummering": (
                    "Europeisk forsvarskunde har tildelt NOTE en avtale med estimert "
                    "ordeverdi på rundt 160 MSEK over tre år."
                ),
                "Betydning for caset": (
                    "Bekrefter den sterke etterspørselen innen europeisk forsvar og "
                    "styrker sannsynligheten for flere langsiktige produksjonsprogrammer."
                ),
                "Kilde": "NOTE Investor Relations",
                "Lenke": "https://www.note-ems.com/en/press-release/note-has-been-awarded-a-security-and-defence-contract-worth-approximately-sek-160-million/",
            },
            {
                "Dato": "15.07.2026",
                "Kategori": "Resultat",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Q2 2026 – rekordomsetning",
                "Kort oppsummering": (
                    "Omsetning 1 175 MSEK (+20 %), justert EBIT-margin 9,6 % og "
                    "EPS 1,95 SEK. Ordreboken for inneværende år var 11 % høyere YoY LFL."
                ),
                "Betydning for caset": (
                    "Oppkjøpene leverer som ventet, men svak kontantstrøm og "
                    "komponentmangel er viktige kortsiktige risikofaktorer."
                ),
                "Kilde": "NOTE Investor Relations",
                "Lenke": "https://www.note-ems.com/en/press-release/notes-to-the-interim-report-for-q2-2026-2/",
            },
            {
                "Dato": "08.07.2026",
                "Kategori": "Kontrakt",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Ny kunde innen AI-datasenterhardware",
                "Kort oppsummering": (
                    "Produksjon starter i Q1 2027 og kan nå en årlig omsetningsrate "
                    "på rundt 100 MSEK i 2028."
                ),
                "Betydning for caset": (
                    "Gir NOTE eksponering mot et nytt strukturelt vekstområde og "
                    "viser konkurransekraft innen avansert PCBA og box-build."
                ),
                "Kilde": "NOTE Investor Relations",
                "Lenke": "https://www.note-ems.com/en/press-release/note-wins-a-new-client-in-the-field-of-ai-data-centre-hardware/",
            },
            {
                "Dato": "27.05.2026",
                "Kategori": "Kapasitet",
                "Viktighet": "🟡 Relevant",
                "Hendelse": "Ny moderne fabrikk i Torsby åpnet",
                "Kort oppsummering": (
                    "Den nye fabrikken dobler produksjonskapasiteten i Torsby og "
                    "er tilpasset større og mer komplekse oppdrag."
                ),
                "Betydning for caset": (
                    "Øker kapasiteten for lokal europeisk produksjon, særlig relevant "
                    "for forsvar og andre kritiske sektorer."
                ),
                "Kilde": "NOTE Investor Relations",
                "Lenke": "https://www.note-ems.com/en/press-news/",
            },
            {
                "Dato": "20.03.2026",
                "Kategori": "M&A",
                "Viktighet": "🔴 Viktig",
                "Hendelse": "Oppkjøp av STI",
                "Kort oppsummering": (
                    "NOTE kjøpte britiske STI, en ledende EMS-partner for forsvarsindustrien. "
                    "STI ventes å omsette for rundt 750 MSEK i 2026."
                ),
                "Betydning for caset": (
                    "Transformativt oppkjøp som gjør NOTE til en større europeisk "
                    "underleverandør innen forsvar, men øker også gjelden betydelig."
                ),
                "Kilde": "NOTE Investor Relations",
                "Lenke": "https://www.note-ems.com/en/press-release/note-strengthens-its-defence-position-through-the-acquisition-of-sti-the-uks-leading-ems-partner-to-the-defence-industry-confirms-outlook-for-2026-and-provides-outlook-for-q1/",
            },
        ],
        "upcoming_events": [
            {
                "Dato": "23.10.2026",
                "Hendelse": "Q3 2026",
                "Sted": "Investor relations",
                "Hvorfor følge": (
                    "Viktig for organisk vekst i H2, arbeidskapital, cash flow, "
                    "STI-integrasjon og marginutvikling."
                ),
            },
            {
                "Dato": "Q1 2027",
                "Hendelse": "AI-datasenter – produksjonsstart",
                "Sted": "NOTE-produksjon",
                "Hvorfor følge": "Første produksjonsfase for den nye AI-datasenterkunden.",
            },
        ],
        "contracts": [
            {
                "Dato": "03.09.2026",
                "Segment": "Security & Defence",
                "Kunde/prosjekt": "Europeisk forsvarskunde",
                "Verdi (MNOK)": 160,
                "Status": "Tildelt",
                "Levering": "Over 3 år",
            },
            {
                "Dato": "08.07.2026",
                "Segment": "AI Data Centre",
                "Kunde/prosjekt": "Ny kunde – avansert datasenterhardware",
                "Verdi (MNOK)": None,
                "Status": "Avtale signert",
                "Levering": "Start Q1 2027; ~100 MSEK annualisert i 2028",
            },
        ],
        "opportunities": [
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Flere Security & Defence-produksjonsprogrammer",
                "Segment": "Security & Defence",
                "Sannsynlighet": "Høy",
                "Est. verdi (MNOK)": None,
                "Status": "Aktiv pipeline",
                "Neste trigger": "Nye industrialiseringsprosjekter konverteres til serieproduksjon",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "NOTE opplyser at flere utviklings- og industrialiseringsprosjekter "
                    "kan utvikle seg til langsiktige produksjonsprogrammer."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "AI-datasenter – høyere volum og nye produkter",
                "Segment": "AI Data Centre",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": 100,
                "Status": "Ramping planlagt",
                "Neste trigger": "Produksjonsstart Q1 2027 og volumøkning gjennom 2027",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Avtalen har potensial til rundt 100 MSEK i annualisert omsetning "
                    "i 2028 og kan bli større dersom kundens AI-infrastruktur vokser videre."
                ),
            },
            {
                "Prioritet": "🟢 Høy",
                "Mulighet": "Kryssalg via STI og Kasdon",
                "Segment": "Security & Defence",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Overvåkes",
                "Neste trigger": "Nye ordre fra eksisterende defence primes/OEM-er",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "STI tilfører relasjoner til store globale forsvarskunder på tvers "
                    "av luft, land, cyber og marine."
                ),
            },
            {
                "Prioritet": "🟡 Middels–høy",
                "Mulighet": "Communications – konvertering av sterk ordrebok",
                "Segment": "Communications",
                "Sannsynlighet": "Middels–høy",
                "Est. verdi (MNOK)": None,
                "Status": "Komponentbegrenset",
                "Neste trigger": "Bedre komponenttilgang og vekst fra Q3",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Ledelsen beskriver ordreboken som svært sterk. Bedre tilgang på "
                    "halvledere kan utløse utsatte leveranser."
                ),
            },
            {
                "Prioritet": "🟡 Middels",
                "Mulighet": "Større oppdrag gjennom Torsby-kapasiteten",
                "Segment": "Industrial / Defence",
                "Sannsynlighet": "Middels",
                "Est. verdi (MNOK)": None,
                "Status": "Kapasitet tilgjengelig",
                "Neste trigger": "Nye større og komplekse kundeprogrammer",
                "Sist oppdatert": "14.09.2026",
                "Kommentar": (
                    "Ny Torsby-fabrikk dobler produksjonskapasiteten og styrker lokal "
                    "produksjon for kunder med høye krav til forsyningssikkerhet."
                ),
            },
        ],
        "contract_value_metric_label": "Kjent kontraktsverdi 2026",
        "contract_value_caption": (
            "Den kjente verdien inkluderer forsvarskontrakten på ca. 160 MSEK. "
            "AI-datasenteravtalen har ikke oppgitt total kontraktsverdi; selskapet har "
            "kun oppgitt potensial for rundt 100 MSEK i annualisert omsetning i 2028."
        ),
        "contract_watchlist": [
            "Nye Security & Defence-programmer og konvertering fra industrialisering til serieproduksjon.",
            "AI-datasenterkunden: produksjonsstart Q1 2027 og volumramp gjennom 2027–2028.",
            "Nye ordre via STI og Kasdons etablerte forsvarskunder.",
            "Bedre komponenttilgang og realisering av Communications-ordreboken.",
            "Utnyttelse av den økte Torsby-kapasiteten.",
        ],
        "valuation": {
            "reference_price": 181.0,
            "eps_2026": 10.10,
            "growth_bear": 8.0,
            "growth_base": 20.0,
            "growth_bull": 25.0,
            "pe_bear": 15.0,
            "pe_base": 18.0,
            "pe_bull": 22.0,
            "required_return": 10.0,
            "target_year": 2028,
            "dcf_revenue_2026": 4630.0,
            "dcf_revenue_2030": 7500.0,
            "dcf_ebit_margin_2026": 10.0,
            "dcf_ebit_margin_2030": 11.5,
            "dcf_tax_rate": 20.6,
            "dcf_conversion": 80.0,
            "dcf_wacc": 9.5,
            "dcf_terminal_growth": 3.0,
            "note": (
                "Forutsetningene er arbeidsestimater og ikke konsensus. NOTE har "
                "høyere gjeld etter STI-oppkjøpet og kortsiktig svak cash conversion, "
                "mens Security & Defence og oppkjøpt vekst trekker i positiv retning."
            ),
        },
    },

    "Protector": {
        "ticker": "PROT",
        "marked": "Oslo Børs",
        "sektor": "Forsikring",
        "currency": "NOK",
        "case": (
            "Skadeforsikringsselskap med sterk historisk lønnsomhet, høy kapitalavkastning "
            "og en tydelig kostnads- og kvalitetsstrategi. Caset drives av disiplinert underwriting, "
            "vekst i UK og Norden, gradvis oppbygging i Frankrike og god kapitalallokering."
        ),
        "dashboard_5y": {
            "revenue_cagr": 20.7,
            "eps_cagr": 21.5,
            "fcf_yield_avg": None,
            "ebit_margin_avg": 20.8,
            "combined_ratio_avg": 87.2,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 25.34,
            "growth_bear": 5.0,
            "growth_base": 10.0,
            "growth_bull": 15.0,
            "pe_bear": 14.0,
            "pe_base": 18.0,
            "pe_bull": 21.0,
        },
        "protector": {
            "reference_price": 451.0,
            "reference_price_date": "16.09.2026",
            "q2": {
                "gwp": 4142,
                "insurance_revenue": 3698,
                "insurance_service_result": 684,
                "combined_ratio": 81.5,
                "investment_return": 365,
                "profit": 755,
                "eps": 9.0,
                "solvency": 221,
            },
            "q2_yoy": {
                "gwp": "-2% mot i fjor",
                "insurance_revenue": "+8% mot i fjor",
                "combined_ratio": "-3,4 pp mot i fjor",
                "investment_return": "-22% mot i fjor",
                "profit": "+4% mot i fjor",
                "eps": "+3% mot i fjor",
            },
            "h1": {
                "gwp": 10481,
                "insurance_service_result": 1243,
                "combined_ratio": 83.2,
                "investment_return": 134,
                "profit": 920,
                "eps": 10.8,
            },
            "h1_yoy": {
                "gwp": "+10% mot i fjor",
                "insurance_service_result": "+28% mot i fjor",
                "combined_ratio": "-2,2 pp mot i fjor",
                "investment_return": "-87% mot i fjor",
                "profit": "-38% mot i fjor",
                "eps": "-39% mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Premieinntekter": 12333,
                    "Combined ratio": 88.1,
                    "Investeringsresultat": 846,
                    "ROE": 31.6,
                    "EPS": 18.7,
                    "Solvens": 193,
                },
                {
                    "Periode": "2025",
                    "Premieinntekter": 14136,
                    "Combined ratio": 84.7,
                    "Investeringsresultat": 1575,
                    "ROE": 42.2,
                    "EPS": 31.7,
                    "Solvens": 219,
                },
            ],
            "targets": {
                "combined_ratio": "<91%",
                "roe": "≥20%",
            },
            "shareholders_date": "31.12.2025",
            "shareholders": [
                {"Aksjonær": "AWC AS", "Aksjer": 16625117, "Andel": 20.2},
                {"Aksjonær": "Stenshagen Invest AS", "Aksjer": 7526353, "Andel": 9.1},
                {"Aksjonær": "Citibank (Switzerland) AG", "Aksjer": 4456162, "Andel": 5.4},
                {"Aksjonær": "VPF Odin Norden", "Aksjer": 2926572, "Andel": 3.5},
                {"Aksjonær": "VPF Alfred Berg Gambak", "Aksjer": 1701873, "Andel": 2.1},
                {"Aksjonær": "Skandinaviska Enskilda Banken AB", "Aksjer": 1500000, "Andel": 1.8},
                {"Aksjonær": "MP Pensjon PK", "Aksjer": 1262553, "Andel": 1.5},
                {"Aksjonær": "State Street Bank and Trust Comp", "Aksjer": 1137660, "Andel": 1.4},
            ],
            "news": [
                {
                    "Dato": "09.07.2026",
                    "Hendelse": "Q2 2026 – combined ratio 81,5%",
                    "Oppsummering": (
                        "EPS 9,0 NOK, resultat 755 MNOK og investeringsavkastning inkl. "
                        "insurance finance 365 MNOK. Utbytte 3,00 NOK per aksje."
                    ),
                },
                {
                    "Dato": "22.04.2026",
                    "Hendelse": "Q1 2026 – combined ratio 84,9%",
                    "Oppsummering": (
                        "Premievekst 20%, EPS 1,8 NOK og solvensgrad 220%. "
                        "Styret besluttet utbytte på 8,00 NOK per aksje."
                    ),
                },
                {
                    "Dato": "18.03.2026",
                    "Hendelse": "Årsrapport 2025",
                    "Oppsummering": (
                        "ROE 42,2%, combined ratio 84,7% og investeringsavkastning 7,3%."
                    ),
                },
                {
                    "Dato": "28.01.2026",
                    "Hendelse": "2025-resultat",
                    "Oppsummering": (
                        "EPS 31,7 NOK, resultat 2 646 MNOK og premieinntekter 14 136 MNOK."
                    ),
                },
            ],
            "next_report": "21.10.2026",
            "buy_level": 420.0,
            "sell_level": 600.0,
            "max_pe_underway": 24.0,
        },
    },
    "B2 Impact": {
        "ticker": "B2I",
        "marked": "Oslo Børs",
        "sektor": "Finans / Inkasso",
        "case": (
            "Pan-europeisk gjeldsinvestor og forvalter. Caset bygger på høy kontantinnkreving, "
            "disiplinerte porteføljekjøp, fallende finansieringskostnader og økende EPS/utbytte "
            "med leverage under 2,5x."
        ),
        "dashboard_5y": {
            "revenue_cagr": 3.3,
            "eps_cagr": 4.5,
            "fcf_yield_avg": None,
            "ebit_margin_avg": 24.1,
        },
        "b2": {
            "reference_price": 23.35,
            "reference_price_date": "16.09.2026",
            "q2": {
                "cash_collections": 1665,
                "cash_ebitda": 1262,
                "adj_ebit": 494,
                "adj_net_profit": 246,
                "eps": 0.66,
                "collection_performance": 117,
                "investments": 1300,
                "erc": 28.9,
                "leverage": 2.1,
                "liquidity_eur": 320,
            },
            "q2_yoy": {
                "cash_collections": "+10% mot i fjor",
                "cash_ebitda": "+10% mot i fjor",
                "eps": "+20% mot i fjor",
                "adj_ebit": "+2% mot i fjor",
                "collection_performance": "+5 pp mot i fjor",
                "investments": "+189% mot i fjor",
            },
            "h1": {
                "cash_collections": 3055,
                "cash_ebitda": 2268,
                "adj_ebit": 957,
                "adj_net_profit": 454,
                "eps": 1.22,
            },
            "h1_yoy": {
                "cash_collections": "+7% mot i fjor",
                "cash_ebitda": "+7% mot i fjor",
                "eps": "+33% mot i fjor",
                "adj_ebit": "+12% mot i fjor",
                "adj_net_profit": "+35% mot i fjor",
                "leverage": "-0,3x mot i fjor",
            },
            "targets_2026": {
                "eps": 2.25,
                "roe": 16,
                "investments": 4.0,
                "leverage": 2.5,
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Cash collections": 5284,
                    "Cash EBITDA": 4175,
                    "Adj. EPS": 1.57,
                    "Investeringer": 2.5,
                    "ERC": 25.5,
                    "Leverage": 2.2,
                },
                {
                    "Periode": "2025",
                    "Cash collections": 6168,
                    "Cash EBITDA": 4727,
                    "Adj. EPS": 1.91,
                    "Investeringer": 3.7,
                    "ERC": 28.8,
                    "Leverage": 2.1,
                },
            ],
            "shareholders_date": "06.11.2025",
            "shareholders": [
                {"Aksjonær": "Nevedal Invest AS", "Aksjer": 89740738, "Andel": 24.27},
                {"Aksjonær": "Valset Invest AS", "Aksjer": 32003804, "Andel": 8.66},
                {"Aksjonær": "Stenshagen Invest AS", "Aksjer": 30500143, "Andel": 8.25},
                {"Aksjonær": "Rasmussengruppen AS", "Aksjer": 17373236, "Andel": 4.70},
                {"Aksjonær": "DNB Markets Aksjehandel/-analyse", "Aksjer": 16624479, "Andel": 4.50},
                {"Aksjonær": "Skandinaviska Enskilda Banken AB", "Aksjer": 13038856, "Andel": 3.53},
                {"Aksjonær": "RB Investor AS", "Aksjer": 8413680, "Andel": 2.28},
                {"Aksjonær": "Storebrand Norge", "Aksjer": 6958040, "Andel": 1.88},
            ],
            "news": [
                {
                    "Dato": "16.09.2026",
                    "Hendelse": "Ledelsen kjøper aksjer i sekundærplassering",
                    "Oppsummering": (
                        "CEO Trond Kristian Andreassen og CFO André Adolfsen kjøpte henholdsvis "
                        "23 000 og 23 114 aksjer til 23,35 NOK."
                    ),
                },
                {
                    "Dato": "20.08.2026",
                    "Hendelse": "Q2 2026 – EPS-målet løftes",
                    "Oppsummering": (
                        "Q2 adj. EPS 0,66, cash collections 1 665 MNOK og cash EBITDA 1 262 MNOK. "
                        "2026-målet ble løftet til minst 2,25 NOK EPS og rundt 16 % ROE."
                    ),
                },
                {
                    "Dato": "21.05.2026",
                    "Hendelse": "Q1 2026 – sterk EPS-vekst",
                    "Oppsummering": (
                        "Adj. EPS 0,56 mot 0,37 året før. Cash collections 1 390 MNOK og "
                        "cash EBITDA 1 006 MNOK."
                    ),
                },
                {
                    "Dato": "12.02.2026",
                    "Hendelse": "2025 – EPS 1,91 og utbytte 1,90",
                    "Oppsummering": (
                        "Cash collections 6 168 MNOK, cash EBITDA 4 727 MNOK og leverage 2,1x."
                    ),
                },
            ],
            "next_report": "05.11.2026",
            "valuation": {
                "eps_2026": 2.25,
                "growth_bear": 5.0,
                "growth_base": 14.0,
                "growth_bull": 20.0,
                "pe_bear": 8.0,
                "pe_base": 10.0,
                "pe_bull": 12.0,
                "buy_level": 21.0,
                "sell_level": 35.0,
                "max_pe_underway": 14.0,
            },
        },
    },
    "Byggmax": {
        "ticker": "BMAX",
        "marked": "Nasdaq Stockholm",
        "sektor": "Forbruksvarer / Byggevare",
        "currency": "SEK",
        "case": (
            "Nordisk lavpriskjede innen byggevare og gjør-det-selv. Caset bygger på en enkel "
            "lavkostmodell, sterk prisposisjon, gradvis normalisering i forbrukermarkedet og "
            "mulighet for høyere marginer når volumene bedres."
        ),
        "dashboard_5y": {
            "revenue_cagr": -2.1,
            "eps_cagr": -24.8,
            "fcf_yield_avg": 21.3,
            "ebit_margin_avg": 5.4,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 4.23,
            "growth_bear": 4.0,
            "growth_base": 11.0,
            "growth_bull": 16.0,
            "pe_bear": 10.0,
            "pe_base": 13.0,
            "pe_bull": 16.0,
        },
        "byggmax": {
            "reference_price": 53.80,
            "reference_price_date": "16.09.2026",
            "q2": {
                "revenue": 2263,
                "gross_margin": 35.1,
                "ebit": 267,
                "ebit_margin": 11.8,
                "eps": 3.42,
                "ocf": 564,
                "net_debt_ex_leases": 186,
                "net_debt_ebitda": 0.4,
            },
            "q2_yoy": {
                "revenue": "+2,9% mot i fjor",
                "gross_margin": "+0,9 pp mot i fjor",
                "ebit": "+20% mot i fjor",
                "ebit_margin": "+1,7 pp mot i fjor",
                "eps": "+24% mot i fjor",
                "ocf": "+1% mot i fjor",
                "net_debt": "-50% mot i fjor",
            },
            "h1": {
                "revenue": 3143,
                "gross_margin": 35.4,
                "ebit": 140,
                "ebit_margin": 4.5,
                "eps": 1.57,
                "ocf": 545,
                "net_profit": 92,
            },
            "h1_yoy": {
                "revenue": "+0,5% mot i fjor",
                "gross_margin": "+1,0 pp mot i fjor",
                "ebit": "+40% mot i fjor",
                "ebit_margin": "+1,3 pp mot i fjor",
                "eps": "+87% mot i fjor",
                "ocf": "+2% mot i fjor",
                "net_profit": "+84% mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning": 5986,
                    "EBIT": 177,
                    "EBIT-margin": 3.0,
                    "EPS": 1.14,
                    "OCF": 860,
                    "Nettogjeld eks. IFRS 16": 618,
                    "Utbytte": 0.75,
                },
                {
                    "Periode": "2025",
                    "Omsetning": 6133,
                    "EBIT": 306,
                    "EBIT-margin": 5.0,
                    "EPS": 3.25,
                    "OCF": 809,
                    "Nettogjeld eks. IFRS 16": 354,
                    "Utbytte": 1.65,
                },
            ],
            "targets": {
                "sales_growth": "Minst 5% p.a. over en konjunktursyklus",
                "ebita_margin": "Minst 7%",
                "dividend": "50% av nettoresultat",
                "leverage": "Maks 2,5x nettogjeld/EBITDA eks. IFRS 16",
            },
            "shareholders_date": "31.12.2025",
            "shareholders": [
                {"Aksjonær": "Avanza Pension", "Aksjer": 4116915, "Andel": 7.0},
                {"Aksjonær": "Nordea Funds AB", "Aksjer": 3875451, "Andel": 6.6},
                {"Aksjonær": "AAT Invest AS", "Aksjer": 2750000, "Andel": 4.7},
                {"Aksjonær": "Vevlen Kapital AS", "Aksjer": 2595000, "Andel": 4.4},
                {"Aksjonær": "Varner Equities AS", "Aksjer": 2072052, "Andel": 3.5},
                {"Aksjonær": "Brown Brothers Harriman/LUX", "Aksjer": 1933904, "Andel": 3.3},
                {"Aksjonær": "Norges Bank", "Aksjer": 1754244, "Andel": 3.0},
                {"Aksjonær": "Dimensional Fund Advisors", "Aksjer": 1749418, "Andel": 3.0},
                {"Aksjonær": "Bank of New York Mellon", "Aksjer": 1645244, "Andel": 2.8},
                {"Aksjonær": "Unionen", "Aksjer": 1340209, "Andel": 2.3},
            ],
            "news": [
                {
                    "Dato": "10.07.2026",
                    "Hendelse": "Q2 2026 – bedre lønnsomhet",
                    "Oppsummering": (
                        "Omsetning 2 263 MSEK, EBIT 267 MSEK og EPS 3,42. "
                        "EBIT-margin steg til 11,8% og nettogjeld eks. leasing falt til 186 MSEK."
                    ),
                },
                {
                    "Dato": "10.06.2026",
                    "Hendelse": "Byggmax gjenåpner i Stenungsund",
                    "Oppsummering": (
                        "Butikken i Stenungsund ble gjenåpnet som del av den løpende utviklingen "
                        "av butikkporteføljen."
                    ),
                },
                {
                    "Dato": "25.05.2026",
                    "Hendelse": "Økt bruk av AI i kundereisen",
                    "Oppsummering": (
                        "Byggmax utvider AI-bruk i kundeservice, salg og støtte til butikkansatte "
                        "for å øke effektivitet og kunderelevans."
                    ),
                },
                {
                    "Dato": "17.04.2026",
                    "Hendelse": "Q1 2026 – svak sesongstart",
                    "Oppsummering": (
                        "Omsetning 880 MSEK og EPS -1,85. Kaldt vær i februar påvirket salget, "
                        "mens nettogjelden ble redusert mot året før."
                    ),
                },
            ],
            "next_report": "20.10.2026",
            "buy_level": 48.0,
            "sell_level": 80.0,
            "max_pe_underway": 18.0,
        },
    },
    "Bakkafrost": {
        "ticker": "BAKKA",
        "marked": "Oslo Børs",
        "sektor": "Sjømat",
        "currency": "NOK",
        "case": (
            "Vertikalt integrert lakseoppdretter i Færøyene og Skottland. Caset drives av sterk "
            "biologi og kostnadsposisjon på Færøyene, større smolt, høyere fremtidige slaktevolumer "
            "og potensial for betydelig resultatforbedring når den skotske virksomheten normaliseres."
        ),
        "dashboard_5y": {
            "revenue_cagr": 8.5,
            "eps_cagr": -14.0,
            "fcf_yield_avg": 1.0,
            "ebit_margin_avg": 17.5,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 14.90,
            "growth_bear": 35.0,
            "growth_base": 66.0,
            "growth_bull": 80.0,
            "pe_bear": 12.0,
            "pe_base": 15.0,
            "pe_bull": 18.0,
        },
        "bakkafrost": {
            "reference_price": 434.80,
            "reference_price_date": "16.09.2026",
            "dkk_nok": 1.4432,
            "q2": {
                "harvest": 29894,
                "operational_ebit": 273,
                "ocf": 273,
                "fo_ebit_per_kg": 4.06,
                "sct_ebit_per_kg": -44.26,
                "smolt_transfer": 9.5,
                "fo_harvest": 26749,
                "sct_harvest": 3145,
            },
            "q2_yoy": {
                "harvest": "+30% mot i fjor",
                "operational_ebit": "+320% mot i fjor",
                "ocf": "klart forbedret mot i fjor",
                "fo_ebit_per_kg": "+3,82 DKK/kg mot i fjor",
                "sct_ebit_per_kg": "-26,13 DKK/kg mot i fjor",
                "smolt_transfer": "+48% mot i fjor",
            },
            "h1": {
                "harvest": 61231,
                "operational_ebit": 817,
                "fo_harvest": 51888,
                "sct_harvest": 9343,
                "smolt_transfer": 14.4,
                "fof_margin": 18.0,
            },
            "h1_yoy": {
                "harvest": "+27% mot i fjor",
                "operational_ebit": "+43% mot i fjor",
                "fo_harvest": "+49% mot i fjor",
                "sct_harvest": "-30% mot i fjor",
                "smolt_transfer": "+43% mot i fjor",
                "fof_margin": "+5,0 pp mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning": 7480,
                    "Operasjonell EBIT": 1550,
                    "Operasjonell EBIT-margin": 20.7,
                    "Slaktevolum": 90656,
                    "EPS DKK": 10.88,
                    "Utbytte DKK": 8.44,
                },
                {
                    "Periode": "2025",
                    "Omsetning": 7007,
                    "Operasjonell EBIT": 888,
                    "Operasjonell EBIT-margin": 12.7,
                    "Slaktevolum": 106823,
                    "EPS DKK": 8.83,
                    "Utbytte DKK": 3.45,
                },
            ],
            "targets": {
                "harvest_2026": "117 000 tonn",
                "smolt_fo": "20,0 mill. smolt",
                "smolt_sct": "10,0 mill. smolt",
                "dividend": "30–50% av EPS over tid",
            },
            "shareholders_date": "28.08.2026",
            "shareholders": [
                {"Aksjonær": "Johan Regin Jacobsen", "Aksjer": 4658608, "Andel": 7.84},
                {"Aksjonær": "Oddvør Marita Jacobsen", "Aksjer": 4594437, "Andel": 7.74},
                {"Aksjonær": "Folketrygdfondet", "Aksjer": 3966523, "Andel": 6.68},
                {"Aksjonær": "Alecta Tjänstepension", "Aksjer": 2400000, "Andel": 4.04},
                {"Aksjonær": "J.P. Morgan SE", "Aksjer": 2062071, "Andel": 3.47},
                {"Aksjonær": "Saxo Bank A/S", "Aksjer": 1939868, "Andel": 3.27},
                {"Aksjonær": "JPMorgan Chase Bank, London", "Aksjer": 1624697, "Andel": 2.74},
                {"Aksjonær": "Verdipapirfondet DNB Norge", "Aksjer": 1622385, "Andel": 2.73},
                {"Aksjonær": "State Street Bank and Trust", "Aksjer": 1488459, "Andel": 2.51},
                {"Aksjonær": "Skagen Vekst", "Aksjer": 1049315, "Andel": 1.77},
            ],
            "news": [
                {
                    "Dato": "31.08.2026",
                    "Hendelse": "Q2 2026 – sterk forbedring på Færøyene",
                    "Oppsummering": (
                        "Operasjonell EBIT 273 MDKK mot 65 MDKK året før. Slaktevolum 29 894 tonn, "
                        "sterk biologi på Færøyene og fortsatt svak lønnsomhet i Skottland."
                    ),
                },
                {
                    "Dato": "19.05.2026",
                    "Hendelse": "Q1 2026 – sterk start og økt guiding",
                    "Oppsummering": (
                        "Operasjonell EBIT 544 MDKK. Færøyene leverte rekordhøyt Q1-volum og "
                        "lavere produksjonskostnader."
                    ),
                },
                {
                    "Dato": "24.04.2026",
                    "Hendelse": "100% ASC-sertifisert",
                    "Oppsummering": (
                        "Alle Bakkafrosts lakseoppdrettsoperasjoner ble ASC-sertifisert."
                    ),
                },
                {
                    "Dato": "27.03.2026",
                    "Hendelse": "Årsrapport 2025",
                    "Oppsummering": (
                        "Omsetning 7,0 mrd. DKK, operasjonell EBIT 888 MDKK og slaktevolum "
                        "106 823 tonn."
                    ),
                },
            ],
            "next_report": "02.11.2026",
            "buy_level": 400.0,
            "sell_level": 600.0,
            "max_pe_underway": 22.0,
        },
    },
    "Nordic Semiconductor": {
        "ticker": "NOD",
        "marked": "Oslo Børs",
        "sektor": "Teknologi / Halvledere",
        "currency": "NOK",
        "case": (
            "Fabless halvlederselskap og global leder innen energieffektiv trådløs IoT. "
            "Caset drives av fortsatt Bluetooth-lederskap, nRF54-produktfamilien, sterk vekst "
            "innen cellular/satellitt, større programvare- og skytjenesteinnhold og betydelig "
            "operasjonell gearing når omsetningen skalerer."
        ),
        "dashboard_5y": {
            "revenue_cagr": 10.5,
            "eps_cagr": None,
            "fcf_yield_avg": 0.9,
            "ebit_margin_avg": 6.2,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 2.83,
            "growth_bear": 35.0,
            "growth_base": 55.0,
            "growth_bull": 70.0,
            "pe_bear": 25.0,
            "pe_base": 30.0,
            "pe_bull": 35.0,
        },
        "nordicsemi": {
            "reference_price": 171.0,
            "reference_price_date": "16.09.2026",
            "q2": {
                "revenue": 218.6,
                "gross_margin": 53.1,
                "adj_ebitda": 36.3,
                "adj_ebitda_margin": 16.6,
                "ebit": 22.3,
                "eps_usd": 0.083,
                "ocf": 15.3,
                "short_range": 199.8,
                "long_range": 14.6,
                "design_share": 28.0,
            },
            "q2_yoy": {
                "revenue": "+33% mot i fjor",
                "gross_margin": "+2,4 pp mot i fjor",
                "adj_ebitda": "+75% mot i fjor",
                "adj_ebitda_margin": "+3,9 pp mot i fjor",
                "ebit": "+95% mot i fjor",
                "eps_usd": "+57% mot i fjor",
                "ocf": "-67% mot i fjor",
                "short_range": "+30% mot i fjor",
                "long_range": "+94% mot i fjor",
            },
            "h1": {
                "revenue": 411.0,
                "gross_margin": 52.6,
                "adj_ebitda": 60.2,
                "adj_ebitda_margin": 14.6,
                "ebit": 32.4,
                "eps_usd": 0.137,
                "ocf": 16.2,
                "cash": 276.1,
                "employees": 1465,
            },
            "h1_yoy": {
                "revenue": "+29% mot i fjor",
                "gross_margin": "+2,5 pp mot i fjor",
                "adj_ebitda": "+69% mot i fjor",
                "adj_ebitda_margin": "+3,5 pp mot i fjor",
                "ebit": "+89% mot i fjor",
                "eps_usd": "+132% mot i fjor",
                "ocf": "-80% mot i fjor",
                "employees": "+10% mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning USDm": 511.4,
                    "Bruttomargin": 47.3,
                    "EBIT USDm": -45.8,
                    "EBIT-margin": -9.0,
                    "EPS USD": -0.200,
                    "OCF USDm": 60.4,
                    "Kontanter USDm": 287.9,
                },
                {
                    "Periode": "2025",
                    "Omsetning USDm": 667.6,
                    "Bruttomargin": 51.8,
                    "EBIT USDm": 23.2,
                    "EBIT-margin": 3.5,
                    "EPS USD": 0.085,
                    "OCF USDm": 115.7,
                    "Kontanter USDm": 307.4,
                },
            ],
            "targets": {
                "revenue_growth": ">20% gjennomsnittlig årlig vekst fra 2024 mot 2030",
                "gross_margin": ">50%",
                "ebitda_margin": "~25% langsiktig driftsmodell",
            },
            "shareholders_date": "31.12.2025",
            "shareholders": [
                {"Aksjonær": "Folketrygdfondet", "Aksjer": 24784246, "Andel": 12.4},
                {"Aksjonær": "Accelerator Ltd", "Aksjer": 17477950, "Andel": 8.7},
                {"Aksjonær": "DNB Asset Management AS", "Aksjer": 14647204, "Andel": 7.3},
                {"Aksjonær": "ODIN", "Aksjer": 7705486, "Andel": 3.9},
                {"Aksjonær": "Vanguard", "Aksjer": 6971293, "Andel": 3.5},
                {"Aksjonær": "Eika Kapitalforvaltning", "Aksjer": 5489760, "Andel": 2.7},
                {"Aksjonær": "KLP Kapitalforvaltning AS", "Aksjer": 5210642, "Andel": 2.6},
                {"Aksjonær": "Handelsbanken Fonder", "Aksjer": 4583455, "Andel": 2.3},
                {"Aksjonær": "BlackRock", "Aksjer": 4303035, "Andel": 2.2},
                {"Aksjonær": "Storebrand Asset Management", "Aksjer": 3267290, "Andel": 1.6},
                {"Aksjonær": "AAT Invest AS", "Aksjer": 2350000, "Andel": 1.2},
            ],
            "news": [
                {
                    "Dato": "15.09.2026",
                    "Hendelse": "Ny nRF54L multiprotokoll-SoC",
                    "Oppsummering": (
                        "Nordic utvidet nRF54L-serien med en ny løsning rettet mot "
                        "kostnads- og plassfølsomme IoT-produkter."
                    ),
                },
                {
                    "Dato": "21.08.2026",
                    "Hendelse": "nRF93M1 smart modem lanseres globalt",
                    "Oppsummering": (
                        "Pre-sertifisert Cat 1 bis-modem skal gjøre global cellular IoT "
                        "enklere å implementere."
                    ),
                },
                {
                    "Dato": "06.08.2026",
                    "Hendelse": "Q2 2026 – rekordomsetning",
                    "Oppsummering": (
                        "Omsetning 219 MUSD, +33%, bruttomargin 53,1% og justert EBITDA "
                        "36,3 MUSD. Q3-guiding 220–240 MUSD."
                    ),
                },
                {
                    "Dato": "06.08.2026",
                    "Hendelse": "nRF9151 utvider satellitt- og cellular IoT",
                    "Oppsummering": (
                        "Nordic fremhevet nRF9151 som plattform for nye globale "
                        "satellitt- og cellular IoT-applikasjoner."
                    ),
                },
            ],
            "next_report": "22.10.2026",
            "buy_level": 150.0,
            "sell_level": 240.0,
            "max_pe_underway": 50.0,
        },
    },
    "SATS": {
        "ticker": "SATS",
        "marked": "Oslo Børs",
        "sektor": "Forbruksvarer / Trening",
        "currency": "NOK",
        "case": (
            "Ledende nordisk treningskjede med høy andel gjentakende medlemsinntekter. "
            "Caset drives av medlemsvekst, høyere ARPM, økt aktivitet og kapasitetsutnyttelse "
            "i eksisterende klubber, kombinert med sterk operasjonell gearing, kontantstrøm "
            "og disiplinert klubbekspansjon."
        ),
        "dashboard_5y": {
            "revenue_cagr": 9.3,
            "eps_cagr": None,
            "fcf_yield_avg": 34.4,
            "ebit_margin_avg": 7.5,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 2.88,
            "growth_bear": 12.0,
            "growth_base": 20.0,
            "growth_bull": 28.0,
            "pe_bear": 13.0,
            "pe_base": 16.0,
            "pe_bull": 19.0,
        },
        "sats": {
            "reference_price": 44.35,
            "reference_price_date": "16.09.2026",
            "q2": {
                "revenue": 1442,
                "members": 744,
                "arpm": 635,
                "ebitda_pre_ifrs16": 313,
                "ebitda_margin": 22.0,
                "ebit_pre_ifrs16": 260,
                "ebit_margin": 18.0,
                "eps": 1.00,
                "ocf": 203,
                "fcf": 100,
                "leverage": 1.1,
                "clubs": 270,
                "workouts_growth": 3.0,
            },
            "q2_yoy": {
                "revenue": "+3% mot i fjor",
                "members": "+1% mot i fjor",
                "arpm": "+2% mot i fjor",
                "ebitda_pre_ifrs16": "+16% mot i fjor",
                "ebit_pre_ifrs16": "+21% mot i fjor",
                "eps": "+25% mot i fjor",
                "ocf": "+58% mot i fjor",
                "fcf": "+164% mot i fjor",
            },
            "h1": {
                "revenue": 2925,
                "members": 744,
                "arpm": 650,
                "ebitda_pre_ifrs16": 530,
                "ebitda_margin": 18.0,
                "ebit_pre_ifrs16": 477,
                "ebit_margin": 16.0,
                "eps": 1.53,
                "ocf": 381,
                "fcf": 236,
                "leverage": 1.1,
            },
            "h1_yoy": {
                "revenue": "+5% mot i fjor",
                "members": "+1% mot i fjor",
                "arpm": "+3% mot i fjor",
                "ebitda_pre_ifrs16": "+16% mot i fjor",
                "ebit_pre_ifrs16": "+19% mot i fjor",
                "eps": "+22% mot i fjor",
                "ocf": "+54% mot i fjor",
                "fcf": "+72% mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning": 5064,
                    "EBITDA før IFRS 16": 738,
                    "EBIT før IFRS 16": 526,
                    "EPS": 1.59,
                    "OCF": 509,
                    "FCF": 405,
                    "Medlemmer": 733,
                    "ARPM": 576,
                    "Leverage": 1.4,
                },
                {
                    "Periode": "2025",
                    "Omsetning": 5509,
                    "EBITDA før IFRS 16": 871,
                    "EBIT før IFRS 16": 652,
                    "EPS": 2.35,
                    "OCF": 642,
                    "FCF": 506,
                    "Medlemmer": 755,
                    "ARPM": 617,
                    "Leverage": 1.1,
                },
            ],
            "targets": {
                "club_openings": "8–12 nye klubber årlig",
                "signed_clubs": "13 signerte klubber frem til og med 2028",
                "ebitda_ambition": "1,1 mrd. NOK EBITDA før IFRS 16 på mellomlang sikt",
                "distribution": "Minst 50% av nettoresultat via utbytte og/eller tilbakekjøp",
            },
            "shareholders_date": "15.09.2026",
            "shareholders": [
                {"Aksjonær": "Folketrygdfondet", "Aksjer": 14348765, "Andel": 7.19},
                {"Aksjonær": "DNB Asset Management AS", "Aksjer": 12107429, "Andel": 6.06},
                {"Aksjonær": "Nordea Investment Management AB", "Aksjer": 11721985, "Andel": 5.87},
                {"Aksjonær": "JPMorgan Asset Management (UK) Ltd.", "Aksjer": 10961691, "Andel": 5.49},
                {"Aksjonær": "Fondsfinans Kapitalforvaltning AS", "Aksjer": 8408083, "Andel": 4.21},
                {"Aksjonær": "Alfred Berg Kapitalforvaltning AS", "Aksjer": 8105288, "Andel": 4.06},
            ],
            "news": [
                {
                    "Dato": "02.09.2026",
                    "Hendelse": "Kapitalnedsettelse etter tilbakekjøp fullført",
                    "Oppsummering": (
                        "SATS fullførte reduksjon av aksjekapitalen knyttet til tidligere "
                        "tilbakekjøpte aksjer."
                    ),
                },
                {
                    "Dato": "24.08.2026",
                    "Hendelse": "Aksjen handles ex. utbytte 0,72 NOK",
                    "Oppsummering": (
                        "H1-utbyttet på 0,72 NOK per aksje ble gjennomført etter Q2-resultatet."
                    ),
                },
                {
                    "Dato": "14.08.2026",
                    "Hendelse": "Q2 2026 – sterk marginutvikling",
                    "Oppsummering": (
                        "Omsetning 1 442 MNOK, EBITDA før IFRS 16 313 MNOK, EBIT før IFRS 16 "
                        "260 MNOK og EPS 1,00. FCF steg til 100 MNOK."
                    ),
                },
                {
                    "Dato": "14.08.2026",
                    "Hendelse": "Nytt tilbakekjøpsprogram",
                    "Oppsummering": (
                        "Styret initierte et nytt tilbakekjøpsprogram parallelt med fortsatt "
                        "utbytte og investeringer i vekst."
                    ),
                },
            ],
            "next_report": "28.10.2026",
            "buy_level": 40.0,
            "sell_level": 65.0,
            "max_pe_underway": 22.0,
        },
    },
    "Vend": {
        "ticker": "VEND",
        "marked": "Oslo Børs",
        "sektor": "Kommunikasjon / Markedsplasser",
        "currency": "NOK",
        "case": (
            "Ledende nordisk markedsplasselskap innen Mobility, Real Estate, Jobs og "
            "Recommerce. Caset drives av sterk markedsposisjon, pris/ARPA, skalering av "
            "felles teknologiplattform, kostnadsreduksjoner, høy kontantgenerering og "
            "kapitalallokering. Adevinta-eierandelen gir i tillegg en betydelig separat verdi."
        ),
        "dashboard_5y": {
            "revenue_cagr": None,
            "eps_cagr": None,
            "fcf_yield_avg": 1.8,
            "ebit_margin_avg": 14.7,
        },
        "valuation": {
            "target_year": 2028,
            "adj_eps_2026": 7.00,
            "growth_bear": 10.0,
            "growth_base": 25.0,
            "growth_bull": 35.0,
            "pe_bear": 18.0,
            "pe_base": 22.0,
            "pe_bull": 26.0,
        },
        "vend": {
            "reference_price": 234.00,
            "reference_price_date": "16.09.2026",
            "q2": {
                "revenue": 1696,
                "ebitda": 674,
                "ebitda_margin": 40.0,
                "adj_eps": 1.99,
                "ocf": 517,
                "fcf": 405,
                "recommerce_revenue": 237,
                "recommerce_ebitda": -33,
                "real_estate_ebitda": 248,
                "adevinta_value": 7200,
            },
            "q2_yoy": {
                "revenue": "0% mot i fjor",
                "ebitda": "+16% mot i fjor",
                "ebitda_margin": "+6 pp mot i fjor",
                "adj_eps": "+14% mot i fjor",
                "ocf": "+65% mot i fjor",
                "fcf": "+148% mot i fjor",
                "recommerce_revenue": "+21% i konstant valuta",
                "recommerce_ebitda": "+23 MNOK mot i fjor",
            },
            "h1": {
                "revenue": 3239,
                "ebitda": 1237,
                "ebitda_margin": 38.0,
                "adj_eps": 3.47,
                "ocf": 1003,
                "fcf": 758,
                "net_cash": 1978,
                "adevinta_value": 7200,
            },
            "h1_yoy": {
                "revenue": "+1% mot i fjor",
                "ebitda": "+24% mot i fjor",
                "ebitda_margin": "+7 pp mot i fjor",
                "adj_eps": "+30% mot i fjor",
                "ocf": "+77% mot i fjor",
                "fcf": "+181% mot i fjor",
                "net_cash": "fra 433 MNOK nettogjeld",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning": 6385,
                    "EBITDA": 1632,
                    "EBITDA-margin": 25.6,
                    "FCF": 668,
                    "Utbytte": 2.25,
                },
                {
                    "Periode": "2025",
                    "Omsetning": 6317,
                    "EBITDA": 2127,
                    "EBITDA-margin": 33.7,
                    "FCF": 1245,
                    "Utbytte": 2.50,
                },
            ],
            "targets": {
                "opex_2026": "~150 MNOK lavere enn 2025, eks. COGS",
                "buyback": "Inntil 4,0 mrd. NOK i 2026-programmet",
                "adevinta": "14% eierandel",
                "platform": "Bilbasen-migrering planlagt i 2027",
            },
            "shareholders_date": "31.12.2025",
            "shareholders": [
                {"Aksjonær": "Blommenholm Industrier AS", "Aksjer": 43167130, "Andel": 19.8},
                {"Aksjonær": "Folketrygdfondet", "Aksjer": 20761135, "Andel": 9.5},
                {"Aksjonær": "DNB Asset Management AS", "Aksjer": 10540306, "Andel": 4.8},
                {"Aksjonær": "HMI Capital Management, L.P.", "Aksjer": 7048045, "Andel": 3.2},
                {"Aksjonær": "The Vanguard Group, Inc.", "Aksjer": 6158171, "Andel": 2.8},
                {"Aksjonær": "Storebrand Kapitalforvaltning AS", "Aksjer": 5580930, "Andel": 2.6},
                {"Aksjonær": "KLP Kapitalforvaltning AS", "Aksjer": 5245779, "Andel": 2.4},
                {"Aksjonær": "ODIN Forvaltning AS", "Aksjer": 4568378, "Andel": 2.1},
                {"Aksjonær": "Novo Holdings A/S", "Aksjer": 4056053, "Andel": 1.9},
                {"Aksjonær": "BlackRock Institutional Trust", "Aksjer": 3949780, "Andel": 1.8},
            ],
            "news": [
                {
                    "Dato": "14.09.2026",
                    "Hendelse": "Q3 pre-silent newsletter",
                    "Oppsummering": (
                        "Vend publiserte oppdaterte volumtrender for juli–august foran Q3. "
                        "Q3-rapporten publiseres 27. oktober."
                    ),
                },
                {
                    "Dato": "14.09.2026",
                    "Hendelse": "Andre tilbakekjøpstransje fortsetter",
                    "Oppsummering": (
                        "513,6 MNOK var kjøpt tilbake i andre transje per 11. september. "
                        "Første transje på 2,0 mrd. NOK ble fullført i august."
                    ),
                },
                {
                    "Dato": "17.07.2026",
                    "Hendelse": "Q2 2026 – marginløft",
                    "Oppsummering": (
                        "Omsetning 1 696 MNOK, EBITDA 674 MNOK og EBITDA-margin 40%. "
                        "Real Estate og Recommerce var viktige drivere."
                    ),
                },
                {
                    "Dato": "17.07.2026",
                    "Hendelse": "Adevinta-verdi 7,2 mrd. NOK",
                    "Oppsummering": (
                        "Verdsettelsen av Vends 14% eierandel i Adevinta var bredt uendret."
                    ),
                },
            ],
            "next_report": "27.10.2026",
            "adevinta_per_share": 36.0,
            "buy_level": 210.0,
            "sell_level": 320.0,
            "max_pe_underway": 28.0,
        },
    },
    "Selvaag Bolig": {
        "ticker": "SBO",
        "marked": "Oslo Børs",
        "sektor": "Eiendom / Boligutvikling",
        "currency": "NOK",
        "case": (
            "Boligutvikler med sterk posisjon i Stor-Oslo og prosjekter også i Bergen, "
            "Stavanger og Stockholm. Caset drives av boligsalg, prosjektmarginer, "
            "igangsettinger og overleveringer, kombinert med en stor prosjekt- og tomtebank. "
            "Rentenivå, byggekostnader og kapitalbinding er de viktigste eksterne driverne."
        ),
        "dashboard_5y": {
            "revenue_cagr": -5.0,
            "eps_cagr": -28.4,
            "fcf_yield_avg": 2.7,
            "ebit_margin_avg": 9.3,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 2.73,
            "growth_bear": -5.0,
            "growth_base": 10.0,
            "growth_bull": 20.0,
            "pe_bear": 9.0,
            "pe_base": 11.0,
            "pe_bull": 13.0,
        },
        "selvaag": {
            "reference_price": 32.80,
            "reference_price_date": "16.09.2026",
            "q2": {
                "revenue": 1451,
                "adj_ebitda": 255,
                "adj_ebitda_margin": 17.6,
                "eps": 0.95,
                "units_sold": 172,
                "sales_value": 1373,
                "units_delivered": 187,
                "construction_starts": 290,
                "under_construction": 1126,
                "backlog_value": 8056,
                "sold_share": 61.0,
                "equity_ratio": 31.2,
                "ocf": 76,
                "net_interest_debt": 3871,
            },
            "q2_yoy": {
                "revenue": "+455% mot i fjor",
                "adj_ebitda": "+240 MNOK mot i fjor",
                "adj_ebitda_margin": "+12,0 pp mot i fjor",
                "eps": "fra 0,02 i fjor",
                "units_sold": "+62% mot i fjor",
                "sales_value": "+99% mot i fjor",
                "units_delivered": "+368% mot i fjor",
                "construction_starts": "+70% mot i fjor",
                "under_construction": "-3% mot i fjor",
                "backlog_value": "-2% mot i fjor",
                "ocf": "+422 MNOK mot i fjor",
            },
            "h1": {
                "revenue": 1574,
                "adj_ebitda": 238,
                "adj_ebitda_margin": 15.1,
                "eps": 0.75,
                "units_sold": 530,
                "units_delivered": 211,
                "construction_starts": 456,
                "ocf": -917,
                "net_income": 70,
            },
            "h1_yoy": {
                "revenue": "+267% mot i fjor",
                "adj_ebitda": "fra -5 MNOK i fjor",
                "adj_ebitda_margin": "+16,2 pp mot i fjor",
                "eps": "fra -0,20 i fjor",
                "units_sold": "+93% mot i fjor",
                "units_delivered": "+185% mot i fjor",
                "construction_starts": "+29% mot i fjor",
                "ocf": "+523 MNOK mot i fjor",
                "net_income": "fra -19 MNOK i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Omsetning": 1971,
                    "EBIT": 198,
                    "EBIT-margin": 10.1,
                    "EPS": 1.90,
                    "Solgte boliger": 568,
                    "Overleverte boliger": 532,
                    "Under bygging": 829,
                    "Tomtebank": 10000,
                    "Utbytte": 1.25,
                },
                {
                    "Periode": "2025",
                    "Omsetning": 2087,
                    "EBIT": 127,
                    "EBIT-margin": 6.1,
                    "EPS": 1.42,
                    "Solgte boliger": 466,
                    "Overleverte boliger": 433,
                    "Under bygging": 912,
                    "Tomtebank": 10400,
                    "Utbytte": 1.00,
                },
            ],
            "targets": {
                "project_margin": "Minst 10%",
                "dividend": "Minimum 60% av nettoresultat over tid",
                "construction_rule": "Normalt byggestart ved ca. 60% forhåndssalg",
                "completion_2026": "688 enheter forventet ferdigstilt i 2026",
            },
            "shareholders_date": "30.06.2026",
            "shareholders": [
                {"Aksjonær": "Selvaag AS", "Aksjer": 50180087, "Andel": 53.5},
                {"Aksjonær": "Skandinaviska Enskilda Banken AB", "Aksjer": 5782973, "Andel": 6.2},
                {"Aksjonær": "Perestroika AS", "Aksjer": 3848312, "Andel": 4.1},
                {"Aksjonær": "Verdipapirfondet Alfred Berg Gamba", "Aksjer": 2706726, "Andel": 2.9},
                {"Aksjonær": "The Northern Trust Comp, London Br", "Aksjer": 2149100, "Andel": 2.3},
                {"Aksjonær": "EGD Capital AS", "Aksjer": 1804471, "Andel": 1.9},
                {"Aksjonær": "Sanden Equity AS", "Aksjer": 1760000, "Andel": 1.9},
                {"Aksjonær": "Hausta Investor AS", "Aksjer": 1553557, "Andel": 1.7},
                {"Aksjonær": "Mustad Industrier AS", "Aksjer": 1067454, "Andel": 1.1},
                {"Aksjonær": "Brown Brothers Harriman & Co.", "Aksjer": 684331, "Andel": 0.7},
            ],
            "news": [
                {
                    "Dato": "06.08.2026",
                    "Hendelse": "Q2 2026 – rekordsalg og god lønnsomhet",
                    "Oppsummering": (
                        "172 boliger solgt for 1,37 mrd. NOK, 187 boliger overlevert og "
                        "justert EBITDA 255 MNOK. Ordrebok/prosjektverdi under bygging 8,1 mrd. NOK."
                    ),
                },
                {
                    "Dato": "01.07.2026",
                    "Hendelse": "Rekordhøyt boligsalg i første halvår",
                    "Oppsummering": (
                        "H1 endte med 530 netto solgte boliger etter et svært sterkt første kvartal."
                    ),
                },
                {
                    "Dato": "06.08.2026",
                    "Hendelse": "Utbytte for H1 utsatt",
                    "Oppsummering": (
                        "Styret besluttet å ikke betale halvårsutbytte nå. Samlet utbytte for 2026 "
                        "vurderes ved årsresultatet i februar 2027."
                    ),
                },
                {
                    "Dato": "06.08.2026",
                    "Hendelse": "Høy byggeaktivitet",
                    "Oppsummering": (
                        "1 126 boliger var under bygging ved utgangen av Q2. "
                        "61% var solgt, og 688 enheter ventes ferdigstilt i 2026."
                    ),
                },
            ],
            "next_report": "05.11.2026",
            "buy_level": 30.0,
            "sell_level": 42.0,
            "max_pe_underway": 14.0,
        },
    },

    "Storebrand": {
        "ticker": "STB",
        "marked": "Oslo Børs",
        "sektor": "Finans / Sparing / Forsikring",
        "currency": "NOK",
        "case": (
            "Ledende nordisk spare- og forsikringskonsern med sterke posisjoner innen "
            "tjenestepensjon, kapitalforvaltning, skadeforsikring og bank. Caset drives av "
            "vekst i kapital under forvaltning, lønnsom forsikringsvekst, bedre kapitalavkastning "
            "og betydelig kapitaldistribusjon gjennom stigende utbytter og tilbakekjøp."
        ),
        "dashboard_5y": {
            "revenue_cagr": 10.8,   # AUM CAGR 2020-2025
            "eps_cagr": None,
            "fcf_yield_avg": None,
            "ebit_margin_avg": None,
        },
        "valuation": {
            "target_year": 2028,
            "eps_2026": 11.49,
            "growth_bear": 7.0,
            "growth_base": 12.0,
            "growth_bull": 15.0,
            "pe_bear": 12.0,
            "pe_base": 15.0,
            "pe_bull": 18.0,
        },
        "storebrand": {
            "reference_price": 200.20,
            "reference_price_date": "16.09.2026",
            "q2": {
                "group_profit": 1799,
                "operating_profit": 1119,
                "cash_eps": 3.43,
                "insurance_result": 889,
                "combined_ratio": 86.7,
                "aum": 1658,
                "roe_ltm": 16.0,
                "solvency": 200.0,
                "fee_income": 2031,
                "portfolio_premiums": 11.1,
            },
            "q2_yoy": {
                "group_profit": "+26% mot i fjor",
                "operating_profit": "+17% mot i fjor",
                "cash_eps": "+20% mot i fjor",
                "insurance_result": "+40% mot i fjor",
                "combined_ratio": "-4,7 pp mot i fjor",
                "aum": "+10% mot i fjor",
                "fee_income": "-2% mot i fjor",
                "portfolio_premiums": "+12% mot i fjor",
            },
            "h1": {
                "group_profit": 3152,
                "operating_profit": 2145,
                "cash_eps": 5.53,
                "insurance_result": 1554,
                "combined_ratio": 90.0,
                "fee_income": 4128,
                "cash_after_tax": 2205,
            },
            "h1_yoy": {
                "group_profit": "+22% mot i fjor",
                "operating_profit": "+22% mot i fjor",
                "cash_eps": "+5% mot i fjor",
                "insurance_result": "+41% mot i fjor",
                "combined_ratio": "-4 pp mot i fjor",
                "fee_income": "+1% mot i fjor",
                "cash_after_tax": "+3% mot i fjor",
            },
            "annual": [
                {
                    "Periode": "2024",
                    "Konsernresultat": 5904,
                    "Driftsresultat": 3153,
                    "Cash EPS": 11.47,
                    "Cash ROE": 18.4,
                    "Solvens II": 200,
                    "AUM mrd.": 1469,
                    "Combined ratio": 97,
                    "Utbytte": 4.70,
                },
                {
                    "Periode": "2025",
                    "Konsernresultat": 5695,
                    "Driftsresultat": 3975,
                    "Cash EPS": 11.25,
                    "Cash ROE": 16.0,
                    "Solvens II": 194,
                    "AUM mrd.": 1609,
                    "Combined ratio": 92,
                    "Utbytte": 5.40,
                },
            ],
            "targets": {
                "group_profit_2028": "7,0 mrd. NOK før amortisering og skatt",
                "roe_2028": "17%",
                "combined_ratio_2028": "90% eller lavere",
                "cost_growth": "Ca. 5% årlig kostnadsvekst 2025–2028",
                "capital_return": ">12 mrd. NOK i tilbakekjøp innen utgangen av 2030",
            },
            "shareholders_date": "31.03.2026",
            "shareholders": [
                {"Aksjonær": "Folketrygdfondet", "Andel": 10.96},
                {"Aksjonær": "DNB Asset Management", "Andel": 4.15},
                {"Aksjonær": "Vanguard Group", "Andel": 3.96},
                {"Aksjonær": "Storebrand ASA (egne aksjer)", "Andel": 3.21},
                {"Aksjonær": "BlackRock", "Andel": 2.87},
                {"Aksjonær": "Alfred Berg", "Andel": 2.62},
                {"Aksjonær": "KLP", "Andel": 2.52},
                {"Aksjonær": "Storebrand Asset Management", "Andel": 2.42},
                {"Aksjonær": "Nordea Funds", "Andel": 2.00},
                {"Aksjonær": "Handelsbanken Fonder", "Andel": 1.81},
            ],
            "news": [
                {
                    "Dato": "16.09.2026",
                    "Hendelse": "Q3 pre-silent newsletter",
                    "Oppsummering": (
                        "2028-ambisjonen på 7 mrd. NOK ble gjentatt. Sterkere NOK er motvind for "
                        "svensk AUM/inntjening, performance fees ventes begrenset og kundeutgangen "
                        "på 13 mrd. NOK gir rundt 20 MNOK lavere fee-inntekter per kvartal fra Q3."
                    ),
                },
                {
                    "Dato": "15.07.2026",
                    "Hendelse": "Q2 2026 – rekordsterkt kvartal",
                    "Oppsummering": (
                        "Konsernresultat 1 799 MNOK, driftsresultat 1 119 MNOK, "
                        "forsikringsresultat 889 MNOK og solvensgrad 200%."
                    ),
                },
                {
                    "Dato": "15.07.2026",
                    "Hendelse": "Ny tilbakekjøpstransje på 1 mrd. NOK",
                    "Oppsummering": (
                        "Andre 2026-transje ble startet. Totalt planlegges 2 mrd. NOK "
                        "i tilbakekjøp i 2026."
                    ),
                },
                {
                    "Dato": "11.06.2026",
                    "Hendelse": "Avtale om kjøp av Knif Trygghet Forsikring",
                    "Oppsummering": (
                        "Storebrand inngikk avtale om å kjøpe opptil 100% av Knif Trygghet, "
                        "med rundt 0,8 mrd. NOK i porteføljepremier."
                    ),
                },
            ],
            "next_report": "21.10.2026",
            "consensus": {
                "cash_eps_2026": 11.49,
                "cash_eps_2027": 13.08,
                "cash_eps_2028": 14.46,
                "dps_2027": 6.72,
                "dps_2028": 7.51,
            },
            "buy_level": 180.0,
            "sell_level": 260.0,
            "max_pe_underway": 20.0,
        },
    },
}

# =========================================================
# HISTORISK VERDSETTELSE / HJELPEFUNKSJONER
# =========================================================

# Historiske referanser som vises med liten skrift under vekst- og P/E-feltene.
# P/E-tallene er historiske årsmultipler. Når 5 sammenlignbare år ikke finnes,
# brukes siste 3 sammenlignbare år. N/M brukes der resultat/scope gjør P/E lite meningsfull.
VALUATION_HISTORY = {
    "NORBIT": {
        "growth_text": "Omsetning CAGR 5 år 32,2% | EPS CAGR 5 år 67,5%",
        "pe_text": "P/E snitt 5 år 25,5x | siste år 29,5x",
    },
    "Cambi": {
        "growth_text": "Omsetning CAGR 5 år 23,8% | EPS CAGR N/M pga. store resultatsvingninger",
        "pe_text": "Historisk P/E N/M – flere år er ikke sammenlignbare",
    },
    "Kitron": {
        "growth_text": "Omsetning CAGR 5 år 14,4% | EPS CAGR 5 år 15,4%",
        "pe_text": "P/E snitt 5 år 22,1x | siste år 28,0x",
    },
    "NOTE": {
        "growth_text": "Omsetning CAGR 5 år 15,3% | EPS CAGR 5 år 19,2%",
        "pe_text": "P/E snitt 5 år 20,7x | siste år 18,4x",
    },
    "Protector": {
        "growth_text": "Premie-/omsetningsvekst CAGR 5 år 20,7% | EPS CAGR 5 år 21,5%",
        "pe_text": "P/E snitt 5 år 12,2x | siste år 16,5x",
    },
    "B2 Impact": {
        "growth_text": "Omsetning CAGR 5 år 3,3% | EPS CAGR 5 år 4,5%",
        "pe_text": "P/E snitt 5 år 9,7x | siste år 10,9x",
    },
    "Byggmax": {
        "growth_text": "Omsetning CAGR 5 år -2,1% | EPS CAGR 5 år -24,8%",
        "pe_text": "P/E snitt 5 år 32,1x | siste år 16,9x",
    },
    "Bakkafrost": {
        "growth_text": "Omsetning CAGR 5 år 8,5% | EPS CAGR 5 år -14,0%",
        "pe_text": "P/E snitt 5 år 28,3x | siste år 37,0x",
    },
    "Nordic Semiconductor": {
        "growth_text": "Omsetning CAGR 5 år 10,5% | EPS CAGR N/M pga. tapsår",
        "pe_text": "P/E snitt N/M pga. tapsår | siste år ca. 165x",
    },
    "SATS": {
        "growth_text": "Omsetning CAGR 5 år 9,3% | EPS CAGR N/M pga. tapsår tidlig i perioden",
        "pe_text": "P/E snitt 3 år 15,8x | siste år 17,0x",
    },
    "Vend": {
        "growth_text": "3-års CAGR N/M pga. store portefølje- og scope-endringer",
        "pe_text": "Historisk P/E N/M pga. Adevinta-effekter og scope-endringer",
    },
    "Selvaag Bolig": {
        "growth_text": "Omsetning CAGR 5 år -5,0% | EPS CAGR 5 år -28,4%",
        "pe_text": "P/E snitt 5 år 15,1x | siste år 25,8x",
    },
    "Storebrand": {
        "growth_text": "AUM CAGR 5 år 10,8% | EPS CAGR N/M som historisk sammenligning",
        "pe_text": "P/E snitt 5 år 13,4x | siste år 14,8x",
    },
}


def render_valuation_history_context(company_name, section):
    hist = VALUATION_HISTORY.get(company_name, {})
    key = "growth_text" if section == "growth" else "pe_text"
    txt = hist.get(key)
    if txt:
        st.markdown(
            f"<div style='font-size:0.78rem;color:#8a8f98;margin-top:-0.35rem;margin-bottom:0.35rem;'>"
            f"({txt})</div>",
            unsafe_allow_html=True,
        )


def get_reference_price(company_name):
    info = companies[company_name]
    val = info.get("valuation", {})
    if "reference_price" in val:
        return float(val["reference_price"])
    for value in info.values():
        if isinstance(value, dict) and "reference_price" in value:
            return float(value["reference_price"])
    return None


def get_reference_price_date(company_name):
    info = companies[company_name]
    val = info.get("valuation", {})
    if "reference_price_date" in val:
        return val["reference_price_date"]
    for value in info.values():
        if isinstance(value, dict) and "reference_price_date" in value:
            return value["reference_price_date"]
    return "16.09.2026"


def get_valuation_targets_2028(company_name):
    info = companies[company_name]

    if company_name == "B2 Impact":
        v = info["b2"]["valuation"]
        eps_bear = v["eps_2026"] * (1 + v["growth_bear"] / 100) ** 2
        eps_base = v["eps_2026"] * (1 + v["growth_base"] / 100) ** 2
        eps_bull = v["eps_2026"] * (1 + v["growth_bull"] / 100) ** 2
        return (
            eps_bear * v["pe_bear"],
            eps_base * v["pe_base"],
            eps_bull * v["pe_bull"],
        )

    v = info.get("valuation")
    if not v:
        return (None, None, None)

    if company_name == "Cambi":
        return (
            v["cambi_eps_2028_bear"] * v["pe_bear"],
            v["cambi_eps_2028_base"] * v["pe_base"],
            v["cambi_eps_2028_bull"] * v["pe_bull"],
        )

    if company_name == "Vend":
        eps_bear = v["adj_eps_2026"] * (1 + v["growth_bear"] / 100) ** 2
        eps_base = v["adj_eps_2026"] * (1 + v["growth_base"] / 100) ** 2
        eps_bull = v["adj_eps_2026"] * (1 + v["growth_bull"] / 100) ** 2
        adevinta = float(info["vend"].get("adevinta_per_share", 0.0))
        return (
            eps_bear * v["pe_bear"] + adevinta,
            eps_base * v["pe_base"] + adevinta,
            eps_bull * v["pe_bull"] + adevinta,
        )

    eps_key = "eps_2026"
    eps_2026 = float(v[eps_key])
    eps_bear = eps_2026 * (1 + v["growth_bear"] / 100) ** 2
    eps_base = eps_2026 * (1 + v["growth_base"] / 100) ** 2
    eps_bull = eps_2026 * (1 + v["growth_bull"] / 100) ** 2
    return (
        eps_bear * v["pe_bear"],
        eps_base * v["pe_base"],
        eps_bull * v["pe_bull"],
    )


# =========================================================
# TOPP / MENY
# =========================================================

st.title("📊 Investeringsdashboard")

st.sidebar.title("Meny")

side = st.sidebar.radio(
    "Velg side",
    [
        "Dashboard",
        "Selskaper",
        "Gode kjøp",
    ]
)

# =========================================================
# RAPPORTERINGSDATA – TEST FOR NORBIT
# =========================================================
# Første steg mot én sentral datakilde for rapporterte regnskapstall.
REPORTING_DATA = {
    "NORBIT": {
        "source_note": (
            "Historiske års- og kvartalstall er hentet fra NORBITs publiserte "
            "års- og kvartalsrapporter. Beløp er i MNOK dersom ikke annet er oppgitt."
        ),
        "annual": [
            {"År": 2021, "Omsetning": 787.8, "Vekst": 27.0, "EBITDA": 142.6, "EBITDA-margin": 18.0, "EBIT": 73.5, "EBIT-margin": 9.0, "Resultat": 47.9, "EPS": 0.83, "OCF": 47.7, "FCF": None, "NIBD / EBITDA": 1.7},
            {"År": 2022, "Omsetning": 1167.5, "Vekst": 48.0, "EBITDA": 235.3, "EBITDA-margin": 20.0, "EBIT": 148.8, "EBIT-margin": 13.0, "Resultat": 106.7, "EPS": 1.82, "OCF": 85.7, "FCF": None, "NIBD / EBITDA": 1.4},
            {"År": 2023, "Omsetning": 1518.9, "Vekst": 30.0, "EBITDA": 391.8, "EBITDA-margin": 26.0, "EBIT": 284.2, "EBIT-margin": 19.0, "Resultat": 185.3, "EPS": 3.10, "OCF": 345.7, "FCF": None, "NIBD / EBITDA": 0.5},
            {"År": 2024, "Omsetning": 1751.4, "Vekst": 15.0, "EBITDA": 474.0, "EBITDA-margin": 27.0, "EBIT": 341.7, "EBIT-margin": 20.0, "Resultat": 243.3, "EPS": 3.93, "OCF": 430.9, "FCF": None, "NIBD / EBITDA": 0.7},
            {"År": 2025, "Omsetning": 2502.5, "Vekst": 43.0, "EBITDA": 712.2, "EBITDA-margin": 28.0, "EBIT": 555.4, "EBIT-margin": 22.0, "Resultat": 404.3, "EPS": 6.32, "OCF": 500.6, "FCF": None, "NIBD / EBITDA": 0.8},
        ],
        "quarterly": [
            {"Periode": "Q1 2025", "Omsetning": 521.7, "Vekst YoY": 29.0, "EBIT": 127.4, "EBIT-margin": 24.0, "EPS": 1.40, "OCF": None, "FCF": None, "NIBD / EBITDA": None},
            {"Periode": "Q2 2025", "Omsetning": 684.4, "Vekst YoY": 63.0, "EBIT": 174.2, "EBIT-margin": 25.0, "EPS": 2.06, "OCF": None, "FCF": None, "NIBD / EBITDA": None},
            {"Periode": "Q3 2025", "Omsetning": 505.4, "Vekst YoY": 36.0, "EBIT": 75.4, "EBIT-margin": 15.0, "EPS": 0.81, "OCF": None, "FCF": None, "NIBD / EBITDA": None},
            {"Periode": "Q4 2025", "Omsetning": 791.1, "Vekst YoY": 42.0, "EBIT": 178.4, "EBIT-margin": 23.0, "EPS": 2.05, "OCF": None, "FCF": None, "NIBD / EBITDA": 0.8},
            {"Periode": "Q1 2026", "Omsetning": 732.1, "Vekst YoY": 40.0, "EBIT": 155.9, "EBIT-margin": 21.0, "Resultat": None, "EPS": 1.73, "OCF": 212.6, "FCF": 156.2, "NIBD / EBITDA": None},
            {"Periode": "Q2 2026", "Omsetning": 831.6, "Vekst YoY": 22.0, "EBIT": 205.2, "EBIT-margin": 24.7, "Resultat": 157.1, "EPS": 2.45, "OCF": 275.2, "FCF": 219.4, "NIBD / EBITDA": 0.7},
        ],
    }
}

# =========================================================
# DAGLIGE OPPDATERINGER
# =========================================================

DATA_DIR = Path(__file__).resolve().parent / "data"
DAILY_UPDATES_FILE = DATA_DIR / "daily_updates.json"
CONTRACT_MONITOR_FILE = DATA_DIR / "contract_monitor.json"

def load_json_file(path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

REPORTING_FILE = DATA_DIR / "norbit_reporting.json"


def _secret(name, default=None):
    """Les Streamlit-secret uten å feile i lokal utvikling når secrets.toml mangler."""
    try:
        value = st.secrets[name]
        return value if value not in (None, "") else default
    except Exception:
        return default


def _github_reporting_config():
    token = _secret("GITHUB_TOKEN")
    repo = _secret("GITHUB_REPO")
    if not token or not repo:
        return None
    return {
        "token": str(token),
        "repo": str(repo),
        "branch": str(_secret("GITHUB_BRANCH", "main")),
        "path": str(_secret("GITHUB_REPORTING_PATH", "data/norbit_reporting.json")),
    }


def _github_request(method, url, token, payload=None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jt-investering-streamlit",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def _load_reporting_from_github(config):
    path = urllib.parse.quote(config["path"], safe="/")
    branch = urllib.parse.quote(config["branch"], safe="")
    url = f"https://api.github.com/repos/{config['repo']}/contents/{path}?ref={branch}"
    try:
        meta = _github_request("GET", url, config["token"])
        encoded = meta.get("content", "").replace("\n", "")
        if not encoded:
            return None, "GitHub-filen finnes, men inneholder ingen data."
        raw = base64.b64decode(encoded).decode("utf-8")
        return json.loads(raw), None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        return None, f"GitHub svarte med HTTP {exc.code}."
    except Exception as exc:
        return None, f"Kunne ikke lese rapporteringsdata fra GitHub: {exc}"


def _save_reporting_to_github(report, config, commit_message):
    path = urllib.parse.quote(config["path"], safe="/")
    branch = urllib.parse.quote(config["branch"], safe="")
    get_url = f"https://api.github.com/repos/{config['repo']}/contents/{path}?ref={branch}"
    put_url = f"https://api.github.com/repos/{config['repo']}/contents/{path}"
    sha = None
    try:
        current = _github_request("GET", get_url, config["token"])
        sha = current.get("sha")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return False, f"Kunne ikke lese eksisterende GitHub-fil (HTTP {exc.code})."
    except Exception as exc:
        return False, f"Kunne ikke kontakte GitHub før lagring: {exc}"

    content = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    payload = {
        "message": commit_message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": config["branch"],
    }
    if sha:
        payload["sha"] = sha

    try:
        _github_request("PUT", put_url, config["token"], payload)
        return True, "Lagret permanent i GitHub."
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
            message = json.loads(detail).get("message", detail)
        except Exception:
            message = ""
        return False, f"GitHub-lagring feilet (HTTP {exc.code}){': ' + message if message else '.'}"
    except Exception as exc:
        return False, f"GitHub-lagring feilet: {exc}"


def _quarter_parts(period):
    match = re.fullmatch(r"Q([1-4])\s+(20\d{2})", str(period).strip())
    if not match:
        return None
    return int(match.group(2)), int(match.group(1))


def _quarter_sort_key(row):
    parts = _quarter_parts(row.get("Periode"))
    return parts if parts else (0, 0)


def load_norbit_reporting_data(force_reload=False):
    """Last NORBIT-data fra GitHub når konfigurert, ellers lokal fil/fallback."""
    if force_reload:
        st.session_state.pop("norbit_reporting_data", None)

    if "norbit_reporting_data" not in st.session_state:
        config = _github_reporting_config()
        loaded = None
        source = "Innebygde standarddata"
        warning = None

        if config:
            loaded, warning = _load_reporting_from_github(config)
            if loaded is not None:
                source = f"GitHub · {config['repo']} · {config['branch']}"

        if loaded is None:
            local = load_json_file(REPORTING_FILE, None)
            if local is not None:
                loaded = local
                source = "Lokal datafil (utvikling)"
            else:
                loaded = copy.deepcopy(REPORTING_DATA["NORBIT"])

        for row in loaded.get("quarterly", []):
            row.setdefault("Resultat", None)
            row.setdefault("OCF", None)
            row.setdefault("FCF", None)
            row.setdefault("NIBD / EBITDA", None)
        for row in loaded.get("annual", []):
            row.setdefault("FCF", None)

        st.session_state["norbit_reporting_data"] = loaded
        st.session_state["norbit_reporting_storage_source"] = source
        st.session_state["norbit_reporting_storage_warning"] = warning

    return st.session_state["norbit_reporting_data"]


def save_norbit_reporting_data(report, commit_message="Oppdater NORBIT rapportering"):
    """Lagre permanent i GitHub når secrets er konfigurert; ellers lokalt i utvikling."""
    config = _github_reporting_config()
    if config:
        ok, message = _save_reporting_to_github(report, config, commit_message)
        if not ok:
            return False, message
        st.session_state["norbit_reporting_storage_source"] = (
            f"GitHub · {config['repo']} · {config['branch']}"
        )
    else:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with REPORTING_FILE.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        message = "Lagret lokalt i Codespaces (testmodus)."
        st.session_state["norbit_reporting_storage_source"] = "Lokal datafil (utvikling)"

    st.session_state["norbit_reporting_data"] = report
    return True, message


def _find_quarter(report, year, quarter):
    target = f"Q{quarter} {year}"
    for row in report.get("quarterly", []):
        if row.get("Periode") == target:
            return row
    return None


def _pct_change(current, previous):
    if current is None or previous in (None, 0):
        return None
    return (float(current) / float(previous) - 1) * 100


def prepare_norbit_info(base_info, report):
    """Koble siste registrerte rapportering til NORBITs Oversikt/Nøkkeltall."""
    info = copy.deepcopy(base_info)
    quarterly = sorted(report.get("quarterly", []), key=_quarter_sort_key)
    if not quarterly:
        return info

    latest = quarterly[-1]
    parts = _quarter_parts(latest.get("Periode"))
    if not parts:
        return info
    year, quarter = parts
    prev = _find_quarter(report, year - 1, quarter)

    revenue = latest.get("Omsetning")
    ebit = latest.get("EBIT")
    ebit_margin = latest.get("EBIT-margin")
    if ebit_margin is None and revenue not in (None, 0) and ebit is not None:
        ebit_margin = float(ebit) / float(revenue) * 100

    info["_latest_period"] = latest.get("Periode", "Q2 2026")
    info["q2"] = {
        "revenue": float(revenue or 0),
        "growth": float(latest.get("Vekst YoY") or 0),
        "ebit": float(ebit or 0),
        "ebit_margin": float(ebit_margin or 0),
        "eps": float(latest.get("EPS") or 0),
        "ocf": float(latest.get("OCF") or 0),
        "fcf": float(latest.get("FCF") or 0),
    }

    rev_yoy = latest.get("Vekst YoY")
    ebit_yoy = _pct_change(ebit, prev.get("EBIT") if prev else None)
    eps_yoy = _pct_change(latest.get("EPS"), prev.get("EPS") if prev else None)
    ocf_yoy = _pct_change(latest.get("OCF"), prev.get("OCF") if prev else None)
    fcf_yoy = _pct_change(latest.get("FCF"), prev.get("FCF") if prev else None)
    prev_margin = prev.get("EBIT-margin") if prev else None
    margin_delta = None if prev_margin is None else float(ebit_margin or 0) - float(prev_margin)

    def pct_text(value, suffix=" mot i fjor"):
        return "" if value is None else f"{value:+.0f}%{suffix}"

    info["q2_yoy"] = {
        "revenue": pct_text(rev_yoy),
        "ocf": pct_text(ocf_yoy),
        "ebit_margin": "" if margin_delta is None else f"{margin_delta:+.1f} pp mot i fjor".replace(".", ","),
        "ebit": pct_text(ebit_yoy),
        "eps": pct_text(eps_yoy),
        "fcf": pct_text(fcf_yoy),
    }

    leverage = latest.get("NIBD / EBITDA")
    if leverage is not None:
        info["nibd_ebitda"] = float(leverage)

    # LTM EPS og P/E fra de siste fire registrerte kvartalene.
    if len(quarterly) >= 4:
        last4 = quarterly[-4:]
        eps_values = [r.get("EPS") for r in last4]
        if all(v is not None for v in eps_values):
            eps_ltm = sum(float(v) for v in eps_values)
            info["eps_ltm"] = eps_ltm
            if eps_ltm > 0 and info.get("price"):
                info["pe_ltm"] = float(info["price"]) / eps_ltm
        fcf_values = [r.get("FCF") for r in last4]
        if all(v is not None for v in fcf_values):
            info["fcf_ltm"] = sum(float(v) for v in fcf_values)

    # Dynamisk YTD (Q1, H1, 9M eller FY) fra registrerte kvartaler.
    ytd_rows = []
    for q in range(1, quarter + 1):
        row = _find_quarter(report, year, q)
        if row is not None:
            ytd_rows.append(row)
    if len(ytd_rows) == quarter:
        revenue_ytd = sum(float(r.get("Omsetning") or 0) for r in ytd_rows)
        ebit_ytd = sum(float(r.get("EBIT") or 0) for r in ytd_rows)
        eps_ytd = sum(float(r.get("EPS") or 0) for r in ytd_rows)
        ocf_complete = all(r.get("OCF") is not None for r in ytd_rows)
        fcf_complete = all(r.get("FCF") is not None for r in ytd_rows)
        ocf_ytd = sum(float(r.get("OCF") or 0) for r in ytd_rows) if ocf_complete else 0.0
        fcf_ytd = sum(float(r.get("FCF") or 0) for r in ytd_rows) if fcf_complete else 0.0
        margin_ytd = ebit_ytd / revenue_ytd * 100 if revenue_ytd else 0.0

        prev_ytd = [_find_quarter(report, year - 1, q) for q in range(1, quarter + 1)]
        prev_complete = all(r is not None for r in prev_ytd)
        if prev_complete:
            prev_revenue = sum(float(r.get("Omsetning") or 0) for r in prev_ytd)
            prev_ebit = sum(float(r.get("EBIT") or 0) for r in prev_ytd)
            prev_eps = sum(float(r.get("EPS") or 0) for r in prev_ytd)
            prev_margin_ytd = prev_ebit / prev_revenue * 100 if prev_revenue else None
            revenue_yoy_ytd = _pct_change(revenue_ytd, prev_revenue)
            ebit_yoy_ytd = _pct_change(ebit_ytd, prev_ebit)
            eps_yoy_ytd = _pct_change(eps_ytd, prev_eps)
            margin_delta_ytd = None if prev_margin_ytd is None else margin_ytd - prev_margin_ytd
        else:
            revenue_yoy_ytd = ebit_yoy_ytd = eps_yoy_ytd = margin_delta_ytd = None

        label_map = {1: f"Q1 {year}", 2: f"H1 {year}", 3: f"9M {year}", 4: f"FY {year}"}
        info["_ytd_label"] = label_map[quarter]
        info["h1"] = {
            "revenue": revenue_ytd,
            "growth": revenue_yoy_ytd or 0.0,
            "ebit": ebit_ytd,
            "ebit_margin": margin_ytd,
            "eps": eps_ytd,
            "ocf": ocf_ytd,
            "fcf": fcf_ytd,
        }
        info["h1_yoy"] = {
            "revenue": pct_text(revenue_yoy_ytd),
            "ocf": "",
            "ebit_margin": "" if margin_delta_ytd is None else f"{margin_delta_ytd:+.1f} pp mot i fjor".replace(".", ","),
            "ebit": pct_text(ebit_yoy_ytd),
            "eps": pct_text(eps_yoy_ytd),
            "fcf": "",
        }

    # Nøkkeltall-tabellen bygges nå fra den samme rapporteringsdatabasen.
    financials = []
    annual = sorted(report.get("annual", []), key=lambda r: int(r.get("År", 0)))
    for row in annual[-2:]:
        financials.append({
            "Periode": str(row["År"]),
            "Omsetning": row.get("Omsetning"),
            "Vekst": f"{float(row.get('Vekst') or 0):.0f}%",
            "EBIT": row.get("EBIT"),
            "EBIT-margin": f"{float(row.get('EBIT-margin') or 0):.0f}%",
            "EPS": row.get("EPS"),
        })
    current_year_rows = [r for r in quarterly if _quarter_parts(r.get("Periode")) and _quarter_parts(r.get("Periode"))[0] == year]
    for row in current_year_rows:
        financials.append({
            "Periode": row.get("Periode"),
            "Omsetning": row.get("Omsetning"),
            "Vekst": f"{float(row.get('Vekst YoY') or 0):.0f}%",
            "EBIT": row.get("EBIT"),
            "EBIT-margin": f"{float(row.get('EBIT-margin') or 0):.1f}%",
            "EPS": row.get("EPS"),
        })
    if quarter > 1 and "_ytd_label" in info:
        financials.append({
            "Periode": info["_ytd_label"],
            "Omsetning": info["h1"]["revenue"],
            "Vekst": f"{info['h1']['growth']:.0f}%",
            "EBIT": info["h1"]["ebit"],
            "EBIT-margin": f"{info['h1']['ebit_margin']:.1f}%",
            "EPS": info["h1"]["eps"],
        })
    info["financials"] = financials
    return info


daily_updates = load_json_file(
    DAILY_UPDATES_FILE,
    [
        {
            "Dato": "2026-09-15",
            "Selskap": "Cambi",
            "Kategori": "Kontrakt / anbud",
            "Tittel": "Clarkson WRRF – Peel Region, Ontario",
            "Oppdatering": (
                "Nytt aktivt THP-anbud er lagt inn i kontraktsmonitoren. "
                "Offentlig tilbudsfrist er 02.10.2026."
            ),
            "Viktighet": "Høy",
        }
    ],
)

contract_monitor = load_json_file(CONTRACT_MONITOR_FILE, {})

# =========================================================
# DASHBOARD
# =========================================================

if side == "Dashboard":

    st.header("Dashboard")

    detailed_companies = ["NORBIT", "Cambi", "Kitron", "NOTE"]

    oslo_today = datetime.now(ZoneInfo("Europe/Oslo")).date().isoformat()
    updates_today = [
        item for item in daily_updates
        if item.get("Dato") == oslo_today
    ]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Selskaper", len(companies))

    with c2:
        st.metric("Nye oppdateringer i dag", len(updates_today))
        update_companies = sorted({
            item["Selskap"]
            for item in updates_today
            if item.get("Selskap")
        })
        if update_companies:
            st.caption(f"({', '.join(update_companies)})")

    c3.metric("Aksjonærendringer", "0")
    c4.metric(
        "Annonserte kontrakter",
        sum(len(companies[name]["contracts"]) for name in detailed_companies)
    )

    st.divider()
    st.subheader("Selskapsoversikt")

    def dashboard_target_2028(name):
        _, base_target, _ = get_valuation_targets_2028(name)
        return base_target

    dashboard_rows = []

    dashboard_company_order = [
        "NORBIT",
        "Cambi",
        "Kitron",
        "NOTE",
        "Protector",
        "B2 Impact",
        "Byggmax",
        "Bakkafrost",
        "Nordic Semiconductor",
        "SATS",
        "Vend",
        "Selvaag Bolig",
        "Storebrand",
    ]

    for name in dashboard_company_order:
        info = companies[name]
        hist = info.get("dashboard_5y", {})
        currency = info.get("currency", "NOK")
        target = dashboard_target_2028(name)

        ebit_margin = hist.get("ebit_margin_avg")
        combined_ratio = hist.get("combined_ratio_avg")
        revenue_cagr = hist.get("revenue_cagr")
        eps_cagr = hist.get("eps_cagr")
        fcf_yield_avg = hist.get("fcf_yield_avg")

        dashboard_rows.append({
            "Selskap": name,
            "Margin / ROE 5Å": (
                f'{info["storebrand"]["q2"]["roe_ltm"]:.1f}% ROE'.replace(".", ",")
                if name == "Storebrand"
                else (
                    f'{ebit_margin:.1f}%'.replace(".", ",")
                    if ebit_margin is not None
                    else "N/M"
                )
            ),
            "Omsetning / AUM CAGR 5Å": (
                f'{revenue_cagr:.1f}% AUM'.replace(".", ",")
                if name == "Storebrand" and revenue_cagr is not None
                else (
                    f'{revenue_cagr:.1f}%'.replace(".", ",")
                    if revenue_cagr is not None
                    else ("N/M" if name == "Vend" else "–")
                )
            ),
            "EPS CAGR 5Å": (
                f'{eps_cagr:.1f}%'.replace(".", ",")
                if eps_cagr is not None
                else (
                    "N/M"
                    if name in ["Cambi", "Nordic Semiconductor", "SATS", "Vend", "Storebrand"]
                    else "–"
                )
            ),
            "FCF / relevant KPI": (
                f'{combined_ratio:.1f}% CR'.replace(".", ",")
                if name == "Protector" and combined_ratio is not None
                else (
                    f'{info["b2"]["q2"]["leverage"]:.1f}x'.replace(".", ",")
                    if name == "B2 Impact"
                    else (
                        f'{info["selvaag"]["q2"]["backlog_value"] / 1000:.1f} mrd.'.replace(".", ",")
                        if name == "Selvaag Bolig"
                        else (
                            f'{info["storebrand"]["q2"]["solvency"]:.0f}% Solvens II'
                            if name == "Storebrand"
                            else (
                                f'{fcf_yield_avg:.1f}%'.replace(".", ",")
                                if fcf_yield_avg is not None
                                else "–"
                            )
                        )
                    )
                )
            ),
            "Kursmål 2028": f'{target:.0f} {currency}' if target else "–",
        })

    oversikt = pd.DataFrame(dashboard_rows)

    st.dataframe(oversikt, width="stretch", hide_index=True, height=500)

    st.caption(
        "CAGR er normalt FY2020–FY2025; øvrige 5Å-snitt gjelder FY2021–FY2025. "
        "Kolonnene bruker relevante nøkkeltall for hvert selskap. For Protector vises "
        "combined ratio (CR), for B2 Impact netto gjeld / Cash EBITDA, for Selvaag Bolig "
        "verdi under bygging, og for Storebrand ROE, AUM-vekst og Solvens II. "
        "N/M = ikke meningsfullt/sammenlignbart."
    )

    st.subheader("Dagens viktigste endringer")

    if updates_today:
        for item in updates_today:
            st.info(
                f"**{item['Selskap']} – {item['Tittel']}**\n\n"
                f"{item['Oppdatering']}"
            )
    else:
        st.info("Ingen nye vesentlige oppdateringer i dag.")

# =========================================================
# GODE KJØP
# =========================================================

elif side == "Gode kjøp":
    st.header("Gode kjøp")
    st.caption(
        "Daglig oversikt over dagens/ref. kurs mot våre bear-, base- og bull-scenarioer for 2028. "
        "Kursene under er redigerbare slik at siden kan oppdateres raskt hver dag."
    )

    good_buy_order = [
        "NORBIT", "Cambi", "Kitron", "NOTE", "Protector", "B2 Impact",
        "Byggmax", "Bakkafrost", "Nordic Semiconductor", "SATS", "Vend",
        "Selvaag Bolig", "Storebrand",
    ]

    price_rows = []
    for name in good_buy_order:
        price = get_reference_price(name)
        price_rows.append({
            "Selskap": name,
            "Dagens kurs": float(price) if price is not None else None,
            "Valuta": companies[name].get("currency", "NOK"),
        })

    with st.expander("Oppdater dagens kurser", expanded=False):
        st.caption(
            "Endre bare kolonnen Dagens kurs. Verdsettelsestabellen under beregnes på nytt automatisk."
        )
        edited_prices = st.data_editor(
            pd.DataFrame(price_rows),
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            disabled=["Selskap", "Valuta"],
            key="good_buys_price_editor",
        )

    price_map = {
        row["Selskap"]: float(row["Dagens kurs"])
        for _, row in edited_prices.iterrows()
        if pd.notna(row["Dagens kurs"])
    }

    # Vis kursdato kompakt over tabellen i stedet for en egen datotabell.
    model_dates = [get_reference_price_date(name) for name in good_buy_order]
    parsed_dates = []
    for date_text in model_dates:
        try:
            parsed_dates.append(datetime.strptime(date_text, "%d.%m.%Y").date())
        except (TypeError, ValueError):
            pass

    if parsed_dates:
        oldest_date = min(parsed_dates)
        newest_date = max(parsed_dates)
        if oldest_date == newest_date:
            st.caption(f"Kurser sist oppdatert i modellen: **{newest_date.strftime('%d.%m.%Y')}**")
        else:
            st.caption(
                "Kursdato i modellen: "
                f"**{oldest_date.strftime('%d.%m.%Y')}–{newest_date.strftime('%d.%m.%Y')}**"
            )

    rows = []
    for name in good_buy_order:
        bear, base, bull = get_valuation_targets_2028(name)
        price = price_map.get(name, get_reference_price(name))
        currency = companies[name].get("currency", "NOK")

        base_upside = ((base / price) - 1) * 100 if price and base else None
        bear_upside = ((bear / price) - 1) * 100 if price and bear else None
        bull_upside = ((bull / price) - 1) * 100 if price and bull else None

        rows.append({
            "Selskap": name,
            "Dagens kurs": f"{price:.2f} {currency}".replace(".", ",") if price else "–",
            "Bear 2028": f"{bear:.0f} {currency}" if bear else "–",
            "Base 2028": f"{base:.0f} {currency}" if base else "–",
            "Bull 2028": f"{bull:.0f} {currency}" if bull else "–",
            "Bear avvik": f"{bear_upside:+.0f}%" if bear_upside is not None else "–",
            "Base oppside": f"{base_upside:+.0f}%" if base_upside is not None else "–",
            "Bull oppside": f"{bull_upside:+.0f}%" if bull_upside is not None else "–",
            "_base_sort": base_upside if base_upside is not None else float("-inf"),
        })

    # Mest interessant base-oppside øverst hver gang siden åpnes/oppdateres.
    good_buys_df = (
        pd.DataFrame(rows)
        .sort_values("_base_sort", ascending=False, kind="stable")
        .drop(columns=["_base_sort"])
        .reset_index(drop=True)
    )

    def style_base_upside(value):
        """Diskré fargekoding: grønn >=20 %, rød <0 %, ellers nøytral."""
        if value in (None, "–"):
            return ""
        try:
            pct = float(str(value).replace("%", "").replace("+", "").replace(",", "."))
        except (TypeError, ValueError):
            return ""
        if pct >= 20:
            return "color: #17824b; font-weight: 600;"
        if pct < 0:
            return "color: #b42318; font-weight: 600;"
        return "color: #6b7280; font-weight: 500;"

    good_buys_styled = good_buys_df.style.map(
        style_base_upside,
        subset=["Base oppside"],
    )

    st.dataframe(good_buys_styled, width="stretch", hide_index=True, height=500)

    st.caption(
        "Tabellen er sortert etter Base oppside, høyest først. Bear/base/bull følger de samme "
        "forutsetningene som på selskapenes Verdsettelse-sider. Dagens kurs er et arbeidsfelt, "
        "ikke en automatisk live-feed."
    )

# =========================================================
# SELSKAPER
# =========================================================

elif side == "Selskaper":

    # Litt mindre tall på selskapssidene for et mer kompakt uttrykk.
    st.markdown(
        """
        <style>
        div[data-testid="stMetricValue"] {
            font-size: 1.85rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    selskap = st.selectbox("Velg selskap", list(companies.keys()))
    info = companies[selskap]

    st.header(selskap)
    st.caption(f"{info['ticker']} | {info['marked']} | {info['sektor']}")

    if selskap == "B2 Impact":
        b2 = info["b2"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("ERC", f"{b2['q2']['erc']:.1f} mrd. NOK".replace(".", ","))
            k2.metric("Leverage", f"{b2['q2']['leverage']:.1f}x".replace(".", ","))
            k3.metric("EPS-mål 2026", f"{b2['targets_2026']['eps']:.2f} NOK".replace(".", ","))

            k4, k5, k6 = st.columns(3)
            k4.metric("ROE-mål 2026", f"{b2['targets_2026']['roe']:.0f}%")
            k5.metric("Investeringer 2026", f"{b2['targets_2026']['investments']:.1f} mrd. NOK".replace(".", ","))
            k6.metric("Likviditetsreserve Q2", f"{b2['q2']['liquidity_eur']:.0f} MEUR")

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(q1, "Cash collections", f"{b2['q2']['cash_collections']:,} MNOK".replace(",", " "), b2["q2_yoy"]["cash_collections"])
            metric_with_yoy(q2, "Cash EBITDA", f"{b2['q2']['cash_ebitda']:,} MNOK".replace(",", " "), b2["q2_yoy"]["cash_ebitda"])
            metric_with_yoy(q3, "Adj. EPS", f"{b2['q2']['eps']:.2f}".replace(".", ","), b2["q2_yoy"]["eps"])

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(q4, "Adj. EBIT", f"{b2['q2']['adj_ebit']:,} MNOK".replace(",", " "), b2["q2_yoy"]["adj_ebit"])
            metric_with_yoy(q5, "Collection performance", f"{b2['q2']['collection_performance']:.0f}%", b2["q2_yoy"]["collection_performance"])
            metric_with_yoy(q6, "Porteføljeinvesteringer", f"{b2['q2']['investments']/1000:.1f} mrd. NOK".replace(".", ","), b2["q2_yoy"]["investments"])

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(h1, "Cash collections", f"{b2['h1']['cash_collections']:,} MNOK".replace(",", " "), b2["h1_yoy"]["cash_collections"])
            metric_with_yoy(h2, "Cash EBITDA", f"{b2['h1']['cash_ebitda']:,} MNOK".replace(",", " "), b2["h1_yoy"]["cash_ebitda"])
            metric_with_yoy(h3, "Adj. EPS", f"{b2['h1']['eps']:.2f}".replace(".", ","), b2["h1_yoy"]["eps"])

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(h4, "Adj. EBIT", f"{b2['h1']['adj_ebit']:,} MNOK".replace(",", " "), b2["h1_yoy"]["adj_ebit"])
            metric_with_yoy(h5, "Adj. nettoresultat", f"{b2['h1']['adj_net_profit']:,} MNOK".replace(",", " "), b2["h1_yoy"]["adj_net_profit"])
            metric_with_yoy(h6, "Leverage Q2", f"{b2['q2']['leverage']:.1f}x".replace(".", ","), b2["h1_yoy"]["leverage"])

            st.caption(
                "H1-tallene er summen av rapportert Q1 og Q2. Neste rapport: "
                f"{b2['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(b2["annual"]).copy()
            annual_df["Cash collections"] = annual_df["Cash collections"].map(lambda x: f"{x:,.0f}".replace(",", " "))
            annual_df["Cash EBITDA"] = annual_df["Cash EBITDA"].map(lambda x: f"{x:,.0f}".replace(",", " "))
            annual_df["Adj. EPS"] = annual_df["Adj. EPS"].map(lambda x: f"{x:.2f}".replace(".", ","))
            annual_df["Investeringer"] = annual_df["Investeringer"].map(lambda x: f"{x:.1f} mrd.".replace(".", ","))
            annual_df["ERC"] = annual_df["ERC"].map(lambda x: f"{x:.1f} mrd.".replace(".", ","))
            annual_df["Leverage"] = annual_df["Leverage"].map(lambda x: f"{x:.1f}x".replace(".", ","))
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("2026-mål")
            targets = pd.DataFrame([
                {"KPI": "EPS", "Mål": "Minst 2,25 NOK"},
                {"KPI": "ROE", "Mål": "Rundt 16 %"},
                {"KPI": "Porteføljeinvesteringer", "Mål": "Minst 4,0 mrd. NOK"},
                {"KPI": "Leverage", "Mål": "Under 2,5x"},
            ])
            st.dataframe(targets, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Collection performance og utvikling i ERC\n"
                "• Avkastning på nye porteføljekjøp\n"
                "• Leverage og finansieringskostnader\n"
                "• EPS/ROE og utbyttekapasitet\n"
                "• REO-salg og kapitalfrigjøring"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(b2["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.2f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Detaljert aksjonærliste datert {b2['shareholders_date']}. "
                "Listen oppdateres når nyere komplett offentlig oversikt er tilgjengelig."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(b2["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {b2['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E bruker selskapets minimumsmål på 2,25 NOK. "
                "Vekst og P/E under er våre justerbare scenarioforutsetninger."
            )

            v = b2["valuation"]
            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(b2["reference_price"]),
                step=0.5,
                key="b2_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.05,
                format="%.2f",
                key="b2_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="b2_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input("Bear vekst", value=float(v["growth_bear"]), step=1.0, format="%.0f", key="b2_gb")
            gbase = g2.number_input("Base vekst", value=float(v["growth_base"]), step=1.0, format="%.0f", key="b2_gbase")
            gbull = g3.number_input("Bull vekst", value=float(v["growth_bull"]), step=1.0, format="%.0f", key="b2_gbull")

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input("Bear P/E", min_value=1.0, value=float(v["pe_bear"]), step=1.0, format="%.0f", key="b2_peb")
            pebase = p2.number_input("Base P/E", min_value=1.0, value=float(v["pe_base"]), step=1.0, format="%.0f", key="b2_pebase")
            pebull = p3.number_input("Bull P/E", min_value=1.0, value=float(v["pe_bull"]), step=1.0, format="%.0f", key="b2_pebull")

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input("Kjøpsnivå (NOK)", value=float(v["buy_level"]), step=1.0, format="%.0f", key="b2_buy")
            sell_level = s3.number_input("Reduser/salgsnivå (NOK)", value=float(v["sell_level"]), step=1.0, format="%.0f", key="b2_sell")
            max_pe = s4.number_input("Maks P/E underveis", value=float(v["max_pe_underway"]), step=1.0, format="%.0f", key="b2_maxpe")

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ved kurs ≤ {buy_level:.0f} NOK. "
                f"Reduser deler av beholdningen ved kurs ≥ {sell_level:.0f} NOK "
                f"når P/E samtidig er rundt {max_pe:.0f}x eller høyere."
            )

    elif selskap == "Protector":
        prot = info["protector"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Combined ratio Q2", f"{prot['q2']['combined_ratio']:.1f}%".replace(".", ","))
            k2.metric("Solvensgrad Q2", f"{prot['q2']['solvency']:.0f}%")
            k3.metric("EPS H1 2026", f"{prot['h1']['eps']:.1f} NOK".replace(".", ","))

            k4, k5, k6 = st.columns(3)
            k4.metric("ROE 2025", "42,2%")
            k5.metric("Bruttopremie H1", f"{prot['h1']['gwp']:,} MNOK".replace(",", " "))
            k6.metric("Investeringsresultat H1", f"{prot['h1']['investment_return']:,} MNOK".replace(",", " "))

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Bruttopremie",
                f"{prot['q2']['gwp']:,} MNOK".replace(",", " "),
                prot["q2_yoy"]["gwp"],
            )
            metric_with_yoy(
                q2, "Forsikringsinntekter",
                f"{prot['q2']['insurance_revenue']:,} MNOK".replace(",", " "),
                prot["q2_yoy"]["insurance_revenue"],
            )
            metric_with_yoy(
                q3, "Combined ratio",
                f"{prot['q2']['combined_ratio']:.1f}%".replace(".", ","),
                prot["q2_yoy"]["combined_ratio"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "Investeringsresultat",
                f"{prot['q2']['investment_return']:,} MNOK".replace(",", " "),
                prot["q2_yoy"]["investment_return"],
            )
            metric_with_yoy(
                q5, "Resultat",
                f"{prot['q2']['profit']:,} MNOK".replace(",", " "),
                prot["q2_yoy"]["profit"],
            )
            metric_with_yoy(
                q6, "EPS",
                f"{prot['q2']['eps']:.1f}".replace(".", ","),
                prot["q2_yoy"]["eps"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Bruttopremie",
                f"{prot['h1']['gwp']:,} MNOK".replace(",", " "),
                prot["h1_yoy"]["gwp"],
            )
            metric_with_yoy(
                h2, "Forsikringsresultat",
                f"{prot['h1']['insurance_service_result']:,} MNOK".replace(",", " "),
                prot["h1_yoy"]["insurance_service_result"],
            )
            metric_with_yoy(
                h3, "Combined ratio",
                f"{prot['h1']['combined_ratio']:.1f}%".replace(".", ","),
                prot["h1_yoy"]["combined_ratio"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "Investeringsresultat",
                f"{prot['h1']['investment_return']:,} MNOK".replace(",", " "),
                prot["h1_yoy"]["investment_return"],
            )
            metric_with_yoy(
                h5, "Resultat",
                f"{prot['h1']['profit']:,} MNOK".replace(",", " "),
                prot["h1_yoy"]["profit"],
            )
            metric_with_yoy(
                h6, "EPS",
                f"{prot['h1']['eps']:.1f}".replace(".", ","),
                prot["h1_yoy"]["eps"],
            )

            st.caption(f"Neste rapport: {prot['next_report']}.")

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(prot["annual"]).copy()
            annual_df["Premieinntekter"] = annual_df["Premieinntekter"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df = annual_df.rename(columns={"Premieinntekter": "Bruttopremie"})
            annual_df["Combined ratio"] = annual_df["Combined ratio"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["Investeringsresultat"] = annual_df["Investeringsresultat"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["ROE"] = annual_df["ROE"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["EPS"] = annual_df["EPS"].map(
                lambda x: f"{x:.1f}".replace(".", ",")
            )
            annual_df["Solvens"] = annual_df["Solvens"].map(
                lambda x: f"{x:.0f}%"
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("Selskapets finansielle mål")
            target_df = pd.DataFrame([
                {"KPI": "Combined ratio", "Mål": prot["targets"]["combined_ratio"]},
                {"KPI": "ROE", "Mål": prot["targets"]["roe"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Combined ratio og skadeutvikling i hvert marked\n"
                "• Premievekst, særlig UK og Frankrike\n"
                "• Avkastning på investeringsporteføljen\n"
                "• ROE og kapitaldistribusjon/utbytte\n"
                "• Solvensgrad og kapitalbuffer"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(prot["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Aksjonærlisten er basert på årsrapporten og gjelder {prot['shareholders_date']}. "
                "Protector opplyser at VPS-registeret på IR-siden sist ble oppdatert 16.09.2026."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(prot["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {prot['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er konsensusestimat. Vekst og P/E er våre justerbare "
                "scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(prot["reference_price"]),
                step=1.0,
                key="prot_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.1,
                format="%.2f",
                key="prot_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="prot_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="prot_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="prot_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="prot_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="prot_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="prot_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="prot_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(prot["buy_level"]),
                step=5.0, format="%.0f", key="prot_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(prot["sell_level"]),
                step=5.0, format="%.0f", key="prot_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(prot["max_pe_underway"]),
                step=1.0, format="%.0f", key="prot_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def protector_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = protector_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = protector_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = protector_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)

            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bear_pv:.0f} NOK**"
                )

            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{base_pv:.0f} NOK**"
                )

            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bull_pv:.0f} NOK**"
                )

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt "
                "avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric(
                "🔴 Bear",
                f"{bear_mos:+.0f}%",
                help="Nåverdi i bear-scenario relativt til dagens kurs / referansekurs.",
            )
            m2.metric(
                "🟡 Base",
                f"{base_mos:+.0f}%",
                help="Nåverdi i base-scenario relativt til dagens kurs / referansekurs.",
            )
            m3.metric(
                "🟢 Bull",
                f"{bull_mos:+.0f}%",
                help="Nåverdi i bull-scenario relativt til dagens kurs / referansekurs.",
            )

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )

            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            base_target_eps = eps_base
            pe_levels = [14, 16, 18, 20, 22, 24, 26]

            sensitivity_rows = []
            for pe in pe_levels:
                sensitivity_target = base_target_eps * pe
                total_return, cagr, present_value = protector_scenario_metrics(
                    sensitivity_target
                )
                margin_of_safety = (present_value / ref_price - 1) * 100

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap == "Byggmax":
        bmax = info["byggmax"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("EBIT-margin Q2", f"{bmax['q2']['ebit_margin']:.1f}%".replace(".", ","))
            k2.metric("Nettogjeld / EBITDA", f"{bmax['q2']['net_debt_ebitda']:.1f}x".replace(".", ","))
            k3.metric("EPS H1 2026", f"{bmax['h1']['eps']:.2f} SEK".replace(".", ","))

            k4, k5, k6 = st.columns(3)
            k4.metric("Bruttomargin Q2", f"{bmax['q2']['gross_margin']:.1f}%".replace(".", ","))
            k5.metric(f"OCF {info.get('_ytd_label', 'H1 2026')}", f"{bmax['h1']['ocf']:,} MSEK".replace(",", " "))
            k6.metric("Nettogjeld eks. leasing", f"{bmax['q2']['net_debt_ex_leases']:,} MSEK".replace(",", " "))

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Omsetning",
                f"{bmax['q2']['revenue']:,} MSEK".replace(",", " "),
                bmax["q2_yoy"]["revenue"],
            )
            metric_with_yoy(
                q2, "Bruttomargin",
                f"{bmax['q2']['gross_margin']:.1f}%".replace(".", ","),
                bmax["q2_yoy"]["gross_margin"],
            )
            metric_with_yoy(
                q3, "EBIT-margin",
                f"{bmax['q2']['ebit_margin']:.1f}%".replace(".", ","),
                bmax["q2_yoy"]["ebit_margin"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "EBIT",
                f"{bmax['q2']['ebit']:,} MSEK".replace(",", " "),
                bmax["q2_yoy"]["ebit"],
            )
            metric_with_yoy(
                q5, "EPS",
                f"{bmax['q2']['eps']:.2f}".replace(".", ","),
                bmax["q2_yoy"]["eps"],
            )
            metric_with_yoy(
                q6, "OCF",
                f"{bmax['q2']['ocf']:,} MSEK".replace(",", " "),
                bmax["q2_yoy"]["ocf"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Omsetning",
                f"{bmax['h1']['revenue']:,} MSEK".replace(",", " "),
                bmax["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2, "Bruttomargin",
                f"{bmax['h1']['gross_margin']:.1f}%".replace(".", ","),
                bmax["h1_yoy"]["gross_margin"],
            )
            metric_with_yoy(
                h3, "EBIT-margin",
                f"{bmax['h1']['ebit_margin']:.1f}%".replace(".", ","),
                bmax["h1_yoy"]["ebit_margin"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "EBIT",
                f"{bmax['h1']['ebit']:,} MSEK".replace(",", " "),
                bmax["h1_yoy"]["ebit"],
            )
            metric_with_yoy(
                h5, "EPS",
                f"{bmax['h1']['eps']:.2f}".replace(".", ","),
                bmax["h1_yoy"]["eps"],
            )
            metric_with_yoy(
                h6, "OCF",
                f"{bmax['h1']['ocf']:,} MSEK".replace(",", " "),
                bmax["h1_yoy"]["ocf"],
            )

            st.caption(f"Neste rapport: {bmax['next_report']}.")

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(bmax["annual"]).copy()
            annual_df["Omsetning"] = annual_df["Omsetning"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["EBIT"] = annual_df["EBIT"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["EBIT-margin"] = annual_df["EBIT-margin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["EPS"] = annual_df["EPS"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            annual_df["OCF"] = annual_df["OCF"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["Nettogjeld eks. IFRS 16"] = annual_df["Nettogjeld eks. IFRS 16"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["Utbytte"] = annual_df["Utbytte"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("Selskapets finansielle mål")
            target_df = pd.DataFrame([
                {"KPI": "Omsetningsvekst", "Mål": bmax["targets"]["sales_growth"]},
                {"KPI": "EBITA-margin", "Mål": bmax["targets"]["ebita_margin"]},
                {"KPI": "Utbytte", "Mål": bmax["targets"]["dividend"]},
                {"KPI": "Nettogjeld / EBITDA", "Mål": bmax["targets"]["leverage"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Sammenlignbar salgsvekst og normalisering i DIY-markedet\n"
                "• Bruttomargin og EBITA/EBIT-margin\n"
                "• Kostnadsdisiplin og operasjonell gearing\n"
                "• Kontantstrøm og nettogjeld\n"
                "• Utvikling i e-handel og butikkproduktivitet"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(bmax["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Aksjonærlisten er basert på årsrapporten og gjelder {bmax['shareholders_date']}."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(bmax["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {bmax['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er konsensusestimat. Vekst og P/E er våre justerbare "
                "scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (SEK)",
                min_value=1.0,
                value=float(bmax["reference_price"]),
                step=0.5,
                key="bmax_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.1,
                format="%.2f",
                key="bmax_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="bmax_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="bmax_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="bmax_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="bmax_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="bmax_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="bmax_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="bmax_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (SEK)", value=float(bmax["buy_level"]),
                step=1.0, format="%.0f", key="bmax_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (SEK)", value=float(bmax["sell_level"]),
                step=1.0, format="%.0f", key="bmax_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(bmax["max_pe_underway"]),
                step=1.0, format="%.0f", key="bmax_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def bmax_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = bmax_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = bmax_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = bmax_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} SEK")
            r2.metric("🟡 Base", f"{target_base:.0f} SEK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} SEK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)

            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bear_pv:.0f} SEK**"
                )

            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{base_pv:.0f} SEK**"
                )

            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(
                    f"Nåverdi ved {required_return:.1f}% krav: "
                    f"**{bull_pv:.0f} SEK**"
                )

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [8, 10, 12, 13, 14, 16, 18]
            sensitivity_rows = []

            for pe in pe_levels:
                sensitivity_target = eps_base * pe
                total_return, cagr, present_value = bmax_scenario_metrics(
                    sensitivity_target
                )
                margin_of_safety = (present_value / ref_price - 1) * 100

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} SEK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} SEK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} SEK; "
                f"reduser ≥ {sell_level:.0f} SEK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap == "Bakkafrost":
        bakka = info["bakkafrost"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Slaktevolum Q2", f"{bakka['q2']['harvest']:,} tonn".replace(",", " "))
            k2.metric("Operasjonell EBIT Q2", f"{bakka['q2']['operational_ebit']:,} MDKK".replace(",", " "))
            k3.metric("Guiding 2026", "117 000 tonn")

            k4, k5, k6 = st.columns(3)
            k4.metric("FO EBIT/kg Q2", f"{bakka['q2']['fo_ebit_per_kg']:.2f} DKK".replace(".", ","))
            k5.metric("Slaktevolum H1", f"{bakka['h1']['harvest']:,} tonn".replace(",", " "))
            k6.metric("Smolt overført H1", f"{bakka['h1']['smolt_transfer']:.1f}".replace(".", ",") + " mill.")

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Slaktevolum",
                f"{bakka['q2']['harvest']:,} tonn".replace(",", " "),
                bakka["q2_yoy"]["harvest"],
            )
            metric_with_yoy(
                q2, "Operasjonell EBIT",
                f"{bakka['q2']['operational_ebit']:,} MDKK".replace(",", " "),
                bakka["q2_yoy"]["operational_ebit"],
            )
            metric_with_yoy(
                q3, "Kontantstrøm fra drift",
                f"{bakka['q2']['ocf']:,} MDKK".replace(",", " "),
                bakka["q2_yoy"]["ocf"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "FO operasjonell EBIT/kg",
                f"{bakka['q2']['fo_ebit_per_kg']:.2f} DKK".replace(".", ","),
                bakka["q2_yoy"]["fo_ebit_per_kg"],
            )
            metric_with_yoy(
                q5, "SCT operasjonell EBIT/kg",
                f"{bakka['q2']['sct_ebit_per_kg']:.2f} DKK".replace(".", ","),
                bakka["q2_yoy"]["sct_ebit_per_kg"],
            )
            metric_with_yoy(
                q6, "Smolt overført",
                f"{bakka['q2']['smolt_transfer']:.1f}".replace(".", ",") + " mill.",
                bakka["q2_yoy"]["smolt_transfer"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Slaktevolum",
                f"{bakka['h1']['harvest']:,} tonn".replace(",", " "),
                bakka["h1_yoy"]["harvest"],
            )
            metric_with_yoy(
                h2, "Operasjonell EBIT",
                f"{bakka['h1']['operational_ebit']:,} MDKK".replace(",", " "),
                bakka["h1_yoy"]["operational_ebit"],
            )
            metric_with_yoy(
                h3, "FO slaktevolum",
                f"{bakka['h1']['fo_harvest']:,} tonn".replace(",", " "),
                bakka["h1_yoy"]["fo_harvest"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "SCT slaktevolum",
                f"{bakka['h1']['sct_harvest']:,} tonn".replace(",", " "),
                bakka["h1_yoy"]["sct_harvest"],
            )
            metric_with_yoy(
                h5, "Smolt overført",
                f"{bakka['h1']['smolt_transfer']:.1f}".replace(".", ",") + " mill.",
                bakka["h1_yoy"]["smolt_transfer"],
            )
            metric_with_yoy(
                h6, "FOF operasjonell EBIT-margin",
                f"{bakka['h1']['fof_margin']:.0f}%",
                bakka["h1_yoy"]["fof_margin"],
            )

            st.caption(f"Neste rapport: {bakka['next_report']}.")

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(bakka["annual"]).copy()
            annual_df["Omsetning"] = annual_df["Omsetning"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["Operasjonell EBIT"] = annual_df["Operasjonell EBIT"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["Operasjonell EBIT-margin"] = annual_df["Operasjonell EBIT-margin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["Slaktevolum"] = annual_df["Slaktevolum"].map(
                lambda x: f"{x:,.0f}".replace(",", " ")
            )
            annual_df["EPS DKK"] = annual_df["EPS DKK"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            annual_df["Utbytte DKK"] = annual_df["Utbytte DKK"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("2026-guiding og finansielle mål")
            target_df = pd.DataFrame([
                {"KPI": "Slaktevolum 2026", "Mål": bakka["targets"]["harvest_2026"]},
                {"KPI": "Smoltoverføring Færøyene", "Mål": bakka["targets"]["smolt_fo"]},
                {"KPI": "Smoltoverføring Skottland", "Mål": bakka["targets"]["smolt_sct"]},
                {"KPI": "Utbyttepolicy", "Mål": bakka["targets"]["dividend"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Biologi, dødelighet og kostnad per kg på Færøyene\n"
                "• Normalisering av lønnsomheten i Skottland\n"
                "• Slaktevolum, snittvekt og smoltkvalitet\n"
                "• Laksepris og balansen mellom tilbud og etterspørsel\n"
                "• Fôrkostnader, investeringer og kontantstrøm"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(bakka["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.2f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Bakkafrosts offentliggjorte aksjonærliste, oppdatert {bakka['shareholders_date']}."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(bakka["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {bakka['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er satt til ca. 14,90 NOK, basert på konsensus 10,32 DKK "
                "omregnet med DKK/NOK 1,4432 per 16.09.2026. Vekst og P/E er våre "
                "justerbare scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(bakka["reference_price"]),
                step=1.0,
                key="bakka_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.1,
                format="%.2f",
                key="bakka_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="bakka_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="bakka_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="bakka_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="bakka_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="bakka_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="bakka_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="bakka_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(bakka["buy_level"]),
                step=5.0, format="%.0f", key="bakka_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(bakka["sell_level"]),
                step=5.0, format="%.0f", key="bakka_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(bakka["max_pe_underway"]),
                step=1.0, format="%.0f", key="bakka_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def bakka_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = bakka_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = bakka_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = bakka_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [10, 12, 14, 15, 16, 18, 20]
            sensitivity_rows = []
            for pe in pe_levels:
                sensitivity_target = eps_base * pe
                total_return, cagr, present_value = bakka_scenario_metrics(sensitivity_target)
                margin_of_safety = (present_value / ref_price - 1) * 100
                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap == "Nordic Semiconductor":
        nod = info["nordicsemi"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Omsetning Q2", f"{nod['q2']['revenue']:.1f} MUSD".replace(".", ","))
            k2.metric("Bruttomargin Q2", f"{nod['q2']['gross_margin']:.1f}%".replace(".", ","))
            k3.metric("Just. EBITDA-margin Q2", f"{nod['q2']['adj_ebitda_margin']:.1f}%".replace(".", ","))

            k4, k5, k6 = st.columns(3)
            k4.metric("Long-range Q2", f"{nod['q2']['long_range']:.1f} MUSD".replace(".", ","))
            k5.metric("Kontanter H1", f"{nod['h1']['cash']:.1f} MUSD".replace(".", ","))
            k6.metric("Bluetooth designandel Q2", f"{nod['q2']['design_share']:.0f}%")

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Omsetning",
                f"{nod['q2']['revenue']:.1f} MUSD".replace(".", ","),
                nod["q2_yoy"]["revenue"],
            )
            metric_with_yoy(
                q2, "Bruttomargin",
                f"{nod['q2']['gross_margin']:.1f}%".replace(".", ","),
                nod["q2_yoy"]["gross_margin"],
            )
            metric_with_yoy(
                q3, "Just. EBITDA-margin",
                f"{nod['q2']['adj_ebitda_margin']:.1f}%".replace(".", ","),
                nod["q2_yoy"]["adj_ebitda_margin"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "Just. EBITDA",
                f"{nod['q2']['adj_ebitda']:.1f} MUSD".replace(".", ","),
                nod["q2_yoy"]["adj_ebitda"],
            )
            metric_with_yoy(
                q5, "EBIT",
                f"{nod['q2']['ebit']:.1f} MUSD".replace(".", ","),
                nod["q2_yoy"]["ebit"],
            )
            metric_with_yoy(
                q6, "EPS",
                f"{nod['q2']['eps_usd']:.3f} USD".replace(".", ","),
                nod["q2_yoy"]["eps_usd"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Omsetning",
                f"{nod['h1']['revenue']:.1f} MUSD".replace(".", ","),
                nod["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2, "Bruttomargin",
                f"{nod['h1']['gross_margin']:.1f}%".replace(".", ","),
                nod["h1_yoy"]["gross_margin"],
            )
            metric_with_yoy(
                h3, "Just. EBITDA-margin",
                f"{nod['h1']['adj_ebitda_margin']:.1f}%".replace(".", ","),
                nod["h1_yoy"]["adj_ebitda_margin"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "EBIT",
                f"{nod['h1']['ebit']:.1f} MUSD".replace(".", ","),
                nod["h1_yoy"]["ebit"],
            )
            metric_with_yoy(
                h5, "EPS",
                f"{nod['h1']['eps_usd']:.3f} USD".replace(".", ","),
                nod["h1_yoy"]["eps_usd"],
            )
            metric_with_yoy(
                h6, "Kontantstrøm fra drift",
                f"{nod['h1']['ocf']:.1f} MUSD".replace(".", ","),
                nod["h1_yoy"]["ocf"],
            )

            st.caption(
                "Svakere kontantstrøm i H1 skyldes hovedsakelig bevisst lageroppbygging "
                "for å sikre kapasitet og støtte nRF54-rampen. "
                f"Neste rapport: {nod['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(nod["annual"]).copy()
            for col in ["Omsetning USDm", "EBIT USDm", "OCF USDm", "Kontanter USDm"]:
                annual_df[col] = annual_df[col].map(
                    lambda x: f"{x:,.1f}".replace(",", " ").replace(".", ",")
                )
            annual_df["Bruttomargin"] = annual_df["Bruttomargin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["EBIT-margin"] = annual_df["EBIT-margin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["EPS USD"] = annual_df["EPS USD"].map(
                lambda x: f"{x:.3f}".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("Langsiktige finansielle mål")
            target_df = pd.DataFrame([
                {"KPI": "Omsetningsvekst", "Mål": nod["targets"]["revenue_growth"]},
                {"KPI": "Bruttomargin", "Mål": nod["targets"]["gross_margin"]},
                {"KPI": "EBITDA-margin", "Mål": nod["targets"]["ebitda_margin"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• nRF54-rampen og markedsandel i nye Bluetooth-design\n"
                "• Vekst i Long-range, cellular/satellitt og nRF Cloud\n"
                "• Bruttomargin over 50% og operasjonell gearing\n"
                "• Lager/nette arbeidskapital og normalisering av kontantstrøm\n"
                "• Kundekonsentrasjon og utvikling i industri/helse"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(nod["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Beneficial-owner-oversikt fra årsrapporten, datert {nod['shareholders_date']}."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(nod["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {nod['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er satt til ca. 2,83 NOK, basert på konsensus nettoresultat "
                "og dagens aksjeantall. Vekst og P/E er våre justerbare scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(nod["reference_price"]),
                step=1.0,
                key="nod_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.1,
                format="%.2f",
                key="nod_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="nod_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="nod_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="nod_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="nod_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="nod_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="nod_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="nod_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(nod["buy_level"]),
                step=5.0, format="%.0f", key="nod_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(nod["sell_level"]),
                step=5.0, format="%.0f", key="nod_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(nod["max_pe_underway"]),
                step=1.0, format="%.0f", key="nod_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def nod_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = nod_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = nod_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = nod_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [20, 25, 30, 35, 40, 45, 50]
            sensitivity_rows = []
            for pe in pe_levels:
                sensitivity_target = eps_base * pe
                total_return, cagr, present_value = nod_scenario_metrics(sensitivity_target)
                margin_of_safety = (present_value / ref_price - 1) * 100
                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap == "SATS":
        sats = info["sats"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Medlemmer Q2", f"{sats['q2']['members']:.0f} 000")
            k2.metric("ARPM Q2", f"{sats['q2']['arpm']:.0f} NOK/mnd.")
            k3.metric("EBITDA-margin Q2", f"{sats['q2']['ebitda_margin']:.0f}%")

            k4, k5, k6 = st.columns(3)
            k4.metric(f"FCF {info.get('_ytd_label', 'H1 2026')}", f"{sats['h1']['fcf']:,} MNOK".replace(",", " "))
            k5.metric("Leverage", f"{sats['h1']['leverage']:.1f}x".replace(".", ","))
            k6.metric("Klubber Q2", f"{sats['q2']['clubs']:.0f}")

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Omsetning",
                f"{sats['q2']['revenue']:,} MNOK".replace(",", " "),
                sats["q2_yoy"]["revenue"],
            )
            metric_with_yoy(
                q2, "Medlemmer",
                f"{sats['q2']['members']:.0f} 000",
                sats["q2_yoy"]["members"],
            )
            metric_with_yoy(
                q3, "ARPM",
                f"{sats['q2']['arpm']:.0f} NOK/mnd.",
                sats["q2_yoy"]["arpm"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "EBITDA før IFRS 16",
                f"{sats['q2']['ebitda_pre_ifrs16']:,} MNOK".replace(",", " "),
                sats["q2_yoy"]["ebitda_pre_ifrs16"],
            )
            metric_with_yoy(
                q5, "EBIT før IFRS 16",
                f"{sats['q2']['ebit_pre_ifrs16']:,} MNOK".replace(",", " "),
                sats["q2_yoy"]["ebit_pre_ifrs16"],
            )
            metric_with_yoy(
                q6, "EPS",
                f"{sats['q2']['eps']:.2f}".replace(".", ","),
                sats["q2_yoy"]["eps"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Omsetning",
                f"{sats['h1']['revenue']:,} MNOK".replace(",", " "),
                sats["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2, "EBITDA før IFRS 16",
                f"{sats['h1']['ebitda_pre_ifrs16']:,} MNOK".replace(",", " "),
                sats["h1_yoy"]["ebitda_pre_ifrs16"],
            )
            metric_with_yoy(
                h3, "EBIT før IFRS 16",
                f"{sats['h1']['ebit_pre_ifrs16']:,} MNOK".replace(",", " "),
                sats["h1_yoy"]["ebit_pre_ifrs16"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "EPS",
                f"{sats['h1']['eps']:.2f}".replace(".", ","),
                sats["h1_yoy"]["eps"],
            )
            metric_with_yoy(
                h5, "Kontantstrøm fra drift",
                f"{sats['h1']['ocf']:,} MNOK".replace(",", " "),
                sats["h1_yoy"]["ocf"],
            )
            metric_with_yoy(
                h6, "Fri kontantstrøm",
                f"{sats['h1']['fcf']:,} MNOK".replace(",", " "),
                sats["h1_yoy"]["fcf"],
            )

            st.caption(
                "Q2: treningsøkter økte 3% mot i fjor. SATS har signert 13 nye klubber "
                "som skal åpne frem til og med 2028. "
                f"Neste rapport: {sats['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(sats["annual"]).copy()
            for col in [
                "Omsetning",
                "EBITDA før IFRS 16",
                "EBIT før IFRS 16",
                "OCF",
                "FCF",
            ]:
                annual_df[col] = annual_df[col].map(
                    lambda x: f"{x:,.0f}".replace(",", " ")
                )
            annual_df["EPS"] = annual_df["EPS"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            annual_df["Medlemmer"] = annual_df["Medlemmer"].map(
                lambda x: f"{x:.0f} 000"
            )
            annual_df["ARPM"] = annual_df["ARPM"].map(
                lambda x: f"{x:.0f}"
            )
            annual_df["Leverage"] = annual_df["Leverage"].map(
                lambda x: f"{x:.1f}x".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("Vekstambisjoner og kapitalallokering")
            target_df = pd.DataFrame([
                {"KPI": "Klubbåpninger", "Mål": sats["targets"]["club_openings"]},
                {"KPI": "Signerte klubber", "Mål": sats["targets"]["signed_clubs"]},
                {"KPI": "EBITDA-ambisjon", "Mål": sats["targets"]["ebitda_ambition"]},
                {"KPI": "Aksjonærdistribusjon", "Mål": sats["targets"]["distribution"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Medlemsvekst, churn og aktivitet per medlem\n"
                "• ARPM og pris/miks\n"
                "• EBITDA-/EBIT-margin før IFRS 16 og operasjonell gearing\n"
                "• Fri kontantstrøm, leverage og kapitaldistribusjon\n"
                "• Avkastning på nye klubber og kapasitetsutnyttelse i eksisterende portefølje"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(sats["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.2f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Listen er basert på konsolidert eieroversikt rundt {sats['shareholders_date']}. "
                "SATS' egen IR-side oppdaterer aksjonærlisten daglig."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(sats["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {sats['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er satt til ca. 2,88 NOK, basert på siste konsensus for "
                "2026-nettoresultat og dagens aksjeantall. Vekst og P/E er våre "
                "justerbare scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(sats["reference_price"]),
                step=0.5,
                key="sats_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.05,
                format="%.2f",
                key="sats_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="sats_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="sats_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="sats_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="sats_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="sats_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="sats_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="sats_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(sats["buy_level"]),
                step=1.0, format="%.0f", key="sats_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(sats["sell_level"]),
                step=1.0, format="%.0f", key="sats_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(sats["max_pe_underway"]),
                step=1.0, format="%.0f", key="sats_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def sats_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = sats_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = sats_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = sats_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [12, 14, 16, 18, 20, 22, 24]
            sensitivity_rows = []

            for pe in pe_levels:
                sensitivity_target = eps_base * pe
                total_return, cagr, present_value = sats_scenario_metrics(sensitivity_target)
                margin_of_safety = (present_value / ref_price - 1) * 100

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap == "Vend":
        vend = info["vend"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            approx_adevinta_per_share = vend["adevinta_per_share"]

            k1, k2, k3 = st.columns(3)
            k1.metric("EBITDA-margin Q2", f"{vend['q2']['ebitda_margin']:.0f}%")
            k2.metric("Adj. EPS H1", f"{vend['h1']['adj_eps']:.2f} NOK".replace(".", ","))
            k3.metric(f"FCF {info.get('_ytd_label', 'H1 2026')}", f"{vend['h1']['fcf']:,} MNOK".replace(",", " "))

            k4, k5, k6 = st.columns(3)
            k4.metric("Netto kontanter H1", f"{vend['h1']['net_cash']:,} MNOK".replace(",", " "))
            k5.metric("Adevinta-verdi", f"{vend['h1']['adevinta_value']/1000:.1f} mrd. NOK".replace(".", ","))
            k6.metric("Adevinta / aksje", f"~{approx_adevinta_per_share:.0f} NOK")

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Omsetning",
                f"{vend['q2']['revenue']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["revenue"],
            )
            metric_with_yoy(
                q2, "EBITDA",
                f"{vend['q2']['ebitda']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["ebitda"],
            )
            metric_with_yoy(
                q3, "EBITDA-margin",
                f"{vend['q2']['ebitda_margin']:.0f}%",
                vend["q2_yoy"]["ebitda_margin"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "Adj. EPS – videreført virksomhet",
                f"{vend['q2']['adj_eps']:.2f}".replace(".", ","),
                vend["q2_yoy"]["adj_eps"],
            )
            metric_with_yoy(
                q5, "Kontantstrøm fra drift",
                f"{vend['q2']['ocf']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["ocf"],
            )
            metric_with_yoy(
                q6, "Fri kontantstrøm",
                f"{vend['q2']['fcf']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["fcf"],
            )

            st.subheader("Vertikaler – Q2 2026")
            v1, v2, v3 = st.columns(3)
            metric_with_yoy(
                v1, "Recommerce omsetning",
                f"{vend['q2']['recommerce_revenue']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["recommerce_revenue"],
            )
            metric_with_yoy(
                v2, "Recommerce EBITDA",
                f"{vend['q2']['recommerce_ebitda']:,} MNOK".replace(",", " "),
                vend["q2_yoy"]["recommerce_ebitda"],
            )
            v3.metric(
                "Real Estate EBITDA",
                f"{vend['q2']['real_estate_ebitda']:,} MNOK".replace(",", " "),
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Omsetning",
                f"{vend['h1']['revenue']:,} MNOK".replace(",", " "),
                vend["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2, "EBITDA",
                f"{vend['h1']['ebitda']:,} MNOK".replace(",", " "),
                vend["h1_yoy"]["ebitda"],
            )
            metric_with_yoy(
                h3, "EBITDA-margin",
                f"{vend['h1']['ebitda_margin']:.0f}%",
                vend["h1_yoy"]["ebitda_margin"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "Adj. EPS – videreført virksomhet",
                f"{vend['h1']['adj_eps']:.2f}".replace(".", ","),
                vend["h1_yoy"]["adj_eps"],
            )
            metric_with_yoy(
                h5, "Kontantstrøm fra drift",
                f"{vend['h1']['ocf']:,} MNOK".replace(",", " "),
                vend["h1_yoy"]["ocf"],
            )
            metric_with_yoy(
                h6, "Fri kontantstrøm",
                f"{vend['h1']['fcf']:,} MNOK".replace(",", " "),
                vend["h1_yoy"]["fcf"],
            )

            st.caption(
                "Rapportert EPS i H1 påvirkes kraftig av ikke-kontante verdiendringer i "
                "Adevinta. Derfor bruker vi justert EPS fra videreført virksomhet i "
                "driftsanalysen og verdsettelsen. "
                f"Neste rapport: {vend['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(vend["annual"]).copy()
            for col in ["Omsetning", "EBITDA", "FCF"]:
                annual_df[col] = annual_df[col].map(
                    lambda x: f"{x:,.0f}".replace(",", " ")
                )
            annual_df["EBITDA-margin"] = annual_df["EBITDA-margin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["Utbytte"] = annual_df["Utbytte"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("2026-prioriteringer og kapitalallokering")
            target_df = pd.DataFrame([
                {"KPI": "Kostnadsbase", "Mål": vend["targets"]["opex_2026"]},
                {"KPI": "Tilbakekjøpsprogram", "Mål": vend["targets"]["buyback"]},
                {"KPI": "Adevinta", "Mål": vend["targets"]["adevinta"]},
                {"KPI": "Felles teknologiplattform", "Mål": vend["targets"]["platform"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• ARPA/pris og volum i Mobility, Real Estate og Jobs\n"
                "• Recommerce: transaksjonsvekst, enhetsøkonomi og vei mot positiv EBITDA\n"
                "• EBITDA-margin og realisering av kostnadsreduksjoner\n"
                "• Fri kontantstrøm, netto kontanter og tilbakekjøp\n"
                "• Adevinta-verdien og eventuell fremtidig realisering"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(vend["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Beneficial-owner-oversikt fra årsrapporten, datert {vend['shareholders_date']}. "
                "Blommenholm Industrier eier fortsatt 43 167 130 aksjer; etter kapitalnedsettelsen "
                "i juli 2026 tilsvarer dette 20,47% av utestående aksjer og stemmer."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(vend["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {vend['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "Vend skiller seg fra de andre selskapene fordi Adevinta-eierandelen "
                "verdsettes separat. Vi bruker derfor justert EPS for kjernevirksomheten, "
                "multipliserer denne med valgt P/E og legger deretter til valgt Adevinta-verdi "
                "per Vend-aksje."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(vend["reference_price"]),
                step=1.0,
                key="vend_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "Adj. EPS 2026E – kjernevirksomhet",
                min_value=0.1,
                value=float(v["adj_eps_2026"]),
                step=0.1,
                format="%.2f",
                key="vend_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="vend_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år – kjernevirksomhet**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="vend_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="vend_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="vend_gbull"
            )

            st.markdown("**P/E i målåret – kjernevirksomhet**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="vend_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="vend_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="vend_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Adj. EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(vend["buy_level"]),
                step=5.0, format="%.0f", key="vend_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(vend["sell_level"]),
                step=5.0, format="%.0f", key="vend_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(vend["max_pe_underway"]),
                step=1.0, format="%.0f", key="vend_maxpe"
            )

            adevinta_per_share = st.number_input(
                "Adevinta-verdi per Vend-aksje (NOK)",
                min_value=0.0,
                value=float(vend["adevinta_per_share"]),
                step=1.0,
                format="%.0f",
                key="vend_adevinta_per_share",
            )
            st.caption(
                "Utgangspunktet 36 NOK per aksje tilsvarer omtrent 7,2 mrd. NOK fordelt "
                "på rundt 200 mill. utestående Vend-aksjer etter egne aksjer."
            )

            core_bear = eps_bear * peb
            core_base = eps_base * pebase
            core_bull = eps_bull * pebull

            target_bear = core_bear + adevinta_per_share
            target_base = core_base + adevinta_per_share
            target_bull = core_bull + adevinta_per_share

            target_year = 2028
            years_to_target = target_year - 2026

            def vend_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = vend_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = vend_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = vend_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.caption(
                f"Base består av ca. {core_base:.0f} NOK for kjernevirksomheten + "
                f"{adevinta_per_share:.0f} NOK Adevinta-verdi per aksje."
            )

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            st.caption(
                "Nåverdi er samlet kursmål i målåret, inkludert Adevinta-verdi, "
                "diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("Adj. EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [16, 18, 20, 22, 24, 26, 28]
            sensitivity_rows = []

            for pe in pe_levels:
                core_value = eps_base * pe
                total_target = core_value + adevinta_per_share
                total_return, cagr, present_value = vend_scenario_metrics(total_target)
                margin_of_safety = (present_value / ref_price - 1) * 100

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kjerneverdi": f"{core_value:.0f} NOK",
                        "Adevinta": f"{adevinta_per_share:.0f} NOK",
                        "Kursmål 2028": f"{total_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E på kjernevirksomheten samtidig "
                f"er rundt {max_pe:.0f}x eller høyere."
            )

    elif selskap == "Selvaag Bolig":
        sbo = info["selvaag"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Solgte boliger Q2", f"{sbo['q2']['units_sold']:.0f}")
            k2.metric("Overleverte boliger Q2", f"{sbo['q2']['units_delivered']:.0f}")
            k3.metric(
                "Ordrebok / under bygging",
                f"{sbo['q2']['backlog_value']/1000:.1f} mrd. NOK".replace(".", ",")
            )

            k4, k5, k6 = st.columns(3)
            k4.metric(
                "Just. EBITDA-margin Q2",
                f"{sbo['q2']['adj_ebitda_margin']:.1f}%".replace(".", ",")
            )
            k5.metric("Boliger under bygging", f"{sbo['q2']['under_construction']:,}".replace(",", " "))
            k6.metric("Egenkapitalgrad", f"{sbo['q2']['equity_ratio']:.1f}%".replace(".", ","))

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1, "Solgte boliger",
                f"{sbo['q2']['units_sold']:.0f}",
                sbo["q2_yoy"]["units_sold"],
            )
            metric_with_yoy(
                q2, "Salgsverdi",
                f"{sbo['q2']['sales_value']:,} MNOK".replace(",", " "),
                sbo["q2_yoy"]["sales_value"],
            )
            metric_with_yoy(
                q3, "Overleverte boliger",
                f"{sbo['q2']['units_delivered']:.0f}",
                sbo["q2_yoy"]["units_delivered"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4, "Just. EBITDA",
                f"{sbo['q2']['adj_ebitda']:,} MNOK".replace(",", " "),
                sbo["q2_yoy"]["adj_ebitda"],
            )
            metric_with_yoy(
                q5, "Just. EBITDA-margin",
                f"{sbo['q2']['adj_ebitda_margin']:.1f}%".replace(".", ","),
                sbo["q2_yoy"]["adj_ebitda_margin"],
            )
            metric_with_yoy(
                q6, "EPS",
                f"{sbo['q2']['eps']:.2f}".replace(".", ","),
                sbo["q2_yoy"]["eps"],
            )

            st.subheader("Prosjektportefølje – Q2 2026")
            p1, p2, p3 = st.columns(3)
            metric_with_yoy(
                p1, "Boliger under bygging",
                f"{sbo['q2']['under_construction']:,}".replace(",", " "),
                sbo["q2_yoy"]["under_construction"],
            )
            metric_with_yoy(
                p2, "Verdi under bygging",
                f"{sbo['q2']['backlog_value']/1000:.1f} mrd. NOK".replace(".", ","),
                sbo["q2_yoy"]["backlog_value"],
            )
            p3.metric("Andel solgt under bygging", f"{sbo['q2']['sold_share']:.0f}%")

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1, "Omsetning",
                f"{sbo['h1']['revenue']:,} MNOK".replace(",", " "),
                sbo["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2, "Solgte boliger",
                f"{sbo['h1']['units_sold']:.0f}",
                sbo["h1_yoy"]["units_sold"],
            )
            metric_with_yoy(
                h3, "Overleverte boliger",
                f"{sbo['h1']['units_delivered']:.0f}",
                sbo["h1_yoy"]["units_delivered"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4, "Just. EBITDA",
                f"{sbo['h1']['adj_ebitda']:,} MNOK".replace(",", " "),
                sbo["h1_yoy"]["adj_ebitda"],
            )
            metric_with_yoy(
                h5, "EPS",
                f"{sbo['h1']['eps']:.2f}".replace(".", ","),
                sbo["h1_yoy"]["eps"],
            )
            metric_with_yoy(
                h6, "Kontantstrøm fra drift",
                f"{sbo['h1']['ocf']:,} MNOK".replace(",", " "),
                sbo["h1_yoy"]["ocf"],
            )

            st.caption(
                "Negativ H1-kontantstrøm skyldes hovedsakelig flere boliger i produksjon "
                "og dermed høyere varelager. "
                f"Neste rapport: {sbo['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(sbo["annual"]).copy()
            for col in ["Omsetning", "EBIT", "Solgte boliger", "Overleverte boliger", "Under bygging", "Tomtebank"]:
                annual_df[col] = annual_df[col].map(
                    lambda x: f"{x:,.0f}".replace(",", " ")
                )
            annual_df["EBIT-margin"] = annual_df["EBIT-margin"].map(
                lambda x: f"{x:.1f}%".replace(".", ",")
            )
            annual_df["EPS"] = annual_df["EPS"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            annual_df["Utbytte"] = annual_df["Utbytte"].map(
                lambda x: f"{x:.2f}".replace(".", ",")
            )
            st.dataframe(annual_df, width="stretch", hide_index=True)

            st.subheader("Mål og prosjektstyring")
            target_df = pd.DataFrame([
                {"KPI": "Prosjektmargin", "Mål": sbo["targets"]["project_margin"]},
                {"KPI": "Utbyttepolicy", "Mål": sbo["targets"]["dividend"]},
                {"KPI": "Byggestart", "Mål": sbo["targets"]["construction_rule"]},
                {"KPI": "Ferdigstillelser 2026", "Mål": sbo["targets"]["completion_2026"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Salgstakt og salgsverdi i nye prosjekter\n"
                "• Prosjektmargin og byggekostnader\n"
                "• Andel solgte boliger før byggestart og under bygging\n"
                "• Ferdigstillelser/overleveringer og resultatføring\n"
                "• Varelager, nettogjeld og renter\n"
                "• Tomtebank og nye prosjektstarter"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(sbo["shareholders"]).copy()
            sh["Aksjer"] = sh["Aksjer"].map(lambda x: f"{x:,}".replace(",", " "))
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(
                f"Offentliggjort aksjonærliste per {sbo['shareholders_date']}."
            )

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(sbo["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {sbo['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "EPS 2026E er satt til 2,73 NOK basert på siste tilgjengelige analytikerkonsensus. "
                "Boligutvikling er syklisk, så EPS og multipler kan variere mye mellom år. "
                "Vekst og P/E er derfor justerbare scenarioforutsetninger."
            )

            v = info["valuation"]

            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)",
                min_value=1.0,
                value=float(sbo["reference_price"]),
                step=0.5,
                key="sbo_ref_price",
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "EPS 2026E",
                min_value=0.1,
                value=float(v["eps_2026"]),
                step=0.05,
                format="%.2f",
                key="sbo_eps_2026",
            )
            required_return = c2.number_input(
                "Avkastningskrav",
                min_value=0.0,
                max_value=30.0,
                value=10.0,
                step=1.0,
                format="%.0f",
                key="sbo_required_return",
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input(
                "Bear vekst", value=float(v["growth_bear"]),
                step=1.0, format="%.0f", key="sbo_gb"
            )
            gbase = g2.number_input(
                "Base vekst", value=float(v["growth_base"]),
                step=1.0, format="%.0f", key="sbo_gbase"
            )
            gbull = g3.number_input(
                "Bull vekst", value=float(v["growth_bull"]),
                step=1.0, format="%.0f", key="sbo_gbull"
            )

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input(
                "Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                step=1.0, format="%.0f", key="sbo_peb"
            )
            pebase = p2.number_input(
                "Base P/E", min_value=1.0, value=float(v["pe_base"]),
                step=1.0, format="%.0f", key="sbo_pebase"
            )
            pebull = p3.number_input(
                "Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                step=1.0, format="%.0f", key="sbo_pebull"
            )

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2

            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input(
                "Kjøpsnivå (NOK)", value=float(sbo["buy_level"]),
                step=1.0, format="%.0f", key="sbo_buy"
            )
            sell_level = s3.number_input(
                "Reduser/salgsnivå (NOK)", value=float(sbo["sell_level"]),
                step=1.0, format="%.0f", key="sbo_sell"
            )
            max_pe = s4.number_input(
                "Maks P/E underveis", value=float(sbo["max_pe_underway"]),
                step=1.0, format="%.0f", key="sbo_maxpe"
            )

            target_year = 2028
            years_to_target = target_year - 2026

            def sbo_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                if years_to_target > 0:
                    cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                    present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                else:
                    cagr = total_return
                    present_value = target_value
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = sbo_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = sbo_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = sbo_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Total avkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            st.caption(
                "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt avkastningskrav."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                "dagens kurs / referansekurs."
            )

            st.subheader("EPS-scenario 2026E–2030E")
            scenario_rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                scenario_rows.append(
                    {
                        "År": year,
                        "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                        "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                        "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                    }
                )

            eps_table = pd.DataFrame(scenario_rows)
            display_eps = eps_table.copy()
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                display_eps[col] = display_eps[col].map(
                    lambda x: f"{x:.2f}".replace(".", ",")
                )
            st.dataframe(display_eps, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base EPS 2028")
            pe_levels = [8, 9, 10, 11, 12, 13, 14]
            sensitivity_rows = []

            for pe in pe_levels:
                sensitivity_target = eps_base * pe
                total_return, cagr, present_value = sbo_scenario_metrics(sensitivity_target)
                margin_of_safety = (present_value / ref_price - 1) * 100

                sensitivity_rows.append(
                    {
                        "P/E": f"{pe}x",
                        "Kursmål 2028": f"{sensitivity_target:.0f} NOK",
                        "Total avkastning": f"{total_return:+.0f}%",
                        "CAGR p.a.": f"{cagr:+.1f}%",
                        f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                        "Margin of safety": f"{margin_of_safety:+.0f}%",
                    }
                )

            st.dataframe(
                pd.DataFrame(sensitivity_rows),
                width="stretch",
                hide_index=True,
            )

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )


    elif selskap == "Storebrand":
        stb = info["storebrand"]
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            ["Oversikt", "Nøkkeltall", "Aksjonærer", "Nyheter", "Verdsettelse"]
        )

        with tab1:
            k1, k2, k3 = st.columns(3)
            k1.metric("Cash EPS Q2", f"{stb['q2']['cash_eps']:.2f} NOK".replace(".", ","))
            k2.metric("ROE LTM", f"{stb['q2']['roe_ltm']:.0f}%")
            k3.metric("Solvens II", f"{stb['q2']['solvency']:.0f}%")

            k4, k5, k6 = st.columns(3)
            k4.metric("AUM Q2", f"{stb['q2']['aum']:,} mrd. NOK".replace(",", " "))
            k5.metric("Combined ratio Q2", f"{stb['q2']['combined_ratio']:.1f}%".replace(".", ","))
            k6.metric("Konsernresultat Q2", f"{stb['q2']['group_profit']:,} MNOK".replace(",", " "))

            st.divider()
            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")
            q1, q2, q3 = st.columns(3)
            metric_with_yoy(q1, "Driftsresultat",
                            f"{stb['q2']['operating_profit']:,} MNOK".replace(",", " "),
                            stb["q2_yoy"]["operating_profit"])
            metric_with_yoy(q2, "Konsernresultat",
                            f"{stb['q2']['group_profit']:,} MNOK".replace(",", " "),
                            stb["q2_yoy"]["group_profit"])
            metric_with_yoy(q3, "Cash EPS",
                            f"{stb['q2']['cash_eps']:.2f}".replace(".", ","),
                            stb["q2_yoy"]["cash_eps"])

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(q4, "Forsikringsresultat",
                            f"{stb['q2']['insurance_result']:,} MNOK".replace(",", " "),
                            stb["q2_yoy"]["insurance_result"])
            metric_with_yoy(q5, "Combined ratio",
                            f"{stb['q2']['combined_ratio']:.1f}%".replace(".", ","),
                            stb["q2_yoy"]["combined_ratio"])
            metric_with_yoy(q6, "AUM",
                            f"{stb['q2']['aum']:,} mrd. NOK".replace(",", " "),
                            stb["q2_yoy"]["aum"])

            st.subheader(info.get("_ytd_label", "H1 2026"))
            h1, h2, h3 = st.columns(3)
            metric_with_yoy(h1, "Driftsresultat",
                            f"{stb['h1']['operating_profit']:,} MNOK".replace(",", " "),
                            stb["h1_yoy"]["operating_profit"])
            metric_with_yoy(h2, "Konsernresultat",
                            f"{stb['h1']['group_profit']:,} MNOK".replace(",", " "),
                            stb["h1_yoy"]["group_profit"])
            metric_with_yoy(h3, "Cash EPS",
                            f"{stb['h1']['cash_eps']:.2f}".replace(".", ","),
                            stb["h1_yoy"]["cash_eps"])

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(h4, "Forsikringsresultat",
                            f"{stb['h1']['insurance_result']:,} MNOK".replace(",", " "),
                            stb["h1_yoy"]["insurance_result"])
            metric_with_yoy(h5, "Combined ratio",
                            f"{stb['h1']['combined_ratio']:.0f}%",
                            stb["h1_yoy"]["combined_ratio"])
            metric_with_yoy(h6, "Fee- og administrasjonsinntekter",
                            f"{stb['h1']['fee_income']:,} MNOK".replace(",", " "),
                            stb["h1_yoy"]["fee_income"])

            st.caption(
                "Storebrand hadde 200% Solvens II ved utgangen av Q2. "
                "Andre tilbakekjøpstransje på 1 mrd. NOK er i gang. "
                f"Neste rapport: {stb['next_report']}."
            )

        with tab2:
            st.subheader("Årsutvikling")
            annual_df = pd.DataFrame(stb["annual"]).copy()
            for col in ["Konsernresultat", "Driftsresultat", "AUM mrd."]:
                annual_df[col] = annual_df[col].map(lambda x: f"{x:,.0f}".replace(",", " "))
            annual_df["Cash EPS"] = annual_df["Cash EPS"].map(lambda x: f"{x:.2f}".replace(".", ","))
            annual_df["Cash ROE"] = annual_df["Cash ROE"].map(lambda x: f"{x:.1f}%".replace(".", ","))
            annual_df["Solvens II"] = annual_df["Solvens II"].map(lambda x: f"{x:.0f}%")
            annual_df["Combined ratio"] = annual_df["Combined ratio"].map(lambda x: f"{x:.0f}%")
            annual_df["Utbytte"] = annual_df["Utbytte"].map(lambda x: f"{x:.2f}".replace(".", ","))
            st.dataframe(annual_df, width="stretch", hide_index=True)
            st.caption(
                "Konsernresultatet i 2024 inkluderte en gevinst på 1 047 MNOK fra salget "
                "av Storebrand Helseforsikring."
            )

            st.subheader("2028-mål og kapitalallokering")
            target_df = pd.DataFrame([
                {"KPI": "Konsernresultat 2028", "Mål": stb["targets"]["group_profit_2028"]},
                {"KPI": "ROE 2028", "Mål": stb["targets"]["roe_2028"]},
                {"KPI": "Combined ratio 2028", "Mål": stb["targets"]["combined_ratio_2028"]},
                {"KPI": "Kostnadsvekst", "Mål": stb["targets"]["cost_growth"]},
                {"KPI": "Tilbakekjøp", "Mål": stb["targets"]["capital_return"]},
            ])
            st.dataframe(target_df, width="stretch", hide_index=True)

            st.subheader("Det viktigste å følge")
            st.write(
                "• Vekst i kapital under forvaltning og netto inflow\n"
                "• Fee- og administrasjonsinntekter og kostnadskontroll\n"
                "• Combined ratio og premie-/markedsandelsvekst i skadeforsikring\n"
                "• Cash ROE og utvikling mot 17%-målet i 2028\n"
                "• Solvensgrad, utbytte og tilbakekjøp\n"
                "• Resultatbidrag og kapitalfrigjøring fra garanterte pensjoner"
            )

        with tab3:
            st.subheader("Største aksjonærer")
            sh = pd.DataFrame(stb["shareholders"]).copy()
            sh["Andel"] = sh["Andel"].map(lambda x: f"{x:.2f}%".replace(".", ","))
            st.dataframe(sh, width="stretch", hide_index=True)
            st.caption(f"Storebrands offentliggjorte forvalteroversikt per {stb['shareholders_date']}.")

        with tab4:
            st.subheader("Siste utvikling")
            st.dataframe(pd.DataFrame(stb["news"]), width="stretch", hide_index=True)
            st.info(f"Neste planlagte kvartalsrapport: {stb['next_report']}.")

        with tab5:
            st.subheader("Dynamisk verdsettelse")
            st.caption(
                "Modellen bruker Cash EPS justert for amortisering. EPS 2026E på 11,49 NOK er "
                "gjennomsnittet i Storebrands publiserte Q2-konsensus. Bear/base/bull-veksten er "
                "satt slik at 2028 EPS ligger omtrent på lavt, gjennomsnittlig og høyt konsensusnivå."
            )

            v = info["valuation"]
            ref_price = st.number_input(
                "Dagens kurs / referansekurs (NOK)", min_value=1.0,
                value=float(stb["reference_price"]), step=1.0, key="stb_ref_price"
            )

            c1, c2, c3 = st.columns(3)
            eps_2026 = c1.number_input(
                "Cash EPS 2026E", min_value=0.1, value=float(v["eps_2026"]),
                step=0.1, format="%.2f", key="stb_eps_2026"
            )
            required_return = c2.number_input(
                "Avkastningskrav", min_value=0.0, max_value=30.0,
                value=10.0, step=1.0, format="%.0f", key="stb_required_return"
            )
            c3.metric("Målår", "2028")

            st.markdown("**EPS-vekst per år**")
            render_valuation_history_context(selskap, "growth")
            g1, g2, g3 = st.columns(3)
            gb = g1.number_input("Bear vekst", value=float(v["growth_bear"]),
                                 step=1.0, format="%.0f", key="stb_gb")
            gbase = g2.number_input("Base vekst", value=float(v["growth_base"]),
                                    step=1.0, format="%.0f", key="stb_gbase")
            gbull = g3.number_input("Bull vekst", value=float(v["growth_bull"]),
                                    step=1.0, format="%.0f", key="stb_gbull")

            st.markdown("**P/E i målåret**")
            render_valuation_history_context(selskap, "pe")
            p1, p2, p3 = st.columns(3)
            peb = p1.number_input("Bear P/E", min_value=1.0, value=float(v["pe_bear"]),
                                  step=1.0, format="%.0f", key="stb_peb")
            pebase = p2.number_input("Base P/E", min_value=1.0, value=float(v["pe_base"]),
                                     step=1.0, format="%.0f", key="stb_pebase")
            pebull = p3.number_input("Bull P/E", min_value=1.0, value=float(v["pe_bull"]),
                                     step=1.0, format="%.0f", key="stb_pebull")

            eps_bear = eps_2026 * (1 + gb / 100) ** 2
            eps_base = eps_2026 * (1 + gbase / 100) ** 2
            eps_bull = eps_2026 * (1 + gbull / 100) ** 2
            target_bear = eps_bear * peb
            target_base = eps_base * pebase
            target_bull = eps_bull * pebull

            st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Cash EPS 2028E – vårt scenario", f"{eps_base:.2f}".replace(".", ","))
            buy_level = s2.number_input("Kjøpsnivå (NOK)", value=float(stb["buy_level"]),
                                        step=5.0, format="%.0f", key="stb_buy")
            sell_level = s3.number_input("Reduser/salgsnivå (NOK)", value=float(stb["sell_level"]),
                                         step=5.0, format="%.0f", key="stb_sell")
            max_pe = s4.number_input("Maks P/E underveis", value=float(stb["max_pe_underway"]),
                                     step=1.0, format="%.0f", key="stb_maxpe")

            years_to_target = 2

            def stb_scenario_metrics(target_value):
                total_return = (target_value / ref_price - 1) * 100
                cagr = ((target_value / ref_price) ** (1 / years_to_target) - 1) * 100
                present_value = target_value / ((1 + required_return / 100) ** years_to_target)
                return total_return, cagr, present_value

            bear_total, bear_cagr, bear_pv = stb_scenario_metrics(target_bear)
            base_total, base_cagr, base_pv = stb_scenario_metrics(target_base)
            bull_total, bull_cagr, bull_pv = stb_scenario_metrics(target_bull)

            bear_mos = (bear_pv / ref_price - 1) * 100
            base_mos = (base_pv / ref_price - 1) * 100
            bull_mos = (bull_pv / ref_price - 1) * 100

            st.subheader("Estimert kurs i 2028")
            r1, r2, r3 = st.columns(3)
            r1.metric("🔴 Bear", f"{target_bear:.0f} NOK")
            r2.metric("🟡 Base", f"{target_base:.0f} NOK")
            r3.metric("🟢 Bull", f"{target_bull:.0f} NOK")

            expected_dividends = stb["consensus"]["dps_2027"] + stb["consensus"]["dps_2028"]
            st.caption(
                f"I tillegg kommer forventet kontantutbytte på ca. {expected_dividends:.1f} NOK "
                "per aksje samlet for 2027–2028 etter siste publiserte konsensus. "
                "Tilbakekjøp legges ikke til separat, siden effekten over tid reflekteres i EPS per aksje."
            )

            st.subheader("Forventet avkastning fra referansekurs")
            a1, a2, a3 = st.columns(3)
            with a1:
                st.markdown("**🔴 Bear**")
                st.write(f"Kursavkastning: **{bear_total:+.0f}%**")
                st.write(f"Årlig kursavkastning (CAGR): **{bear_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bear_pv:.0f} NOK**")
            with a2:
                st.markdown("**🟡 Base**")
                st.write(f"Kursavkastning: **{base_total:+.0f}%**")
                st.write(f"Årlig kursavkastning (CAGR): **{base_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{base_pv:.0f} NOK**")
            with a3:
                st.markdown("**🟢 Bull**")
                st.write(f"Kursavkastning: **{bull_total:+.0f}%**")
                st.write(f"Årlig kursavkastning (CAGR): **{bull_cagr:+.1f}%**")
                st.write(f"Nåverdi ved {required_return:.1f}% krav: **{bull_pv:.0f} NOK**")

            base_total_with_dividend = ((target_base + expected_dividends) / ref_price - 1) * 100
            st.info(
                f"Base-scenario inkl. forventet utbytte 2027–2028 gir ca. "
                f"{base_total_with_dividend:+.0f}% samlet avkastning frem mot utgangen av 2028."
            )

            st.subheader("Margin of safety mot nåverdi")
            m1, m2, m3 = st.columns(3)
            m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
            m2.metric("🟡 Base", f"{base_mos:+.0f}%")
            m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

            st.caption(
                "Positiv margin of safety betyr at scenarioets nåverdi ligger over dagens kurs. "
                "Utbytte er ikke inkludert i nåverdien."
            )

            st.subheader("Cash EPS-scenario 2026E–2030E")
            rows = []
            for year in range(2026, 2031):
                periods = year - 2026
                rows.append({
                    "År": year,
                    "Bear EPS": eps_2026 * (1 + gb / 100) ** periods,
                    "Base EPS": eps_2026 * (1 + gbase / 100) ** periods,
                    "Bull EPS": eps_2026 * (1 + gbull / 100) ** periods,
                })
            eps_table = pd.DataFrame(rows)
            for col in ["Bear EPS", "Base EPS", "Bull EPS"]:
                eps_table[col] = eps_table[col].map(lambda x: f"{x:.2f}".replace(".", ","))
            st.dataframe(eps_table, width="stretch", hide_index=True)

            st.subheader("P/E-sensitivitet – Base Cash EPS 2028")
            sensitivity_rows = []
            for pe in [11, 12, 13, 14, 15, 16, 18]:
                target = eps_base * pe
                total_return, cagr, present_value = stb_scenario_metrics(target)
                mos = (present_value / ref_price - 1) * 100
                sensitivity_rows.append({
                    "P/E": f"{pe}x",
                    "Kursmål 2028": f"{target:.0f} NOK",
                    "Kursavkastning": f"{total_return:+.0f}%",
                    "CAGR p.a.": f"{cagr:+.1f}%",
                    f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} NOK",
                    "Margin of safety": f"{mos:+.0f}%",
                })
            st.dataframe(pd.DataFrame(sensitivity_rows), width="stretch", hide_index=True)

            st.caption(
                f"Arbeidsnivåer: kjøp/øk ≤ {buy_level:.0f} NOK; "
                f"reduser ≥ {sell_level:.0f} NOK når P/E samtidig er rundt "
                f"{max_pe:.0f}x eller høyere."
            )

    elif selskap not in ("NORBIT", "Cambi", "Kitron", "NOTE"):
        st.info(
            "Strukturen er klar. Dette selskapet fylles med faktiske data "
            "etter hvert som vi kvalitetssikrer nøkkeltallene."
        )
        st.subheader("Investeringscase")
        st.write(info["case"])

    else:
        if selskap == "NORBIT":
            norbit_report = load_norbit_reporting_data()
            info = prepare_norbit_info(info, norbit_report)
        else:
            norbit_report = None

        widget_prefix = info["ticker"].lower()
        currency = info.get("currency", "NOK")
        financial_currency = info.get("financial_currency", currency)
        million_unit = f"M{financial_currency}"
        cashflow_unit = info.get("cashflow_unit", million_unit)
        billion_unit = f"mrd. {currency}"
        financial_billion_unit = f"mrd. {financial_currency}"
        cashflow_fx_to_share_currency = info.get("cashflow_fx_to_share_currency", 1.0)
        valuation_fx_to_share_currency = info.get("valuation_fx_to_share_currency", 1.0)

        company_tab_labels = [
            "Oversikt",
            "Nøkkeltall",
            "Aksjonærer",
            "Nyheter",
            "Kontrakter",
            "Verdsettelse",
        ]
        if selskap == "NORBIT":
            company_tab_labels.append("Rapportering")

        company_tabs = st.tabs(company_tab_labels)
        tab1, tab2, tab3, tab4, tab5, tab6 = company_tabs[:6]
        tab7 = company_tabs[6] if selskap == "NORBIT" else None

        # -------------------------------------------------
        # OVERSIKT
        # -------------------------------------------------
        with tab1:
            # Selskapsnøkkeltall vises kun på Oversikt.
            k1, k2, k3 = st.columns(3)

            k1.metric(
                "Markedsverdi",
                f"{info['market_cap']:.2f} {billion_unit}".replace(".", ",")
            )
            k2.metric(
                "P/E LTM",
                f"{info['pe_ltm']:.1f}x".replace(".", ",")
            )
            if selskap == "NOTE":
                k3.metric(
                    "OCF LTM",
                    f"{info['ocf_ltm']:.0f} {cashflow_unit}"
                )
            else:
                k3.metric(
                    "FCF Yield LTM",
                    f"{info['fcf_yield']:.1f}%".replace(".", ",")
                )

            k4, k5, k6 = st.columns(3)

            k4.metric(
                "ROE LTM",
                f"{info['roe_ltm']:.1f}%".replace(".", ",")
            )
            k5.metric(
                "ROCE",
                f"{info['roce']:.1f}%".replace(".", ",")
            )
            leverage_label = (
                "Netto kontanter / EBITDA"
                if info["nibd_ebitda"] < 0
                else "Netto gjeld / EBITDA"
            )
            leverage_value = abs(info["nibd_ebitda"])

            k6.metric(
                leverage_label,
                f"{leverage_value:.1f}x".replace(".", ",")
            )

            st.divider()

            st.subheader("Investeringscase")
            st.write(info["case"])

            st.subheader(f"Siste kvartal – {info.get('_latest_period', 'Q2 2026')}")

            q1, q2, q3 = st.columns(3)
            metric_with_yoy(
                q1,
                "Omsetning",
                f"{info['q2']['revenue']:.1f} {million_unit}".replace(".", ","),
                info["q2_yoy"]["revenue"],
            )
            metric_with_yoy(
                q2,
                "OCF",
                f"{info['q2']['ocf']:.1f} {cashflow_unit}".replace(".", ","),
                info["q2_yoy"]["ocf"],
            )
            metric_with_yoy(
                q3,
                "EBIT-margin",
                f"{info['q2']['ebit_margin']:.1f}%".replace(".", ","),
                info["q2_yoy"]["ebit_margin"],
            )

            q4, q5, q6 = st.columns(3)
            metric_with_yoy(
                q4,
                "EBIT",
                f"{info['q2']['ebit']:.1f} {million_unit}".replace(".", ","),
                info["q2_yoy"]["ebit"],
            )
            metric_with_yoy(
                q5,
                "EPS",
                f"{info['q2']['eps']:.2f}".replace(".", ","),
                info["q2_yoy"]["eps"],
            )
            metric_with_yoy(
                q6,
                "CF etter investeringer" if selskap == "NOTE" else "FCF",
                f"{info['q2']['fcf']:.1f} {cashflow_unit}".replace(".", ","),
                info["q2_yoy"]["fcf"],
            )

            st.subheader(info.get("_ytd_label", "H1 2026"))

            h1, h2, h3 = st.columns(3)
            metric_with_yoy(
                h1,
                "Omsetning",
                f"{info['h1']['revenue']:,.1f} {million_unit}".replace(",", " ").replace(".", ","),
                info["h1_yoy"]["revenue"],
            )
            metric_with_yoy(
                h2,
                "OCF",
                f"{info['h1']['ocf']:.1f} {cashflow_unit}".replace(".", ","),
                info["h1_yoy"]["ocf"],
            )
            metric_with_yoy(
                h3,
                "EBIT-margin",
                f"{info['h1']['ebit_margin']:.1f}%".replace(".", ","),
                info["h1_yoy"]["ebit_margin"],
            )

            h4, h5, h6 = st.columns(3)
            metric_with_yoy(
                h4,
                "EBIT",
                f"{info['h1']['ebit']:.1f} {million_unit}".replace(".", ","),
                info["h1_yoy"]["ebit"],
            )
            metric_with_yoy(
                h5,
                "EPS",
                f"{info['h1']['eps']:.2f}".replace(".", ","),
                info["h1_yoy"]["eps"],
            )
            metric_with_yoy(
                h6,
                "CF etter investeringer" if selskap == "NOTE" else "FCF",
                f"{info['h1']['fcf']:.1f} {cashflow_unit}".replace(".", ","),
                info["h1_yoy"]["fcf"],
            )

            if "order_kpis" in info:
                st.subheader("Ordre og backlog")
                ok1, ok2, ok3, ok4 = st.columns(4)
                order_items = list(info["order_kpis"].items())
                for col, (label, value) in zip(
                    [ok1, ok2, ok3, ok4],
                    order_items
                ):
                    col.metric(label, value)

            st.subheader("Balansestyrke og kontantstrøm")
            b1, b2, b3 = st.columns(3)
            debt_label = (
                "Netto kontanter"
                if info["nibd"] < 0
                else "Netto rentebærende gjeld"
            )
            debt_value = (
                abs(info["nibd"])
                if info["nibd"] < 0
                else info["nibd"]
            )
            b1.metric(
                debt_label,
                f"{debt_value:.0f} {million_unit}"
            )
            balance_leverage_label = (
                "Netto kontanter / EBITDA"
                if info["nibd_ebitda"] < 0
                else "NIBD / EBITDA"
            )
            balance_leverage_value = abs(info["nibd_ebitda"])

            b2.metric(
                balance_leverage_label,
                f"{balance_leverage_value:.1f}x".replace(".", ",")
            )
            if selskap == "NOTE":
                b3.metric(
                    "OCF LTM",
                    f"{info['ocf_ltm']:.0f} {million_unit}"
                )
            else:
                b3.metric(
                    "FCF LTM",
                    f"{info['fcf_ltm']:.0f} {cashflow_unit}"
                )

            st.subheader("Selskapets guiding")
            for item in info["guidance"]:
                st.write(f"• {item}")

            st.subheader("Siste utvikling")
            st.success(info["latest_development"])

        # -------------------------------------------------
        # NØKKELTALL
        # -------------------------------------------------
        with tab2:
            st.subheader("Nøkkeltall – utvikling")

            key_rows = []
            for row in info["financials"]:
                key_rows.append({
                    "Periode": row["Periode"],
                    f"Omsetning ({million_unit})": row["Omsetning"],
                    "Vekst": row["Vekst"],
                    f"EBIT ({million_unit})": row["EBIT"],
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

            st.subheader("Segmentdata – Q2 2026 (sist registrert)")
            df_seg = pd.DataFrame(info["segments_q2"])
            st.dataframe(
                df_seg,
                width="stretch",
                hide_index=True
            )

            st.subheader("Kontantstrøm")

            if selskap == "NOTE":
                cf1, cf2, cf3 = st.columns(3)
                cf1.metric(
                    f"OCF {info.get('_latest_period', 'Q2 2026')}",
                    f"{info['q2']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf2.metric(
                    f"OCF {info.get('_ytd_label', 'H1 2026')}",
                    f"{info['h1']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf3.metric(
                    "OCF LTM",
                    f"{info['ocf_ltm']:.0f} {million_unit}"
                )

                cf4, cf5, cf6 = st.columns(3)
                cf4.metric(
                    "CF etter investeringer Q2",
                    f"{info['q2']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf5.metric(
                    "CF etter investeringer H1",
                    f"{info['h1']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf6.metric(
                    "OCF Yield LTM",
                    f"{info['ocf_yield_ltm']:.1f}%".replace(".", ",")
                )

                st.caption(
                    "NOTE rapporterer operasjonell kontantstrøm justert for "
                    "sammenligningsforstyrrende poster separat fra totalt kontantstrøm "
                    "etter investeringer. H1-tallet etter investeringer inkluderer "
                    "store oppkjøpsrelaterte utbetalinger."
                )
            else:
                cf1, cf2, cf3 = st.columns(3)
                cf1.metric(
                    f"FCF {info.get('_latest_period', 'Q2 2026')}",
                    f"{info['q2']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf2.metric(
                    f"FCF {info.get('_ytd_label', 'H1 2026')}",
                    f"{info['h1']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf3.metric(
                    "FCF LTM",
                    f"{info['fcf_ltm']:.0f} {cashflow_unit}"
                )

                cf4, cf5, cf6 = st.columns(3)
                cf4.metric(
                    f"OCF {info.get('_latest_period', 'Q2 2026')}",
                    f"{info['q2']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf5.metric(
                    f"OCF {info.get('_ytd_label', 'H1 2026')}",
                    f"{info['h1']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf6.metric(
                    "FCF Yield LTM",
                    f"{info['fcf_yield']:.1f}%".replace(".", ",")
                )

                st.caption(
                    "FCF = kontantstrøm fra drift minus investeringer i driftsmidler "
                    "og immaterielle eiendeler."
                )

            if info.get("cashflow_note"):
                st.caption(info["cashflow_note"])

            st.subheader("Hva vi følger videre")
            for item in info["what_follow"]:
                st.write(f"• {item}")

        # -------------------------------------------------
        # AKSJONÆRER
        # -------------------------------------------------
        with tab3:
            render_shareholder_monitor(
                info,
                key_prefix=f"{widget_prefix}_company",
            )

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
            n3.metric("Neste rapport", info["news_next_report"])

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

            st.info(info["news_auto_source"])

        # -------------------------------------------------
        # KONTRAKTER
        # -------------------------------------------------
        with tab5:
            known_contract_value = sum(
                item["Verdi (MNOK)"]
                for item in info["contracts"]
                if isinstance(item["Verdi (MNOK)"], (int, float))
            )

            st.subheader("Kontrakter og anbud")

            st.metric(
                info["contract_value_metric_label"],
                f"{known_contract_value:,.0f} {million_unit}".replace(",", " ")
            )
            st.caption(info["contract_value_caption"])

            st.subheader("Inngåtte / annonserte kontrakter")
            df_contracts = pd.DataFrame(info["contracts"]).copy()
            if "Verdi (MNOK)" in df_contracts.columns:
                raw_value_col = "Verdi (MNOK)"
                value_col = f"Verdi ({million_unit})"
                formatted_values = df_contracts[raw_value_col].map(
                    lambda x: "–" if pd.isna(x) else f"{x:,.0f}".replace(",", " ")
                )
                if value_col == raw_value_col:
                    df_contracts[raw_value_col] = formatted_values
                else:
                    df_contracts[value_col] = formatted_values
                    df_contracts = df_contracts.drop(columns=[raw_value_col])

            df_contracts = df_contracts.fillna("–")
            contract_display = df_contracts.copy()
            for col in contract_display.columns:
                contract_display[col] = contract_display[col].map(
                    lambda x: "–" if pd.isna(x) else str(x)
                )

            st.dataframe(
                contract_display,
                width="stretch",
                hide_index=True
            )

            st.subheader("Potensielle kontrakter og anbud")
            df_opp = pd.DataFrame(info["opportunities"]).copy()

            # Automatisk kontraktsmonitor kan overstyre faktiske status-/datofelter,
            # men ikke våre analysefelt som prioritet, sannsynlighet eller kommentar.
            for auto in contract_monitor.values():
                if auto.get("company") != selskap:
                    continue
                match_text = auto.get("opportunity_match") or auto.get("title")
                if not match_text:
                    continue
                mask = df_opp["Mulighet"].astype(str).str.contains(
                    re.escape(match_text), case=False, na=False, regex=True
                )
                if mask.any():
                    if auto.get("status"):
                        df_opp.loc[mask, "Status"] = auto["status"]
                    if auto.get("next_date"):
                        df_opp.loc[mask, "Neste dato"] = auto["next_date"]
                    if auto.get("date_type"):
                        df_opp.loc[mask, "Dato-type"] = auto["date_type"]
                    if auto.get("last_checked"):
                        df_opp.loc[mask, "Sist kontrollert"] = auto["last_checked"]
                    if auto.get("last_updated"):
                        df_opp.loc[mask, "Sist oppdatert"] = auto["last_updated"]
                    if auto.get("source_label"):
                        df_opp.loc[mask, "Kilde"] = auto["source_label"]

            # Felter som kan fylles automatisk etter hvert som overvåkningen bygges ut.
            for optional_col in ["Neste dato", "Dato-type", "Sist kontrollert", "Kilde"]:
                if optional_col not in df_opp.columns:
                    df_opp[optional_col] = "–"
                else:
                    df_opp[optional_col] = df_opp[optional_col].fillna("–")

            value_col = f"Est. verdi ({million_unit})"
            if "Est. verdi (MNOK)" in df_opp.columns:
                raw_est_col = "Est. verdi (MNOK)"
                formatted_est = df_opp[raw_est_col].map(
                    lambda x: "–" if pd.isna(x) else f"{x:,.0f}".replace(",", " ")
                )
                if value_col == raw_est_col:
                    df_opp[raw_est_col] = formatted_est
                else:
                    df_opp[value_col] = formatted_est
                    df_opp = df_opp.drop(columns=[raw_est_col])

            df_opp = df_opp.fillna("–")

            opp_cols = [
                "Prioritet",
                "Mulighet",
                "Sannsynlighet",
                value_col,
                "Status",
                "Neste dato",
                "Dato-type",
                "Sist oppdatert",
                "Sist kontrollert",
                "Kilde",
                "Kommentar",
            ]

            opp_display = df_opp[opp_cols].copy()
            for col in opp_display.columns:
                opp_display[col] = opp_display[col].map(
                    lambda x: "–" if pd.isna(x) else str(x)
                )

            st.dataframe(
                opp_display,
                width="stretch",
                hide_index=True
            )

            st.caption(
                "Neste dato er offentlig kjent frist eller forventet beslutningsdato. "
                "Når kun tilbudsfrist er kjent, vises den – ikke en antatt award-dato. "
                "Sist kontrollert viser når kilden sist ble sjekket; Sist oppdatert endres "
                "bare når selve saken har fått ny informasjon."
            )

            st.warning(
                "Potensielle kontrakter/anbud er vår analyse, ikke annonserte ordre. "
                "Estimert verdi står tom der vi ikke har et forsvarlig offentlig anslag."
            )

        # -------------------------------------------------
        # VERDSETTELSE
        # -------------------------------------------------
        with tab6:
            if selskap == "Cambi" and info["valuation"].get("use_direct_estimates", False):
                st.subheader("Dynamisk verdsettelse – direkte estimater")

                st.caption(
                    "For Cambi bruker vi direkte EPS-estimater for 2026E–2028E i stedet "
                    "for å vokse EPS mekanisk fra 2026. Det passer bedre når 2026 er et "
                    "svakt prosjektår samtidig som ordreboken er høy."
                )

                top1, top2 = st.columns(2)

                reference_price = top1.number_input(
                    f"Dagens kurs / referansekurs ({currency})",
                    min_value=1.0,
                    value=float(info["valuation"]["reference_price"]),
                    step=0.5,
                    key=f"{widget_prefix}_reference_price_direct"
                )

                required_return = top2.number_input(
                    "Avkastningskrav",
                    min_value=0.0,
                    max_value=30.0,
                    value=float(info["valuation"]["required_return"]),
                    step=0.5,
                    format="%.1f",
                    key=f"{widget_prefix}_required_return_direct"
                )

                st.markdown("**Scenarioforutsetninger**")

                s1, s2, s3 = st.columns(3)

                with s1:
                    st.markdown("### 🔴 Bear")
                    bear_eps_2026 = st.number_input(
                        "EPS 2026E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2026_bear"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bear_eps_2026"
                    )
                    bear_rev_2027 = st.number_input(
                        f"Omsetning 2027E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2027_bear"]),
                        step=50.0,
                        key="cambi_bear_rev_2027"
                    )
                    bear_margin_2027 = st.number_input(
                        "EBIT-margin 2027E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2027_bear"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_bear_margin_2027"
                    )
                    bear_eps_2027 = st.number_input(
                        "EPS 2027E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2027_bear"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bear_eps_2027"
                    )
                    bear_rev_2028 = st.number_input(
                        f"Omsetning 2028E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2028_bear"]),
                        step=50.0,
                        key="cambi_bear_rev_2028"
                    )
                    bear_margin_2028 = st.number_input(
                        "EBIT-margin 2028E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2028_bear"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_bear_margin_2028"
                    )
                    bear_eps_2028 = st.number_input(
                        "EPS 2028E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2028_bear"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bear_eps_2028"
                    )
                    pe_bear = st.number_input(
                        "P/E 2028",
                        min_value=5.0,
                        max_value=40.0,
                        value=float(info["valuation"]["pe_bear"]),
                        step=1.0,
                        key="cambi_bear_pe_2028"
                    )

                with s2:
                    st.markdown("### 🟡 Base")
                    base_eps_2026 = st.number_input(
                        "EPS 2026E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2026_base"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_base_eps_2026"
                    )
                    base_rev_2027 = st.number_input(
                        f"Omsetning 2027E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2027_base"]),
                        step=50.0,
                        key="cambi_base_rev_2027"
                    )
                    base_margin_2027 = st.number_input(
                        "EBIT-margin 2027E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2027_base"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_base_margin_2027"
                    )
                    base_eps_2027 = st.number_input(
                        "EPS 2027E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2027_base"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_base_eps_2027"
                    )
                    base_rev_2028 = st.number_input(
                        f"Omsetning 2028E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2028_base"]),
                        step=50.0,
                        key="cambi_base_rev_2028"
                    )
                    base_margin_2028 = st.number_input(
                        "EBIT-margin 2028E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2028_base"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_base_margin_2028"
                    )
                    base_eps_2028 = st.number_input(
                        "EPS 2028E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2028_base"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_base_eps_2028"
                    )
                    pe_base = st.number_input(
                        "P/E 2028",
                        min_value=5.0,
                        max_value=40.0,
                        value=float(info["valuation"]["pe_base"]),
                        step=1.0,
                        key="cambi_base_pe_2028"
                    )

                with s3:
                    st.markdown("### 🟢 Bull")
                    bull_eps_2026 = st.number_input(
                        "EPS 2026E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2026_bull"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bull_eps_2026"
                    )
                    bull_rev_2027 = st.number_input(
                        f"Omsetning 2027E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2027_bull"]),
                        step=50.0,
                        key="cambi_bull_rev_2027"
                    )
                    bull_margin_2027 = st.number_input(
                        "EBIT-margin 2027E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2027_bull"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_bull_margin_2027"
                    )
                    bull_eps_2027 = st.number_input(
                        "EPS 2027E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2027_bull"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bull_eps_2027"
                    )
                    bull_rev_2028 = st.number_input(
                        f"Omsetning 2028E ({million_unit})",
                        min_value=100.0,
                        value=float(info["valuation"]["cambi_revenue_2028_bull"]),
                        step=50.0,
                        key="cambi_bull_rev_2028"
                    )
                    bull_margin_2028 = st.number_input(
                        "EBIT-margin 2028E",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(info["valuation"]["cambi_margin_2028_bull"]),
                        step=0.5,
                        format="%.1f",
                        key="cambi_bull_margin_2028"
                    )
                    bull_eps_2028 = st.number_input(
                        "EPS 2028E",
                        min_value=0.0,
                        value=float(info["valuation"]["cambi_eps_2028_bull"]),
                        step=0.05,
                        format="%.2f",
                        key="cambi_bull_eps_2028"
                    )
                    pe_bull = st.number_input(
                        "P/E 2028",
                        min_value=5.0,
                        max_value=50.0,
                        value=float(info["valuation"]["pe_bull"]),
                        step=1.0,
                        key="cambi_bull_pe_2028"
                    )

                years_to_target = 2

                bear_value = bear_eps_2028 * pe_bear
                base_value = base_eps_2028 * pe_base
                bull_value = bull_eps_2028 * pe_bull

                def scenario_metrics(target_value):
                    total_return = (target_value / reference_price - 1) * 100
                    cagr = (
                        (target_value / reference_price) ** (1 / years_to_target) - 1
                    ) * 100
                    present_value = target_value / (
                        (1 + required_return / 100) ** years_to_target
                    )
                    return total_return, cagr, present_value

                bear_total, bear_cagr, bear_pv = scenario_metrics(bear_value)
                base_total, base_cagr, base_pv = scenario_metrics(base_value)
                bull_total, bull_cagr, bull_pv = scenario_metrics(bull_value)

                bear_mos = (bear_pv / reference_price - 1) * 100
                base_mos = (base_pv / reference_price - 1) * 100
                bull_mos = (bull_pv / reference_price - 1) * 100

                st.subheader("Estimert kurs i 2028")

                v1, v2, v3 = st.columns(3)
                v1.metric("🔴 Bear", f"{bear_value:.0f} {currency}")
                v2.metric("🟡 Base", f"{base_value:.0f} {currency}")
                v3.metric("🟢 Bull", f"{bull_value:.0f} {currency}")

                st.subheader("Forventet avkastning fra referansekurs")

                r1, r2, r3 = st.columns(3)

                with r1:
                    st.markdown("**🔴 Bear**")
                    st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{bear_pv:.0f} {currency}**"
                    )

                with r2:
                    st.markdown("**🟡 Base**")
                    st.write(f"Total avkastning: **{base_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{base_pv:.0f} {currency}**"
                    )

                with r3:
                    st.markdown("**🟢 Bull**")
                    st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{bull_pv:.0f} {currency}**"
                    )

                st.subheader("Margin of safety mot nåverdi")
                m1, m2, m3 = st.columns(3)
                m1.metric("🔴 Bear", f"{bear_mos:+.0f}%")
                m2.metric("🟡 Base", f"{base_mos:+.0f}%")
                m3.metric("🟢 Bull", f"{bull_mos:+.0f}%")

                st.subheader("Scenario – drift og EPS")

                scenario_table = pd.DataFrame(
                    [
                        {
                            "Scenario": "Bear",
                            "EPS 2026E": bear_eps_2026,
                            "Omsetning 2027E": bear_rev_2027,
                            "EBIT-margin 2027E": bear_margin_2027,
                            "EPS 2027E": bear_eps_2027,
                            "Omsetning 2028E": bear_rev_2028,
                            "EBIT-margin 2028E": bear_margin_2028,
                            "EPS 2028E": bear_eps_2028,
                            "P/E 2028": pe_bear,
                            "Kursmål 2028": bear_value,
                        },
                        {
                            "Scenario": "Base",
                            "EPS 2026E": base_eps_2026,
                            "Omsetning 2027E": base_rev_2027,
                            "EBIT-margin 2027E": base_margin_2027,
                            "EPS 2027E": base_eps_2027,
                            "Omsetning 2028E": base_rev_2028,
                            "EBIT-margin 2028E": base_margin_2028,
                            "EPS 2028E": base_eps_2028,
                            "P/E 2028": pe_base,
                            "Kursmål 2028": base_value,
                        },
                        {
                            "Scenario": "Bull",
                            "EPS 2026E": bull_eps_2026,
                            "Omsetning 2027E": bull_rev_2027,
                            "EBIT-margin 2027E": bull_margin_2027,
                            "EPS 2027E": bull_eps_2027,
                            "Omsetning 2028E": bull_rev_2028,
                            "EBIT-margin 2028E": bull_margin_2028,
                            "EPS 2028E": bull_eps_2028,
                            "P/E 2028": pe_bull,
                            "Kursmål 2028": bull_value,
                        },
                    ]
                )

                display_scenarios = scenario_table.copy()

                for col in ["EPS 2026E", "EPS 2027E", "EPS 2028E"]:
                    display_scenarios[col] = display_scenarios[col].map(
                        lambda x: f"{x:.2f}".replace(".", ",")
                    )

                for col in ["EBIT-margin 2027E", "EBIT-margin 2028E"]:
                    display_scenarios[col] = display_scenarios[col].map(
                        lambda x: f"{x:.1f}%".replace(".", ",")
                    )

                for col in ["Omsetning 2027E", "Omsetning 2028E"]:
                    display_scenarios[col] = display_scenarios[col].map(
                        lambda x: f"{x:,.0f}".replace(",", " ")
                    )

                display_scenarios["P/E 2028"] = display_scenarios["P/E 2028"].map(
                    lambda x: f"{x:.0f}x"
                )
                display_scenarios["Kursmål 2028"] = display_scenarios[
                    "Kursmål 2028"
                ].map(lambda x: f"{x:.0f} NOK")

                st.dataframe(
                    display_scenarios,
                    width="stretch",
                    hide_index=True
                )

                st.caption(
                    "Direkte EPS-estimater gjør at Cambi kan normaliseres raskere enn "
                    "en mekanisk CAGR-modell. Omsetning og EBIT-margin vises ved siden "
                    "av EPS for å kontrollere at resultatestimatene henger sammen med driften."
                )

                st.subheader("P/E-sensitivitet – Base EPS 2028")

                pe_levels = [14, 16, 18, 20, 22, 24, 26]
                sensitivity_rows = []

                for pe in pe_levels:
                    target_value = base_eps_2028 * pe
                    total_return, cagr, present_value = scenario_metrics(target_value)
                    margin_of_safety = (
                        present_value / reference_price - 1
                    ) * 100

                    sensitivity_rows.append(
                        {
                            "P/E": f"{pe}x",
                            "Kursmål 2028": f"{target_value:.0f} NOK",
                            "Total avkastning": f"{total_return:+.0f}%",
                            "CAGR p.a.": f"{cagr:+.1f}%",
                            f"Nåverdi @ {required_return:.1f}%": (
                                f"{present_value:.0f} {currency}"
                            ),
                            "Margin of safety": f"{margin_of_safety:+.0f}%",
                        }
                    )

                st.dataframe(
                    pd.DataFrame(sensitivity_rows),
                    width="stretch",
                    hide_index=True
                )

                st.info(
                    "Cambi har store prosjektvariasjoner mellom kvartaler. "
                    "P/E LTM bør derfor tolkes med forsiktighet når 2026-resultatet "
                    "er midlertidig svakt."
                )

            else:
                st.subheader("Dynamisk verdsettelse")

                st.caption(
                    "Modellen estimerer EPS frem til valgt målår og multipliserer med "
                    "en P/E-multippel. Deretter beregnes total avkastning, årlig avkastning "
                    "(CAGR) og nåverdi basert på valgt avkastningskrav."
                )

                with st.expander("Forutsetninger", expanded=True):
                    a1, a2, a3, a4 = st.columns(4)

                    reference_price = a1.number_input(
                        "Dagens kurs",
                        min_value=1.0,
                        value=float(info["valuation"]["reference_price"]),
                        step=1.0,
                        key=f"{widget_prefix}_reference_price"
                    )

                    eps_2026 = a2.number_input(
                        "EPS 2026E",
                        min_value=0.1,
                        value=float(info["valuation"]["eps_2026"]),
                        step=0.1,
                        key=f"{widget_prefix}_eps_2026"
                    )

                    target_year = a3.selectbox(
                        "Målår",
                        [2028, 2029, 2030],
                        index=[2028, 2029, 2030].index(info["valuation"]["target_year"]),
                        key=f"{widget_prefix}_target_year"
                    )

                    required_return = a4.number_input(
                        "Avkastningskrav",
                        min_value=0.0,
                        max_value=30.0,
                        value=float(info["valuation"]["required_return"]),
                        step=0.5,
                        format="%.1f",
                        key=f"{widget_prefix}_required_return"
                    )

                    st.markdown("**EPS-vekst per år**")
                    render_valuation_history_context(selskap, "growth")
                    g1, g2, g3 = st.columns(3)
                    growth_bear = g1.number_input(
                        "Bear vekst",
                        min_value=-20.0,
                        max_value=100.0,
                        value=float(round(info["valuation"]["growth_bear"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_growth_bear"
                    )
                    growth_base = g2.number_input(
                        "Base vekst",
                        min_value=-20.0,
                        max_value=100.0,
                        value=float(round(info["valuation"]["growth_base"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_growth_base"
                    )
                    growth_bull = g3.number_input(
                        "Bull vekst",
                        min_value=-20.0,
                        max_value=100.0,
                        value=float(round(info["valuation"]["growth_bull"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_growth_bull"
                    )

                    st.markdown("**P/E i målåret**")
                    render_valuation_history_context(selskap, "pe")
                    p1, p2, p3 = st.columns(3)
                    pe_bear = p1.number_input(
                        "Bear P/E",
                        min_value=5.0,
                        max_value=50.0,
                        value=float(round(info["valuation"]["pe_bear"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_pe_bear"
                    )
                    pe_base = p2.number_input(
                        "Base P/E",
                        min_value=5.0,
                        max_value=50.0,
                        value=float(round(info["valuation"]["pe_base"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_pe_base"
                    )
                    pe_bull = p3.number_input(
                        "Bull P/E",
                        min_value=5.0,
                        max_value=60.0,
                        value=float(round(info["valuation"]["pe_bull"])),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_pe_bull"
                    )

                    # Egne arbeidsnivåer på vei mot 2028.
                    # Disse endrer ikke selve bear/base/bull-verdsettelsen over.
                    st.markdown("**Kjøps-/salgsnivå på vei mot 2028**")
                    strategy_eps_2028_default = (
                        eps_2026 * (1 + growth_base / 100) ** 2
                    )
                    strategy_base_value_2028 = strategy_eps_2028_default * pe_base

                    s1, s2, s3, s4 = st.columns(4)

                    strategy_eps_2028 = float(strategy_eps_2028_default)
                    s1.metric(
                        "EPS 2028E – vårt scenario",
                        f"{strategy_eps_2028:.2f}".replace(".", ",")
                    )

                    buy_level = s2.number_input(
                        f"Kjøpsnivå ({currency})",
                        min_value=0.0,
                        value=float(round(info["valuation"].get(
                            "buy_level",
                            reference_price * 0.90
                        ))),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_buy_level"
                    )

                    sell_level = s3.number_input(
                        f"Reduser/salgsnivå ({currency})",
                        min_value=0.0,
                        value=float(round(info["valuation"].get(
                            "sell_level",
                            strategy_base_value_2028 * 1.30
                        ))),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_sell_level"
                    )

                    max_pe_underway = s4.number_input(
                        "Maks P/E underveis",
                        min_value=5.0,
                        max_value=100.0,
                        value=float(round(info["valuation"].get(
                            "max_pe_underway",
                            pe_bull + 15.0
                        ))),
                        step=1.0,
                        format="%.0f",
                        key=f"{widget_prefix}_max_pe_underway"
                    )

                    buy_pe_2028 = buy_level / strategy_eps_2028 if strategy_eps_2028 > 0 else 0.0
                    sell_pe_2028 = sell_level / strategy_eps_2028 if strategy_eps_2028 > 0 else 0.0

                    st.caption(
                        f"Arbeidsnivåer: kjøp/øk ved kurs ≤ {buy_level:.0f} {currency}. "
                        f"Reduser deler av beholdningen ved kurs ≥ {sell_level:.0f} {currency} "
                        f"når P/E samtidig er rundt {max_pe_underway:.0f}x eller høyere. "
                        f"Med vårt beregnede EPS 2028E på {strategy_eps_2028:.2f} tilsvarer nivåene "
                        f"ca. {buy_pe_2028:.1f}x / {sell_pe_2028:.1f}x mot 2028E EPS."
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

                bear_mos = (bear_pv / reference_price - 1) * 100
                base_mos = (base_pv / reference_price - 1) * 100
                bull_mos = (bull_pv / reference_price - 1) * 100

                st.subheader(f"Estimert kurs i {target_year}")

                v1, v2, v3 = st.columns(3)
                v1.metric("🔴 Bear", f"{bear_value:.0f} {currency}")
                v2.metric("🟡 Base", f"{base_value:.0f} {currency}")
                v3.metric("🟢 Bull", f"{bull_value:.0f} {currency}")

                st.subheader("Forventet avkastning fra referansekurs")

                r1, r2, r3 = st.columns(3)

                with r1:
                    st.markdown("**🔴 Bear**")
                    st.write(f"Total avkastning: **{bear_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{bear_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{bear_pv:.0f} {currency}**"
                    )

                with r2:
                    st.markdown("**🟡 Base**")
                    st.write(f"Total avkastning: **{base_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{base_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{base_pv:.0f} {currency}**"
                    )

                with r3:
                    st.markdown("**🟢 Bull**")
                    st.write(f"Total avkastning: **{bull_total:+.0f}%**")
                    st.write(f"Årlig avkastning (CAGR): **{bull_cagr:+.1f}%**")
                    st.write(
                        f"Nåverdi ved {required_return:.1f}% krav: "
                        f"**{bull_pv:.0f} {currency}**"
                    )

                st.caption(
                    "Nåverdi er kursmålet i målåret diskontert tilbake til 2026 med valgt "
                    "avkastningskrav. Hvis nåverdien ligger over referansekursen, tilsier "
                    "modellen at scenarioet gir mer enn avkastningskravet."
                )

                st.subheader("Margin of safety mot nåverdi")

                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "🔴 Bear",
                    f"{bear_mos:+.0f}%",
                    help="Nåverdi i bear-scenario relativt til dagens kurs / referansekurs."
                )
                m2.metric(
                    "🟡 Base",
                    f"{base_mos:+.0f}%",
                    help="Nåverdi i base-scenario relativt til dagens kurs / referansekurs."
                )
                m3.metric(
                    "🟢 Bull",
                    f"{bull_mos:+.0f}%",
                    help="Nåverdi i bull-scenario relativt til dagens kurs / referansekurs."
                )

                st.caption(
                    "Positiv margin of safety betyr at scenarioets nåverdi ligger over "
                    "dagens kurs / referansekurs. Negativ margin betyr at kursen ligger "
                    "over scenarioets nåverdi."
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

                    margin_of_safety = (present_value / reference_price - 1) * 100

                    sensitivity_rows.append(
                        {
                            "P/E": f"{pe}x",
                            f"Kursmål {target_year}": f"{target_value:.0f} NOK",
                            "Total avkastning": f"{total_return:+.0f}%",
                            "CAGR p.a.": f"{cagr:+.1f}%",
                            f"Nåverdi @ {required_return:.1f}%": f"{present_value:.0f} {currency}",
                            "Margin of safety": f"{margin_of_safety:+.0f}%",
                        }
                    )

                sensitivity = pd.DataFrame(sensitivity_rows)

                st.dataframe(
                    sensitivity,
                    width="stretch",
                    hide_index=True
                )

            st.subheader("Kontantstrømbasert sjekk")

            f1, f2, f3 = st.columns(3)

            if selskap == "NOTE":
                ocf_per_share = (
                    info["ocf_ltm"] * 1_000_000 / info["shares_outstanding"]
                )
                f1.metric(
                    "OCF per aksje LTM",
                    f"{ocf_per_share:.2f} {currency}".replace(".", ",")
                )
                f2.metric(
                    "OCF Yield LTM",
                    f"{info['ocf_yield_ltm']:.1f}%".replace(".", ",")
                )
            else:
                fcf_per_share = (
                    info["fcf_ltm"] * 1_000_000 / info["shares_outstanding"]
                    * cashflow_fx_to_share_currency
                )
                f1.metric(
                    "FCF per aksje LTM",
                    f"{fcf_per_share:.2f} {currency}".replace(".", ",")
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

            st.divider()
            st.subheader("Enkel DCF-modell")

            st.caption(
                "DCF-en er en transparent arbeidsmodell. Du setter omsetning i 2026E "
                "og mål for 2030E. Programmet beregner nødvendig CAGR automatisk. "
                "EBIT-marginen utvikles gradvis fra 2026-nivå til valgt 2030-nivå."
            )

            with st.expander("DCF-forutsetninger", expanded=True):
                d1, d2, d3, d4 = st.columns(4)

                dcf_revenue_2026 = d1.number_input(
                    f"Omsetning 2026E ({million_unit})",
                    min_value=500.0,
                    value=float(info["valuation"]["dcf_revenue_2026"]),
                    step=50.0,
                    key=f"{widget_prefix}_dcf_revenue_2026"
                )

                dcf_revenue_2030 = d2.number_input(
                    f"Omsetning 2030E ({million_unit})",
                    min_value=500.0,
                    value=float(info["valuation"]["dcf_revenue_2030"]),
                    step=100.0,
                    key=f"{widget_prefix}_dcf_revenue_2030"
                )

                dcf_ebit_margin_2026 = d3.number_input(
                    "EBIT-margin 2026E",
                    min_value=5.0,
                    max_value=40.0,
                    value=float(info["valuation"]["dcf_ebit_margin_2026"]),
                    step=0.5,
                    format="%.1f",
                    key=f"{widget_prefix}_dcf_ebit_margin_2026"
                )

                dcf_ebit_margin_2030 = d4.number_input(
                    "EBIT-margin 2030E",
                    min_value=5.0,
                    max_value=40.0,
                    value=float(info["valuation"]["dcf_ebit_margin_2030"]),
                    step=0.5,
                    format="%.1f",
                    key=f"{widget_prefix}_dcf_ebit_margin_2030"
                )

                d5, d6, d7, d8 = st.columns(4)

                dcf_tax_rate = d5.number_input(
                    "Skattesats",
                    min_value=0.0,
                    max_value=40.0,
                    value=float(info["valuation"]["dcf_tax_rate"]),
                    step=0.5,
                    format="%.1f",
                    key=f"{widget_prefix}_dcf_tax_rate"
                )

                dcf_conversion = d6.number_input(
                    "FCF-konvertering av NOPAT",
                    min_value=20.0,
                    max_value=120.0,
                    value=float(info["valuation"]["dcf_conversion"]),
                    step=1.0,
                    format="%.1f",
                    help="Andel av EBIT etter skatt som omdannes til fri kontantstrøm.",
                    key=f"{widget_prefix}_dcf_conversion"
                )

                dcf_wacc = d7.number_input(
                    "WACC / diskonteringsrente",
                    min_value=4.0,
                    max_value=20.0,
                    value=float(info["valuation"]["dcf_wacc"]),
                    step=0.5,
                    format="%.1f",
                    key=f"{widget_prefix}_dcf_wacc"
                )

                dcf_terminal_growth = d8.number_input(
                    "Terminalvekst",
                    min_value=0.0,
                    max_value=6.0,
                    value=float(info["valuation"]["dcf_terminal_growth"]),
                    step=0.25,
                    format="%.2f",
                    key=f"{widget_prefix}_dcf_terminal_growth"
                )

            if dcf_revenue_2030 <= 0 or dcf_revenue_2026 <= 0:
                st.error("Omsetning må være høyere enn 0.")
            elif dcf_wacc <= dcf_terminal_growth:
                st.error("WACC må være høyere enn terminalveksten.")
            else:
                revenue_cagr = (
                    (dcf_revenue_2030 / dcf_revenue_2026) ** (1 / 4) - 1
                ) * 100

                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Implisitt omsetnings-CAGR 2026–2030",
                    f"{revenue_cagr:.1f}%".replace(".", ",")
                )
                c2.metric(
                    "EBIT-margin 2026E",
                    f"{dcf_ebit_margin_2026:.1f}%".replace(".", ",")
                )
                c3.metric(
                    "EBIT-margin 2030E",
                    f"{dcf_ebit_margin_2030:.1f}%".replace(".", ",")
                )

                forecast_rows = []
                pv_fcff_sum = 0.0

                for year in range(2027, 2031):
                    periods = year - 2026

                    revenue = dcf_revenue_2026 * (
                        1 + revenue_cagr / 100
                    ) ** periods

                    margin = dcf_ebit_margin_2026 + (
                        dcf_ebit_margin_2030 - dcf_ebit_margin_2026
                    ) * (periods / 4)

                    ebit = revenue * margin / 100
                    nopat = ebit * (1 - dcf_tax_rate / 100)
                    fcff = nopat * dcf_conversion / 100

                    discount_factor = (1 + dcf_wacc / 100) ** periods
                    pv_fcff = fcff / discount_factor
                    pv_fcff_sum += pv_fcff

                    forecast_rows.append(
                        {
                            "År": year,
                            "Omsetning (MNOK)": revenue,
                            "EBIT-margin": margin,
                            "EBIT (MNOK)": ebit,
                            "NOPAT (MNOK)": nopat,
                            "FCFF (MNOK)": fcff,
                            "Nåverdi FCFF": pv_fcff,
                        }
                    )

                terminal_fcff = forecast_rows[-1]["FCFF (MNOK)"] * (
                    1 + dcf_terminal_growth / 100
                )

                terminal_value = terminal_fcff / (
                    dcf_wacc / 100 - dcf_terminal_growth / 100
                )

                pv_terminal = terminal_value / (
                    (1 + dcf_wacc / 100) ** 4
                )

                enterprise_value = pv_fcff_sum + pv_terminal
                equity_value = enterprise_value - info["nibd"]

                dcf_value_per_share = (
                    equity_value * 1_000_000 / info["shares_outstanding"]
                    * valuation_fx_to_share_currency
                )

                dcf_mos = (
                    dcf_value_per_share / reference_price - 1
                ) * 100

                terminal_share = (
                    pv_terminal / enterprise_value * 100
                    if enterprise_value != 0
                    else 0
                )

                x1, x2, x3, x4 = st.columns(4)

                x1.metric(
                    "DCF-verdi per aksje",
                    f"{dcf_value_per_share:.0f} {currency}"
                )

                x2.metric(
                    "Margin of safety",
                    f"{dcf_mos:+.0f}%"
                )

                x3.metric(
                    "Enterprise value",
                    f"{enterprise_value / 1000:.2f} {financial_billion_unit}".replace(".", ",")
                )

                x4.metric(
                    "Terminalverdi av EV",
                    f"{terminal_share:.0f}%"
                )

                dcf_table = pd.DataFrame(forecast_rows).copy()

                dcf_table["EBIT-margin"] = dcf_table["EBIT-margin"].map(
                    lambda x: f"{x:.1f}%".replace(".", ",")
                )

                for col in [
                    "Omsetning (MNOK)",
                    "EBIT (MNOK)",
                    "NOPAT (MNOK)",
                    "FCFF (MNOK)",
                    "Nåverdi FCFF",
                ]:
                    dcf_table[col] = dcf_table[col].map(
                        lambda x: f"{x:,.0f}".replace(",", " ")
                    )

                dcf_display = dcf_table.rename(
                    columns={
                        "Omsetning (MNOK)": f"Omsetning ({million_unit})",
                        "EBIT (MNOK)": f"EBIT ({million_unit})",
                        "NOPAT (MNOK)": f"NOPAT ({million_unit})",
                        "FCFF (MNOK)": f"FCFF ({million_unit})",
                    }
                )

                st.dataframe(
                    dcf_display,
                    width="stretch",
                    hide_index=True
                )

                st.subheader("DCF-sensitivitet")

                wacc_levels = [
                    max(4.0, dcf_wacc - 2.0),
                    max(4.0, dcf_wacc - 1.0),
                    dcf_wacc,
                    dcf_wacc + 1.0,
                    dcf_wacc + 2.0,
                ]

                growth_levels = [
                    max(0.0, dcf_terminal_growth - 1.0),
                    max(0.0, dcf_terminal_growth - 0.5),
                    dcf_terminal_growth,
                    dcf_terminal_growth + 0.5,
                    dcf_terminal_growth + 1.0,
                ]

                sensitivity_rows = []
                base_fcff_2030 = forecast_rows[-1]["FCFF (MNOK)"]

                for wacc in wacc_levels:
                    row = {"WACC": f"{wacc:.1f}%".replace(".", ",")}

                    for tg in growth_levels:
                        if wacc <= tg:
                            row[f"g {tg:.1f}%".replace(".", ",")] = "-"
                            continue

                        tv_fcff = base_fcff_2030 * (1 + tg / 100)

                        tv = tv_fcff / (
                            wacc / 100 - tg / 100
                        )

                        pv_explicit = 0.0

                        for item in forecast_rows:
                            year = item["År"]

                            pv_explicit += item["FCFF (MNOK)"] / (
                                (1 + wacc / 100) ** (year - 2026)
                            )

                        pv_tv = tv / (
                            (1 + wacc / 100) ** 4
                        )

                        ev = pv_explicit + pv_tv
                        eq = ev - info["nibd"]

                        per_share = (
                            eq * 1_000_000 / info["shares_outstanding"]
                            * valuation_fx_to_share_currency
                        )

                        row[f"g {tg:.1f}%".replace(".", ",")] = (
                            f"{per_share:.0f} {currency}"
                        )

                    sensitivity_rows.append(row)

                st.dataframe(
                    pd.DataFrame(sensitivity_rows),
                    width="stretch",
                    hide_index=True
                )

                st.caption(
                    "Omsetnings-CAGR beregnes automatisk fra 2026E til 2030E. "
                    "EBIT-marginen interpoleres lineært mellom valgt 2026- og 2030-margin. "
                    "DCF er særlig følsom for WACC, terminalvekst og FCF-konvertering, "
                    "og bør brukes sammen med P/E-verdsettelsen."
                )

        # -------------------------------------------------
        # RAPPORTERING – NORBIT TEST MED MANUELL INNLEGGING
        # -------------------------------------------------
        if tab7 is not None:
            with tab7:
                report = load_norbit_reporting_data()

                st.subheader("Rapportering")
                st.caption(
                    "NORBIT-test: rapporterte års- og kvartalstall samles i én datakilde. "
                    "Når et kvartal lagres, brukes tallene også på Oversikt og Nøkkeltall. "
                    "Bear/base/bull i Verdsettelse beholdes som egne arbeidsestimater."
                )

                quarterly_sorted = sorted(report.get("quarterly", []), key=_quarter_sort_key)
                latest = quarterly_sorted[-1]
                latest_period = latest.get("Periode", "Siste kvartal")
                r1, r2, r3, r4 = st.columns(4)
                yoy = latest.get("Vekst YoY")
                r1.metric(
                    f"Omsetning {latest_period}",
                    f"{float(latest.get('Omsetning') or 0):.1f} MNOK".replace(".", ","),
                    "" if yoy is None else f"{float(yoy):+.0f}% YoY",
                )
                r2.metric(f"EBIT {latest_period}", f"{float(latest.get('EBIT') or 0):.1f} MNOK".replace(".", ","))
                r3.metric(f"EBIT-margin {latest_period}", f"{float(latest.get('EBIT-margin') or 0):.1f}%".replace(".", ","))
                r4.metric(f"EPS {latest_period}", f"{float(latest.get('EPS') or 0):.2f} NOK".replace(".", ","))

                st.subheader("Siste 5 årsresultater")
                annual_display = pd.DataFrame(report.get("annual", [])).copy().rename(
                    columns={
                        "Omsetning": "Omsetning (MNOK)",
                        "EBITDA": "EBITDA (MNOK)",
                        "EBIT": "EBIT (MNOK)",
                        "Resultat": "Resultat (MNOK)",
                        "OCF": "OCF (MNOK)",
                        "FCF": "FCF (MNOK)",
                    }
                )
                if not annual_display.empty:
                    annual_display = annual_display.tail(5)
                    annual_display["Vekst"] = annual_display["Vekst"].map(lambda x: "–" if pd.isna(x) else f"{x:.0f}%")
                    annual_display["EBITDA-margin"] = annual_display["EBITDA-margin"].map(lambda x: "–" if pd.isna(x) else f"{x:.0f}%")
                    annual_display["EBIT-margin"] = annual_display["EBIT-margin"].map(lambda x: "–" if pd.isna(x) else f"{x:.0f}%")
                    annual_display["EPS"] = annual_display["EPS"].map(lambda x: "–" if pd.isna(x) else f"{x:.2f}".replace(".", ","))
                    annual_display["NIBD / EBITDA"] = annual_display["NIBD / EBITDA"].map(lambda x: "–" if pd.isna(x) else f"{x:.1f}x".replace(".", ","))
                    for col in ["Omsetning (MNOK)", "EBITDA (MNOK)", "EBIT (MNOK)", "Resultat (MNOK)", "OCF (MNOK)", "FCF (MNOK)"]:
                        if col in annual_display.columns:
                            annual_display[col] = annual_display[col].map(
                                lambda x: "–" if pd.isna(x) else f"{x:,.1f}".replace(",", " ").replace(".", ",")
                            )
                    st.dataframe(annual_display, width="stretch", hide_index=True)

                st.subheader("Siste kvartaler")
                quarterly_display = pd.DataFrame(quarterly_sorted).copy().rename(
                    columns={
                        "Omsetning": "Omsetning (MNOK)",
                        "EBIT": "EBIT (MNOK)",
                        "Resultat": "Resultat (MNOK)",
                        "OCF": "OCF (MNOK)",
                        "FCF": "FCF (MNOK)",
                    }
                )
                if not quarterly_display.empty:
                    quarterly_display["Omsetning (MNOK)"] = quarterly_display["Omsetning (MNOK)"].map(
                        lambda x: "–" if pd.isna(x) else f"{x:,.1f}".replace(",", " ").replace(".", ",")
                    )
                    quarterly_display["Vekst YoY"] = quarterly_display["Vekst YoY"].map(
                        lambda x: "–" if pd.isna(x) else f"{x:+.0f}%"
                    )
                    for col in ["EBIT (MNOK)", "Resultat (MNOK)", "OCF (MNOK)", "FCF (MNOK)"]:
                        if col in quarterly_display.columns:
                            quarterly_display[col] = quarterly_display[col].map(
                                lambda x: "–" if pd.isna(x) else f"{x:,.1f}".replace(",", " ").replace(".", ",")
                            )
                    quarterly_display["EBIT-margin"] = quarterly_display["EBIT-margin"].map(
                        lambda x: "–" if pd.isna(x) else f"{x:.1f}%".replace(".", ",")
                    )
                    quarterly_display["EPS"] = quarterly_display["EPS"].map(
                        lambda x: "–" if pd.isna(x) else f"{x:.2f}".replace(".", ",")
                    )
                    quarterly_display["NIBD / EBITDA"] = quarterly_display["NIBD / EBITDA"].map(
                        lambda x: "–" if pd.isna(x) else f"{x:.1f}x".replace(".", ",")
                    )
                    st.dataframe(quarterly_display, width="stretch", hide_index=True)

                st.divider()
                st.subheader("Legg inn / oppdater rapport")

                github_config = _github_reporting_config()
                storage_source = st.session_state.get(
                    "norbit_reporting_storage_source",
                    "GitHub" if github_config else "Lokal testlagring",
                )
                st.caption(f"Lagring: {storage_source}")
                storage_warning = st.session_state.get("norbit_reporting_storage_warning")
                if storage_warning:
                    st.warning(storage_warning)

                if github_config and st.button("Last inn siste data fra GitHub", key="reload_norbit_github"):
                    load_norbit_reporting_data(force_reload=True)
                    st.rerun()

                admin_pin = _secret("REPORTING_ADMIN_PIN")
                can_edit_reporting = True
                if github_config:
                    if admin_pin:
                        entered_pin = st.text_input(
                            "PIN for redigering",
                            type="password",
                            key="norbit_reporting_pin",
                            help="PIN-koden ligger kun i Streamlit Secrets og lagres ikke i koden.",
                        )
                        can_edit_reporting = entered_pin == str(admin_pin)
                        if entered_pin and not can_edit_reporting:
                            st.error("Feil PIN.")
                        elif not entered_pin:
                            st.info("Skriv PIN for å åpne redigering av rapporteringsdata.")
                    else:
                        can_edit_reporting = False
                        st.warning(
                            "GitHub-lagring er konfigurert, men REPORTING_ADMIN_PIN mangler. "
                            "Redigering er derfor låst til PIN er lagt inn i Streamlit Secrets."
                        )

                if can_edit_reporting:
                    report_type = st.radio(
                        "Rapporttype",
                        ["Kvartal", "Årsresultat"],
                        horizontal=True,
                        key="norbit_report_type",
                    )

                    if report_type == "Kvartal":
                        selector1, selector2 = st.columns(2)
                        report_year = int(selector1.number_input(
                            "År", min_value=2021, max_value=2035, value=2026, step=1, key="norbit_q_year"
                        ))
                        report_quarter = int(selector2.selectbox(
                            "Kvartal", [1, 2, 3, 4], index=2, key="norbit_q_quarter"
                        ))
                        existing = _find_quarter(report, report_year, report_quarter) or {}
    
                        with st.form("norbit_quarter_form"):
                            c1, c2, c3 = st.columns(3)
                            revenue = c1.number_input("Omsetning (MNOK)", value=float(existing.get("Omsetning") or 0.0), step=1.0)
                            ebit = c2.number_input("EBIT (MNOK)", value=float(existing.get("EBIT") or 0.0), step=1.0)
                            result = c3.number_input("Resultat (MNOK)", value=float(existing.get("Resultat") or 0.0), step=1.0)
    
                            c4, c5, c6 = st.columns(3)
                            eps = c4.number_input("EPS", value=float(existing.get("EPS") or 0.0), step=0.01, format="%.2f")
                            ocf = c5.number_input("OCF (MNOK)", value=float(existing.get("OCF") or 0.0), step=1.0)
                            fcf = c6.number_input("FCF (MNOK)", value=float(existing.get("FCF") or 0.0), step=1.0)
    
                            c7, c8 = st.columns(2)
                            leverage = c7.number_input("NIBD / EBITDA", value=float(existing.get("NIBD / EBITDA") or 0.0), step=0.1, format="%.1f")
                            c8.caption("EBIT-margin og omsetningsvekst YoY beregnes automatisk.")
    
                            submitted = st.form_submit_button("Lagre kvartal", type="primary")
    
                        if submitted:
                            if revenue <= 0:
                                st.error("Omsetning må være større enn 0.")
                            else:
                                previous = _find_quarter(report, report_year - 1, report_quarter)
                                yoy = _pct_change(revenue, previous.get("Omsetning") if previous else None)
                                margin = ebit / revenue * 100
                                new_row = {
                                    "Periode": f"Q{report_quarter} {report_year}",
                                    "Omsetning": revenue,
                                    "Vekst YoY": yoy,
                                    "EBIT": ebit,
                                    "EBIT-margin": margin,
                                    "Resultat": result,
                                    "EPS": eps,
                                    "OCF": ocf,
                                    "FCF": fcf,
                                    "NIBD / EBITDA": leverage,
                                }
                                report["quarterly"] = [
                                    r for r in report.get("quarterly", [])
                                    if r.get("Periode") != new_row["Periode"]
                                ] + [new_row]
                                report["quarterly"] = sorted(report["quarterly"], key=_quarter_sort_key)
                                ok, save_message = save_norbit_reporting_data(
                                    report,
                                    commit_message=f"Oppdater NORBIT {new_row['Periode']}",
                                )
                                if ok:
                                    st.success(
                                        f"{new_row['Periode']} er lagret og koblet til Oversikt/Nøkkeltall. "
                                        f"{save_message}"
                                    )
                                    st.rerun()
                                else:
                                    st.error(save_message)
    
                    else:
                        report_year = int(st.number_input(
                            "År", min_value=2021, max_value=2035, value=2026, step=1, key="norbit_fy_year"
                        ))
                        existing = next((r for r in report.get("annual", []) if int(r.get("År", 0)) == report_year), {})
    
                        with st.form("norbit_annual_form"):
                            c1, c2, c3 = st.columns(3)
                            revenue = c1.number_input("Omsetning (MNOK)", value=float(existing.get("Omsetning") or 0.0), step=1.0)
                            ebitda = c2.number_input("EBITDA (MNOK)", value=float(existing.get("EBITDA") or 0.0), step=1.0)
                            ebit = c3.number_input("EBIT (MNOK)", value=float(existing.get("EBIT") or 0.0), step=1.0)
    
                            c4, c5, c6 = st.columns(3)
                            result = c4.number_input("Resultat (MNOK)", value=float(existing.get("Resultat") or 0.0), step=1.0)
                            eps = c5.number_input("EPS", value=float(existing.get("EPS") or 0.0), step=0.01, format="%.2f")
                            ocf = c6.number_input("OCF (MNOK)", value=float(existing.get("OCF") or 0.0), step=1.0)
    
                            c7, c8, c9 = st.columns(3)
                            fcf = c7.number_input("FCF (MNOK)", value=float(existing.get("FCF") or 0.0), step=1.0)
                            leverage = c8.number_input("NIBD / EBITDA", value=float(existing.get("NIBD / EBITDA") or 0.0), step=0.1, format="%.1f")
                            c9.caption("Vekst og marginer beregnes automatisk.")
    
                            submitted_annual = st.form_submit_button("Lagre årsresultat", type="primary")
    
                        if submitted_annual:
                            if revenue <= 0:
                                st.error("Omsetning må være større enn 0.")
                            else:
                                previous = next((r for r in report.get("annual", []) if int(r.get("År", 0)) == report_year - 1), None)
                                growth = _pct_change(revenue, previous.get("Omsetning") if previous else None)
                                new_row = {
                                    "År": report_year,
                                    "Omsetning": revenue,
                                    "Vekst": growth,
                                    "EBITDA": ebitda,
                                    "EBITDA-margin": ebitda / revenue * 100,
                                    "EBIT": ebit,
                                    "EBIT-margin": ebit / revenue * 100,
                                    "Resultat": result,
                                    "EPS": eps,
                                    "OCF": ocf,
                                    "FCF": fcf,
                                    "NIBD / EBITDA": leverage,
                                }
                                report["annual"] = [
                                    r for r in report.get("annual", [])
                                    if int(r.get("År", 0)) != report_year
                                ] + [new_row]
                                report["annual"] = sorted(report["annual"], key=lambda r: int(r.get("År", 0)))
                                ok, save_message = save_norbit_reporting_data(
                                    report,
                                    commit_message=f"Oppdater NORBIT årsresultat {report_year}",
                                )
                                if ok:
                                    st.success(f"Årsresultat {report_year} er lagret. {save_message}")
                                    st.rerun()
                                else:
                                    st.error(save_message)
    
                st.download_button(
                    "Last ned sikkerhetskopi av rapporteringsdata",
                    data=json.dumps(report, ensure_ascii=False, indent=2),
                    file_name="norbit_reporting_backup.json",
                    mime="application/json",
                )

                if github_config:
                    st.success(
                        "Permanent lagring er aktivert mot GitHub. Nye rapportdata commits til repositoryet "
                        "og overlever restart/redeploy av Streamlit Cloud."
                    )
                else:
                    st.info(
                        "Lokal testmodus: data lagres i data/norbit_reporting.json. For permanent lagring på "
                        "jt-investering.streamlit.app må GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH og "
                        "REPORTING_ADMIN_PIN legges inn i Streamlit Secrets."
                    )
                st.caption(report.get("source_note", ""))

# =========================================================
# NØKKELTALL
# =========================================================

elif side == "Nøkkeltall":
    st.header("Nøkkeltall")

    selskap = st.selectbox(
        "Velg selskap",
        ["NORBIT", "Cambi", "Kitron", "NOTE"],
        key="global_keyfig_company",
    )
    info = companies[selskap]
    st.subheader(selskap)

    df = pd.DataFrame(info["financials"])
    st.dataframe(df, width="stretch", hide_index=True)

# =========================================================
# AKSJONÆRER
# =========================================================

elif side == "Aksjonærer":
    st.header("Aksjonærendringer")

    selskap = st.selectbox(
        "Velg selskap",
        ["NORBIT", "Cambi", "Kitron", "NOTE"],
        key="global_shareholder_company",
    )

    info = companies[selskap]
    render_shareholder_monitor(
        info,
        key_prefix=f"{info['ticker'].lower()}_global",
    )

# =========================================================
# NYHETER
# =========================================================

elif side == "Nyheter":
    st.header("Nyhetsmonitor")

    selskap = st.selectbox(
        "Velg selskap",
        ["NORBIT", "Cambi", "Kitron", "NOTE"],
        key="global_news_company",
    )
    info = companies[selskap]

    n1, n2 = st.columns(2)
    n1.metric("Relevante saker", len(info["news"]))
    n2.metric(
        "Viktige saker",
        sum(1 for item in info["news"] if item["Viktighet"].startswith("🔴"))
    )

    st.subheader(f"{selskap} – siste relevante nyheter")
    st.dataframe(
        pd.DataFrame(info["news"])[
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

# =========================================================
# KONTRAKTER
# =========================================================

elif side == "Kontrakter":
    st.header("Kontrakter og anbud")

    selskap = st.selectbox(
        "Velg selskap",
        ["NORBIT", "Cambi", "Kitron", "NOTE"],
        key="global_contract_company",
    )
    info = companies[selskap]
    currency = info.get("currency", "NOK")
    financial_currency = info.get("financial_currency", currency)
    million_unit = f"M{financial_currency}"

    known_contract_value = sum(
        item["Verdi (MNOK)"]
        for item in info["contracts"]
        if isinstance(item["Verdi (MNOK)"], (int, float))
    )

    st.metric(
        info["contract_value_metric_label"],
        f"{known_contract_value:,.0f} {million_unit}".replace(",", " ")
    )
    st.caption(info["contract_value_caption"])

    st.subheader(f"{selskap} – inngåtte / annonserte kontrakter")
    global_contracts = pd.DataFrame(info["contracts"]).copy()

    if "Verdi (MNOK)" in global_contracts.columns:
        raw_global_value_col = "Verdi (MNOK)"
        global_contract_value_col = f"Verdi ({million_unit})"
        formatted_global_values = global_contracts[raw_global_value_col].map(
            lambda x: "–" if pd.isna(x) else f"{x:,.0f}".replace(",", " ")
        )
        if global_contract_value_col == raw_global_value_col:
            global_contracts[raw_global_value_col] = formatted_global_values
        else:
            global_contracts[global_contract_value_col] = formatted_global_values
            global_contracts = global_contracts.drop(columns=[raw_global_value_col])

    global_contracts = global_contracts.fillna("–")
    global_contract_display = global_contracts.copy()
    for col in global_contract_display.columns:
        global_contract_display[col] = global_contract_display[col].map(
            lambda x: "–" if pd.isna(x) else str(x)
        )

    st.dataframe(
        global_contract_display,
        width="stretch",
        hide_index=True
    )

    st.subheader(f"{selskap} – potensielle kontrakter og anbud")
    df_opp = pd.DataFrame(info["opportunities"]).copy()

    for auto in contract_monitor.values():
        if auto.get("company") != selskap:
            continue
        match_text = auto.get("opportunity_match") or auto.get("title")
        if not match_text:
            continue
        mask = df_opp["Mulighet"].astype(str).str.contains(
            re.escape(match_text), case=False, na=False, regex=True
        )
        if mask.any():
            if auto.get("status"):
                df_opp.loc[mask, "Status"] = auto["status"]
            if auto.get("next_date"):
                df_opp.loc[mask, "Neste dato"] = auto["next_date"]
            if auto.get("date_type"):
                df_opp.loc[mask, "Dato-type"] = auto["date_type"]
            if auto.get("last_checked"):
                df_opp.loc[mask, "Sist kontrollert"] = auto["last_checked"]
            if auto.get("last_updated"):
                df_opp.loc[mask, "Sist oppdatert"] = auto["last_updated"]
            if auto.get("source_label"):
                df_opp.loc[mask, "Kilde"] = auto["source_label"]

    for optional_col in ["Neste dato", "Dato-type", "Sist kontrollert", "Kilde"]:
        if optional_col not in df_opp.columns:
            df_opp[optional_col] = "–"
        else:
            df_opp[optional_col] = df_opp[optional_col].fillna("–")

    global_value_col = f"Est. verdi ({million_unit})"
    if "Est. verdi (MNOK)" in df_opp.columns:
        raw_global_est_col = "Est. verdi (MNOK)"
        formatted_global_est = df_opp[raw_global_est_col].map(
            lambda x: "–" if pd.isna(x) else f"{x:,.0f}".replace(",", " ")
        )
        if global_value_col == raw_global_est_col:
            df_opp[raw_global_est_col] = formatted_global_est
        else:
            df_opp[global_value_col] = formatted_global_est
            df_opp = df_opp.drop(columns=[raw_global_est_col])

    df_opp = df_opp.fillna("–")

    global_opp_cols = [
        "Prioritet",
        "Mulighet",
        "Sannsynlighet",
        global_value_col,
        "Status",
        "Neste dato",
        "Dato-type",
        "Sist oppdatert",
        "Sist kontrollert",
        "Kilde",
        "Kommentar",
    ]

    global_opp_display = df_opp[global_opp_cols].copy()
    for col in global_opp_display.columns:
        global_opp_display[col] = global_opp_display[col].map(
            lambda x: "–" if pd.isna(x) else str(x)
        )

    st.dataframe(
        global_opp_display,
        width="stretch",
        hide_index=True
    )

    st.caption(
        "Neste dato er offentlig kjent frist eller forventet beslutningsdato. "
        "Når bare tilbudsfrist er kjent, vises den – ikke en antatt award-dato. "
        "Sist kontrollert viser når kilden sist ble sjekket; Sist oppdatert endres "
        "bare når selve saken har fått ny informasjon."
    )

    st.warning(
        "Potensielle kontrakter/anbud er vår analyse, ikke annonserte ordre. "
        "Estimert verdi står tom der vi ikke har et forsvarlig offentlig anslag."
    )

