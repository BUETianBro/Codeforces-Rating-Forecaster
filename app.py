from __future__ import annotations

from urllib.parse import quote

import streamlit as st

from src.codeforces_api import CodeforcesAPIError, fetch_rating_history
from src.model import build_forecast
from src.visualization import make_rating_chart


@st.cache_data(ttl=300, show_spinner=False)
def load_rating_history(handle: str):
    """Cache Codeforces responses briefly to avoid repeated API requests."""
    return fetch_rating_history(handle)


st.set_page_config(
    page_title="Codeforces Rating Forecaster",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Codeforces Rating Forecaster")
st.caption(
    "Explore a Codeforces user's rating history and extend its historical trend "
    "with a logarithmic-regression projection."
)

with st.sidebar:
    st.header("Forecast settings")
    handle = st.text_input("Codeforces handle", value="brainsoft").strip()
    future_contests = st.slider(
        "Future contests to project",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )
    run_forecast = st.button("Generate forecast", type="primary", use_container_width=True)

    st.divider()
    st.caption("Public rating data is fetched from the official Codeforces API.")

st.info(
    "This is a mathematical trend projection based only on historical ratings. "
    "It does not predict future contest participation, performance, rank, or official rating changes."
)

if run_forecast:
    if not handle:
        st.warning("Enter a Codeforces handle first.")
        st.stop()

    try:
        with st.spinner(f"Fetching rating history for {handle}..."):
            history = load_rating_history(handle)
    except CodeforcesAPIError as exc:
        st.error(str(exc))
        st.stop()

    if len(history) < 2:
        st.warning("At least two rated contests are required to fit a trend.")
        st.stop()

    forecast = build_forecast(history, future_contests=future_contests)

    current_rating = int(history.iloc[-1]["rating"])
    latest_change = int(history.iloc[-1]["rating_change"])
    peak_rating = int(history["rating"].max())
    current_trend_rating = int(round(forecast.fitted.iloc[-1]["fitted_rating"]))
    projected_rating = int(round(forecast.future.iloc[-1]["projected_rating"]))

    profile_url = f"https://codeforces.com/profile/{quote(handle, safe='')}"
    st.link_button(f"Open {handle} on Codeforces ↗", profile_url)
    download_col1, download_col2 = st.columns(2)
    download_col1.download_button(
        "Download rating history (CSV)",
        data=history.to_csv(index=False).encode("utf-8"),
        file_name=f"{handle}-rating-history.csv",
        mime="text/csv",
        use_container_width=True,
    )
    download_col2.download_button(
        "Download projected trend (CSV)",
        data=forecast.future.to_csv(index=False).encode("utf-8"),
        file_name=f"{handle}-rating-projection.csv",
        mime="text/csv",
        use_container_width=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rated contests", len(history))
    c2.metric("Current rating", current_rating)
    c3.metric("Peak rating", peak_rating)
    c4.metric("Latest change", f"{latest_change:+d}")
    c5.metric(
        f"Trend estimate after {future_contests}",
        projected_rating,
        delta=projected_rating - current_trend_rating,
        help=(
            "The delta is measured against the model's fitted trend at the latest "
            "rated contest, not against the player's actual current rating."
        ),
    )

    st.caption(
        f"Latest actual rating: **{current_rating}** · Current fitted trend: "
        f"**{current_trend_rating}** · The latest actual rating can sit above or below the regression curve."
    )

    st.plotly_chart(
        make_rating_chart(history, forecast, handle),
        use_container_width=True,
        config={
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"{handle}-rating-forecast",
                "scale": 2,
            }
        },
    )

    with st.expander("Model details"):
        st.markdown(
            "The model fits historical ratings against the logarithm of the rated-contest number:"
        )
        st.code("rating = intercept + slope × log2(contest_number)", language="text")
        m1, m2, m3 = st.columns(3)
        m1.metric("Slope", f"{forecast.slope:.3f}")
        m2.metric("Intercept", f"{forecast.intercept:.3f}")
        m3.metric("Historical R²", f"{forecast.r_squared:.4f}")
        st.caption(
            "R² describes how closely this simple curve fits the historical ratings. "
            "It is not a confidence score for future performance."
        )

    with st.expander("Recent rated contests"):
        recent = history.tail(15).sort_values("contest_number", ascending=False).copy()
        recent["contest_url"] = recent["contest_id"].map(
            lambda contest_id: f"https://codeforces.com/contest/{contest_id}"
        )
        recent = recent.rename(
            columns={
                "contest_number": "#",
                "contest_name": "Contest",
                "rank": "Rank",
                "old_rating": "Old rating",
                "rating": "New rating",
                "rating_change": "Change",
                "rating_update_time": "Updated (UTC)",
                "contest_url": "Round link",
            }
        )
        display_columns = [
            "#",
            "Contest",
            "Rank",
            "Old rating",
            "New rating",
            "Change",
            "Updated (UTC)",
            "Round link",
        ]
        st.dataframe(
            recent[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Round link": st.column_config.LinkColumn(display_text="Open round ↗")
            },
        )
else:
    st.subheader("How it works")
    c1, c2, c3 = st.columns(3)
    c1.markdown("### 1. Fetch\nLoad a user's public rated-contest history from Codeforces.")
    c2.markdown("### 2. Fit\nFit a logarithmic regression curve to the historical ratings.")
    c3.markdown("### 3. Project\nExtend that fitted curve across a chosen number of future contests.")

    st.subheader("Try it")
    st.markdown(
        "1. Enter a Codeforces handle in the sidebar.\n"
        "2. Choose how many future rated contests to project.\n"
        "3. Click **Generate forecast**.\n\n"
        "The chart clearly separates real rating history, the historical fitted trend, "
        "and the extrapolated trend."
    )

st.divider()
st.caption("Built by Muhammad Al-Muzahid · Data source: Codeforces public API")
