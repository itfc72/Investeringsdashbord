import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import re

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
        "h1": {
            "revenue": 443.6,
            "growth": -21.7,
            "ebit": 39.5,
            "ebit_margin": 8.9,
            "eps": 0.13,
            "ocf": 151.9,
            "fcf": 148.0,
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
            "growth_bear": 20.0,
            "growth_base": 40.0,
            "growth_bull": 55.0,
            "pe_bear": 16.0,
            "pe_base": 20.0,
            "pe_bull": 24.0,
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
        "h1": {
            "revenue": 568.4,
            "growth": 68.7,
            "ebit": 53.9,
            "ebit_margin": 9.5,
            "eps": 0.19,
            "ocf": 52.1,
            "fcf": -21.1,
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
        "h1": {
            "revenue": 2137.0,
            "growth": 8.0,
            "ebit": 174.0,
            "ebit_margin": 8.1,
            "eps": 3.78,
            "ocf": 12.0,
            "fcf": -810.0,
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
        "case": "Kommer i neste steg."
    }
}

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
        "Nøkkeltall",
        "Aksjonærer",
        "Nyheter",
        "Kontrakter"
    ]
)

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
        info = companies[name]
        val = info.get("valuation")
        if not val:
            return None

        if name == "Cambi":
            return val["cambi_eps_2028_base"] * val["pe_base"]

        years = val["target_year"] - 2026
        eps_target = val["eps_2026"] * (1 + val["growth_base"] / 100) ** years
        return eps_target * val["pe_base"]

    dashboard_rows = []

    for name in ["NORBIT", "Cambi", "Kitron", "NOTE", "Protector"]:
        info = companies[name]
        hist = info.get("dashboard_5y")

        if not hist or "price" not in info:
            dashboard_rows.append({
                "Selskap": name,
                "Kurs": "–",
                "Omsetning CAGR 5Å": "–",
                "EPS CAGR 5Å": "–",
                "FCF-yield 5Å snitt": "–",
                "Kursmål 2028": "–",
                "Oppside": "–",
            })
            continue

        currency = info.get("currency", "NOK")
        target = dashboard_target_2028(name)
        upside = ((target / info["price"]) - 1) * 100 if target else None

        dashboard_rows.append({
            "Selskap": name,
            "Kurs": f'{info["price"]:.2f} {currency}'.replace(".", ","),
            "Omsetning CAGR 5Å": f'{hist["revenue_cagr"]:.1f}%'.replace(".", ","),
            "EPS CAGR 5Å": (
                f'{hist["eps_cagr"]:.1f}%'.replace(".", ",")
                if hist["eps_cagr"] is not None
                else "N/M"
            ),
            "FCF-yield 5Å snitt": f'{hist["fcf_yield_avg"]:.1f}%'.replace(".", ","),
            "Kursmål 2028": f'{target:.0f} {currency}' if target else "–",
            "Oppside": f'{upside:+.0f}%' if upside is not None else "–",
        })

    oversikt = pd.DataFrame(dashboard_rows)

    st.dataframe(oversikt, width="stretch", hide_index=True)

    st.caption(
        "CAGR er beregnet fra FY2020 til FY2025. FCF-yield 5Å snitt er "
        "gjennomsnittet av rapportert årlig FCF-yield for FY2021–FY2025. "
        "N/M betyr at EPS-CAGR ikke er meningsfull fordi EPS var negativt "
        "i deler av perioden. Kursmål 2028 er vårt base-scenario."
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

    if selskap not in ("NORBIT", "Cambi", "Kitron", "NOTE"):
        st.info(
            "Strukturen er klar. Dette selskapet fylles med faktiske data "
            "etter at NORBIT-siden er ferdigstilt."
        )
        st.subheader("Investeringscase")
        st.write(info["case"])

    else:
        widget_prefix = info["ticker"].lower()
        currency = info.get("currency", "NOK")
        financial_currency = info.get("financial_currency", currency)
        million_unit = f"M{financial_currency}"
        cashflow_unit = info.get("cashflow_unit", million_unit)
        billion_unit = f"mrd. {currency}"
        financial_billion_unit = f"mrd. {financial_currency}"
        cashflow_fx_to_share_currency = info.get("cashflow_fx_to_share_currency", 1.0)
        valuation_fx_to_share_currency = info.get("valuation_fx_to_share_currency", 1.0)

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

            st.subheader("Siste kvartal – Q2 2026")

            q1, q2, q3 = st.columns(3)
            q1.metric(
                "Omsetning",
                f"{info['q2']['revenue']:.1f} {million_unit}".replace(".", ",")
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
                f"{info['q2']['ebit']:.1f} {million_unit}".replace(".", ",")
            )
            q5.metric(
                "EPS",
                f"{info['q2']['eps']:.2f}".replace(".", ",")
            )
            q6.metric(
                "CF etter investeringer" if selskap == "NOTE" else "FCF",
                f"{info['q2']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
            )

            st.subheader("H1 2026")

            h1, h2, h3 = st.columns(3)
            h1.metric(
                "Omsetning",
                f"{info['h1']['revenue']:,.1f} {million_unit}".replace(",", " ").replace(".", ",")
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
                f"{info['h1']['ebit']:.1f} {million_unit}".replace(".", ",")
            )
            h5.metric(
                "EPS",
                f"{info['h1']['eps']:.2f}".replace(".", ",")
            )
            h6.metric(
                "CF etter investeringer" if selskap == "NOTE" else "FCF",
                f"{info['h1']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
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

            st.subheader("Q2 2026 – segmenter")
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
                    "OCF Q2",
                    f"{info['q2']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf2.metric(
                    "OCF H1",
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
                    "FCF Q2",
                    f"{info['q2']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf2.metric(
                    "FCF H1",
                    f"{info['h1']['fcf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf3.metric(
                    "FCF LTM",
                    f"{info['fcf_ltm']:.0f} {cashflow_unit}"
                )

                cf4, cf5, cf6 = st.columns(3)
                cf4.metric(
                    "OCF Q2",
                    f"{info['q2']['ocf']:.1f} {cashflow_unit}".replace(".", ",")
                )
                cf5.metric(
                    "OCF H1",
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
            if selskap == "Cambi":
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
                        f"Dagens kurs / referansekurs ({currency})",
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
                    g1, g2, g3 = st.columns(3)
                    growth_bear = g1.number_input(
                        "Bear vekst",
                        min_value=-20.0,
                        max_value=50.0,
                        value=float(info["valuation"]["growth_bear"]),
                        step=1.0,
                        format="%.1f",
                        key=f"{widget_prefix}_growth_bear"
                    )
                    growth_base = g2.number_input(
                        "Base vekst",
                        min_value=-20.0,
                        max_value=50.0,
                        value=float(info["valuation"]["growth_base"]),
                        step=1.0,
                        format="%.1f",
                        key=f"{widget_prefix}_growth_base"
                    )
                    growth_bull = g3.number_input(
                        "Bull vekst",
                        min_value=-20.0,
                        max_value=60.0,
                        value=float(info["valuation"]["growth_bull"]),
                        step=1.0,
                        format="%.1f",
                        key=f"{widget_prefix}_growth_bull"
                    )

                    st.markdown("**P/E i målåret**")
                    p1, p2, p3 = st.columns(3)
                    pe_bear = p1.number_input(
                        "Bear P/E",
                        min_value=5.0,
                        max_value=50.0,
                        value=float(info["valuation"]["pe_bear"]),
                        step=1.0,
                        key=f"{widget_prefix}_pe_bear"
                    )
                    pe_base = p2.number_input(
                        "Base P/E",
                        min_value=5.0,
                        max_value=50.0,
                        value=float(info["valuation"]["pe_base"]),
                        step=1.0,
                        key=f"{widget_prefix}_pe_base"
                    )
                    pe_bull = p3.number_input(
                        "Bull P/E",
                        min_value=5.0,
                        max_value=60.0,
                        value=float(info["valuation"]["pe_bull"]),
                        step=1.0,
                        key=f"{widget_prefix}_pe_bull"
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

