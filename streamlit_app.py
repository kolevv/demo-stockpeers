# -*- coding: utf-8 -*-
"""
Stock Chart - With Glue Context Integration

Subscribes to SelectedInstrument context and displays the selected stock's price chart.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import logging

# Install with: pip install streamlit-autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# Import gluepy for context sharing
from gluepy import (
    glue_ensure_clr,
    glue_lib,
    translate_glue_value,
    GlueState,
    GlueInitCallback,
    active_callbacks
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize CLR early (before any UI) - this needs to happen once
try:
    glue_ensure_clr()
except Exception as e:
    logger.warning(f"CLR initialization: {e}")

st.set_page_config(
    page_title="Stock Chart",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

INSTRUMENT_CONTEXT = "SelectedInstrument"
DEFAULT_TICKER = "AAPL"

STOCKS = [
    "AAPL", "ABBV", "ACN", "ADBE", "ADP", "AMD", "AMGN", "AMT", "AMZN", "APD",
    "AVGO", "AXP", "BA", "BK", "BKNG", "BMY", "BRK.B", "BSX", "C", "CAT",
    "CI", "CL", "CMCSA", "COST", "CRM", "CSCO", "CVX", "DE", "DHR", "DIS",
    "DUK", "ELV", "EOG", "EQR", "FDX", "GD", "GE", "GILD", "GOOG", "GOOGL",
    "HD", "HON", "HUM", "IBM", "ICE", "INTC", "ISRG", "JNJ", "JPM", "KO",
    "LIN", "LLY", "LMT", "LOW", "MA", "MCD", "MDLZ", "META", "MMC", "MO",
    "MRK", "MSFT", "NEE", "NFLX", "NKE", "NOW", "NVDA", "ORCL", "PEP", "PFE",
    "PG", "PLD", "PM", "PSA", "REGN", "RTX", "SBUX", "SCHW", "SLB", "SO",
    "SPGI", "T", "TJX", "TMO", "TSLA", "TXN", "UNH", "UNP", "UPS", "V",
    "VZ", "WFC", "WM", "WMT", "XOM",
]

# ═══════════════════════════════════════════════════════════════════════════════
# Session State Initialization
# ═══════════════════════════════════════════════════════════════════════════════

if 'glue_initialized' not in st.session_state:
    st.session_state.glue_initialized = False
if 'glue_init_attempted' not in st.session_state:
    st.session_state.glue_init_attempted = False
if 'last_ric' not in st.session_state:
    st.session_state.last_ric = None
if 'stock_selector' not in st.session_state:
    st.session_state.stock_selector = DEFAULT_TICKER

# ═══════════════════════════════════════════════════════════════════════════════
# Auto-refresh for context updates (must be early in the script)
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_AUTOREFRESH and st.session_state.glue_initialized:
    st_autorefresh(interval=1000, limit=None, key="context_autorefresh")

# ═══════════════════════════════════════════════════════════════════════════════
# Glue Context Functions
# ═══════════════════════════════════════════════════════════════════════════════


def read_context_ric() -> str:
    """Read the current RIC from the SelectedInstrument context."""
    if not st.session_state.glue_initialized:
        return None

    try:
        ctx_reader = glue_lib.glue_read_context_sync(INSTRUMENT_CONTEXT.encode("utf-8"))
        if ctx_reader:
            ric_value = glue_lib.glue_read_glue_value(ctx_reader, b"ric")
            ric = translate_glue_value(ric_value)
            if ric:
                return str(ric)
    except Exception as e:
        logger.debug(f"Could not read context: {e}")

    return None


# Global to keep callback alive for the lifetime of the app
_glue_init_callback_ref = None
_glue_init_event = None
_glue_init_result = {'success': False}


def init_glue_sync():
    """Initialize Glue synchronously for Streamlit."""
    global _glue_init_callback_ref, _glue_init_event, _glue_init_result

    if st.session_state.glue_initialized:
        return True

    # If we already attempted, check if it succeeded in the background
    if st.session_state.glue_init_attempted:
        if _glue_init_result.get('success'):
            st.session_state.glue_initialized = True
            return True
        return False

    st.session_state.glue_init_attempted = True

    try:
        import threading

        _glue_init_event = threading.Event()
        _glue_init_result['success'] = False

        def glue_init_callback(state, message, glue_payload, cookie):
            decoded_message = message.decode('utf-8') if message else ""
            logger.info(f"Glue callback - state: {state}, message: {decoded_message}")

            # INITIALIZED = 3
            if state == 3:
                _glue_init_result['success'] = True
                _glue_init_event.set()
            # DISCONNECTED = 4
            elif state == 4:
                _glue_init_event.set()

        # Create callback and keep it alive FOREVER
        _glue_init_callback_ref = GlueInitCallback(glue_init_callback)
        active_callbacks.append(_glue_init_callback_ref)

        logger.info("Calling glue_init...")
        result = glue_lib.glue_init(b"StockChart", _glue_init_callback_ref, None)
        logger.info(f"glue_init returned: {result}")

        if result != 0:
            logger.error(f"glue_init returned error: {result}")
            return False

        # Wait for initialization
        logger.info("Waiting for Glue initialization (30s timeout)...")
        if _glue_init_event.wait(timeout=30.0):
            if _glue_init_result['success']:
                st.session_state.glue_initialized = True
                logger.info("Glue initialized successfully")
                return True
            else:
                logger.warning("Glue initialization failed")
                return False
        else:
            logger.warning("Glue initialization timed out")
            return False

    except Exception as e:
        logger.error(f"Error initializing Glue: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def ric_to_ticker(ric: str) -> str:
    """Convert a RIC (e.g., VOD:LN) to a Yahoo Finance ticker."""
    if not ric:
        return None

    ric = ric.upper().strip()

    suffix_map = {
        ":LN": ".L",
        ":GR": ".DE",
        ":FP": ".PA",
        ":NA": ".AS",
        ":SM": ".MC",
        ":IM": ".MI",
        ":SW": ".SW",
        ":AV": ".VI",
        ":BB": ".BR",
        ":JP": ".T",
        ":HK": ".HK",
        ":AU": ".AX",
        ":CN": ".TO",
    }

    for ric_suffix, yahoo_suffix in suffix_map.items():
        if ric.endswith(ric_suffix):
            base = ric[:-len(ric_suffix)]
            return base + yahoo_suffix

    if ":" in ric:
        return ric.split(":")[0]

    return ric


# ═══════════════════════════════════════════════════════════════════════════════
# Check for context updates FIRST (before any UI)
# ═══════════════════════════════════════════════════════════════════════════════

if st.session_state.glue_initialized:
    current_ric = read_context_ric()
    if current_ric and current_ric != st.session_state.last_ric:
        st.session_state.last_ric = current_ric
        new_ticker = ric_to_ticker(current_ric)
        if new_ticker and new_ticker.upper() != st.session_state.stock_selector:
            st.session_state.stock_selector = new_ticker.upper()
            st.toast(f"📥 Switched to {new_ticker.upper()}", icon="✅")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# Sidebar - Glue Connection
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader("🔗 io.Connect Integration")

    if not st.session_state.glue_initialized:
        if st.button("Connect to io.Connect", type="primary", width="stretch"):
            with st.spinner("Connecting..."):
                if init_glue_sync():
                    st.rerun()
                else:
                    st.error("Failed to connect")
    else:
        st.success("✓ Connected")
        st.caption(f"Reading from `{INSTRUMENT_CONTEXT}`")

        if HAS_AUTOREFRESH:
            st.caption("🔄 Auto-sync enabled (1s)")
        else:
            st.warning("Install `streamlit-autorefresh` for auto-sync")

    st.divider()

    # Time horizon selection
    st.subheader("📅 Time Horizon")
    horizon_map = {
        "1 Month": "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year": "1y",
        "5 Years": "5y",
    }
    horizon = st.radio(
        "Select period",
        options=list(horizon_map.keys()),
        index=2,
        label_visibility="collapsed"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main App Content
# ═══════════════════════════════════════════════════════════════════════════════

st.title("📈 Stock Price Chart")

# Stock selector - builds options list including current selection
all_options = sorted(set(STOCKS) | {st.session_state.stock_selector})

st.selectbox(
    "Select Stock",
    options=all_options,
    index=all_options.index(st.session_state.stock_selector) if st.session_state.stock_selector in all_options else 0,
    key="stock_selector"
)

ticker = st.session_state.stock_selector

# ═══════════════════════════════════════════════════════════════════════════════
# Load and Display Data
# ═══════════════════════════════════════════════════════════════════════════════


@st.cache_resource(show_spinner=False, ttl="1h")
def load_data(ticker: str, period: str):
    """Load stock data from Yahoo Finance."""
    stock = yf.Ticker(ticker)
    data = stock.history(period=period)
    if data is None or data.empty:
        return None
    return data["Close"]


with st.spinner(f"Loading {ticker} data..."):
    try:
        data = load_data(ticker, horizon_map[horizon])
    except Exception as e:
        st.error(f"Error loading data: {e}")
        data = None

if data is None or data.empty:
    st.warning(f"Could not load data for {ticker}. The ticker may not exist in Yahoo Finance.")
    st.stop()

# Normalize the data (start at 100)
normalized = (data / data.iloc[0]) * 100

# Calculate stats
start_price = data.iloc[0]
end_price = data.iloc[-1]
change_pct = ((end_price - start_price) / start_price) * 100

# Display metrics
col1, col2, col3 = st.columns(3)
col1.metric("Current Price", f"${end_price:.2f}")
col2.metric("Change", f"{change_pct:+.1f}%", delta=f"{change_pct:+.1f}%")
col3.metric("Period", horizon)

st.divider()

# Create the chart
chart_data = pd.DataFrame({
    "Date": normalized.index,
    "Price (Normalized)": normalized.values
})

chart = (
    alt.Chart(chart_data)
    .mark_line(color="#1f77b4", strokeWidth=2)
    .encode(
        alt.X("Date:T", title="Date"),
        alt.Y("Price (Normalized):Q", title="Normalized Price (Start = 100)", scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("Date:T", title="Date"),
            alt.Tooltip("Price (Normalized):Q", title="Price", format=".2f")
        ]
    )
    .properties(
        title=f"{ticker} - Normalized Price",
        height=500
    )
)

st.altair_chart(chart, width="stretch")

# Show raw data in expander
with st.expander("View Raw Data"):
    st.dataframe(data.tail(20))
