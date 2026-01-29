# -*- coding: utf-8 -*-
"""
Stock peer analysis dashboard - With Glue Context Integration

Subscribes to SelectedInstrument context from the Excel demo app.
When an instrument is selected there, it gets added to the tickers here.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import logging
import tempfile
from pathlib import Path
import json
import time
import threading

# Install with: pip install streamlit-autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# Import gluepy for context sharing
from gluepy import (
    glue_ensure_clr,
    subscribe_context,
    glue_lib,
    translate_glue_value,
    GlueState,
    GlueInitCallback,
    active_callbacks
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Stock peer analysis dashboard",
    page_icon=":chart_with_upwards_trend:",
    layout="wide",
)

# ═══════════════════════════════════════════════════════════════════════════════
# Auto-refresh for context updates
# ═══════════════════════════════════════════════════════════════════════════════

# Auto-refresh every 2 seconds when listening for context updates
if HAS_AUTOREFRESH and 'context_subscribed' in st.session_state and st.session_state.context_subscribed:
    st_autorefresh(interval=2000, limit=None, key="context_autorefresh")

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

INSTRUMENT_CONTEXT = "SelectedInstrument"

# File-based IPC for cross-thread context updates
CONTEXT_TRIGGER_FILE = Path(tempfile.gettempdir()) / \
    "glue_context_trigger.json"

# ═══════════════════════════════════════════════════════════════════════════════
# Session State Initialization
# ═══════════════════════════════════════════════════════════════════════════════

if 'glue_initialized' not in st.session_state:
    st.session_state.glue_initialized = False
if 'context_subscribed' not in st.session_state:
    st.session_state.context_subscribed = False
if 'received_ric' not in st.session_state:
    st.session_state.received_ric = None
if 'last_context_timestamp' not in st.session_state:
    st.session_state.last_context_timestamp = 0

# ═══════════════════════════════════════════════════════════════════════════════
# Glue Initialization and Context Subscription
# ═══════════════════════════════════════════════════════════════════════════════


def write_context_signal(ric: str):
    """Write received RIC to file (called from callback thread)."""
    try:
        with open(CONTEXT_TRIGGER_FILE, 'w') as f:
            json.dump({'ric': ric, 'timestamp': time.time()}, f)
        logger.info(f"Context signal written: {ric}")
    except Exception as e:
        logger.error(f"Error writing context signal: {e}")


def read_context_signal() -> tuple[str, float]:
    """Read RIC from file (called from main thread)."""
    try:
        if CONTEXT_TRIGGER_FILE.exists():
            with open(CONTEXT_TRIGGER_FILE, 'r') as f:
                data = json.load(f)
            return data.get('ric'), data.get('timestamp', 0)
    except Exception as e:
        logger.error(f"Error reading context signal: {e}")
    return None, 0


def context_callback(context_name: str, field_path: str, value):
    """
    Callback when the SelectedInstrument context changes.
    This runs in a different thread, so we write to a file.
    """
    logger.info(f"Context update: {context_name}.{field_path} = {value}")
    if value:
        write_context_signal(str(value))


def init_glue_sync():
    """Initialize Glue synchronously for Streamlit."""
    if st.session_state.glue_initialized:
        return True

    try:
        # Ensure CLR is loaded
        result = glue_ensure_clr()
        if result != 0:
            logger.error(f"Failed to initialize CLR: {result}")
            return False

        # We need to manually replicate what initialize_glue does,
        # but in a synchronous way suitable for Streamlit

        import threading

        init_result = {'success': False, 'done': False}
        init_event = threading.Event()

        def glue_init_callback(state, message, glue_payload, cookie):
            decoded_message = message.decode('utf-8') if message else ""
            logger.info(f"Glue state: {state} - {decoded_message}")

            if state == GlueState.INITIALIZED:
                init_result['success'] = True
                init_result['done'] = True
                init_event.set()
            elif state == GlueState.DISCONNECTED:
                init_result['success'] = False
                init_result['done'] = True
                init_event.set()

        # Create the callback - need to keep reference alive
        from gluepy import GlueInitCallback, glue_lib, active_callbacks

        callback_instance = GlueInitCallback(glue_init_callback)
        active_callbacks.append(callback_instance)  # Keep alive

        # Call glue_init
        result = glue_lib.glue_init(
            b"StockPeerAnalysis", callback_instance, None)

        if result != 0:
            logger.error(f"glue_init returned error: {result}")
            active_callbacks.remove(callback_instance)
            return False

        # Wait for initialization with timeout
        if init_event.wait(timeout=10.0):
            if init_result['success']:
                st.session_state.glue_initialized = True
                logger.info("Glue initialized successfully")
                return True
            else:
                logger.error("Glue initialization failed (disconnected)")
                active_callbacks.remove(callback_instance)
                return False
        else:
            logger.error("Glue initialization timed out")
            active_callbacks.remove(callback_instance)
            return False

    except Exception as e:
        logger.error(f"Error initializing Glue: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def setup_context_subscription():
    """Subscribe to the SelectedInstrument context."""
    if st.session_state.context_subscribed:
        return True

    if not st.session_state.glue_initialized:
        return False

    try:
        # Subscribe to the "ric" field in the SelectedInstrument context
        unsubscribe = subscribe_context(
            INSTRUMENT_CONTEXT,
            "ric",
            context_callback
        )
        st.session_state.context_subscribed = True
        logger.info(f"Subscribed to context: {INSTRUMENT_CONTEXT}.ric")

        # Also try to read current value
        try:
            ctx_reader = glue_lib.glue_read_context_sync(
                INSTRUMENT_CONTEXT.encode("utf-8"))
            if ctx_reader:
                value = glue_lib.glue_read_glue_value(ctx_reader, b"ric")
                current_ric = translate_glue_value(value)
                if current_ric:
                    logger.info(f"Current context value: {current_ric}")
                    write_context_signal(current_ric)
        except Exception as e:
            logger.warning(f"Could not read current context value: {e}")

        return True

    except Exception as e:
        logger.error(f"Error subscribing to context: {e}")
        return False


def check_for_context_updates() -> str:
    """Check if there's a new RIC from context. Returns the RIC or None."""
    ric, timestamp = read_context_signal()

    if timestamp > st.session_state.last_context_timestamp:
        st.session_state.last_context_timestamp = timestamp
        if ric:
            logger.info(f"New context RIC detected: {ric}")
            return ric
    return None


def ric_to_ticker(ric: str) -> str:
    """
    Convert a RIC (e.g., VOD:LN) to a Yahoo Finance ticker.

    Common mappings:
    - :LN (London) -> .L
    - :GR (Germany) -> .DE
    - US stocks usually have no suffix
    """
    if not ric:
        return None

    ric = ric.upper().strip()

    # Common RIC to Yahoo ticker mappings
    suffix_map = {
        ":LN": ".L",      # London Stock Exchange
        ":GR": ".DE",     # Germany (Xetra)
        ":FP": ".PA",     # France (Paris)
        ":NA": ".AS",     # Netherlands (Amsterdam)
        ":SM": ".MC",     # Spain (Madrid)
        ":IM": ".MI",     # Italy (Milan)
        ":SW": ".SW",     # Switzerland
        ":AV": ".VI",     # Austria (Vienna)
        ":BB": ".BR",     # Belgium (Brussels)
        ":JP": ".T",      # Japan (Tokyo)
        ":HK": ".HK",     # Hong Kong
        ":AU": ".AX",     # Australia
        ":CN": ".TO",     # Canada (Toronto)
    }

    for ric_suffix, yahoo_suffix in suffix_map.items():
        if ric.endswith(ric_suffix):
            base = ric[:-len(ric_suffix)]
            return base + yahoo_suffix

    # If no suffix match, assume it's a US ticker or return as-is
    if ":" in ric:
        return ric.split(":")[0]

    return ric


# ═══════════════════════════════════════════════════════════════════════════════
# Sidebar - Glue Connection
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.subheader("🔗 io.Connect Integration")

    if not st.session_state.glue_initialized:
        if st.button("Initialize Glue", type="primary", use_container_width=True):
            with st.spinner("Initializing Glue..."):
                if init_glue_sync():
                    st.success("Glue initialized!")
                    st.rerun()
                else:
                    st.error("Failed to initialize Glue")
    else:
        st.success("✓ Glue Connected")

        if not st.session_state.context_subscribed:
            if st.button("Subscribe to Context", use_container_width=True):
                if setup_context_subscription():
                    st.success("Subscribed!")
                    st.rerun()
                else:
                    st.error("Failed to subscribe")
        else:
            st.success(f"✓ Listening to `{INSTRUMENT_CONTEXT}`")

            if HAS_AUTOREFRESH:
                st.caption("🔄 Auto-refresh: Active (2s)")
            else:
                st.warning("Install `streamlit-autorefresh` for auto-updates")
                st.code("pip install streamlit-autorefresh", language="bash")

            if st.session_state.received_ric:
                st.info(f"Last received: **{st.session_state.received_ric}**")

    st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# Check for context updates and add to tickers
# ═══════════════════════════════════════════════════════════════════════════════

new_ric = None
if st.session_state.context_subscribed:
    new_ric = check_for_context_updates()
    if new_ric:
        st.session_state.received_ric = new_ric


# ═══════════════════════════════════════════════════════════════════════════════
# Main App Content
# ═══════════════════════════════════════════════════════════════════════════════

"""
# :material/query_stats: Stock peer analysis

Easily compare stocks against others in their peer group.
"""

""

cols = st.columns([1, 3])

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

DEFAULT_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "TSLA", "META"]


def stocks_to_str(stocks):
    return ",".join(stocks)


if "tickers_input" not in st.session_state:
    st.session_state.tickers_input = st.query_params.get(
        "stocks", stocks_to_str(DEFAULT_STOCKS)
    ).split(",")


# If we received a new RIC from context, convert and add it
if new_ric:
    yahoo_ticker = ric_to_ticker(new_ric)
    if yahoo_ticker:
        logger.info(
            f"Converting RIC {new_ric} to Yahoo ticker: {yahoo_ticker}")
        # Add to the list if not already present
        if yahoo_ticker.upper() not in [t.upper() for t in st.session_state.tickers_input]:
            st.session_state.tickers_input.append(yahoo_ticker.upper())
            st.toast(f"📥 Added {yahoo_ticker} from {new_ric}", icon="✅")


def update_query_param():
    if st.session_state.tickers_input:
        st.query_params["stocks"] = stocks_to_str(
            st.session_state.tickers_input)
    else:
        st.query_params.pop("stocks", None)


top_left_cell = cols[0].container(
    border=True, height="stretch", vertical_alignment="center")

with top_left_cell:
    # Show context integration status
    if st.session_state.context_subscribed:
        st.caption("🔗 Listening for instruments from io.Connect")

    tickers = st.multiselect(
        "Stock tickers",
        options=sorted(set(STOCKS) | set(st.session_state.tickers_input)),
        default=st.session_state.tickers_input,
        placeholder="Choose stocks to compare. Example: NVDA",
        accept_new_options=True,
    )

horizon_map = {
    "1 Months": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "5 Years": "5y",
    "10 Years": "10y",
    "20 Years": "20y",
}

with top_left_cell:
    horizon = st.pills(
        "Time horizon",
        options=list(horizon_map.keys()),
        default="6 Months",
    )

tickers = [t.upper() for t in tickers]

if tickers:
    st.query_params["stocks"] = stocks_to_str(tickers)
else:
    st.query_params.pop("stocks", None)

if not tickers:
    top_left_cell.info("Pick some stocks to compare", icon=":material/info:")
    st.stop()


right_cell = cols[1].container(
    border=True, height="stretch", vertical_alignment="center")


@st.cache_resource(show_spinner=False, ttl="6h")
def load_data(tickers, period):
    tickers_obj = yf.Tickers(tickers)
    data = tickers_obj.history(period=period)
    if data is None:
        raise RuntimeError("YFinance returned no data.")
    return data["Close"]


try:
    data = load_data(tickers, horizon_map[horizon])
except yf.exceptions.YFRateLimitError as e:
    st.warning("YFinance is rate-limiting us :(\nTry again later.")
    load_data.clear()
    st.stop()

# Check for completely empty columns (tickers with no data at all)
empty_columns = data.columns[data.isna().all()].tolist()

if empty_columns:
    st.warning(
        f"Could not load data for: {', '.join(empty_columns)}. These tickers may not exist in Yahoo Finance.")
    # Remove the problematic tickers from the data
    data = data.drop(columns=empty_columns)
    # Also filter them from the tickers list for downstream processing
    tickers = [t for t in tickers if t not in empty_columns]

    if data.empty or len(tickers) == 0:
        st.error("No valid stock data available.")
        st.stop()

normalized = data.div(data.iloc[0])

# Filter out NaN values when calculating best/worst
latest_norm_values = {}
for ticker in tickers:
    val = normalized[ticker].iat[-1]
    if pd.notna(val):  # Only include non-NaN values
        latest_norm_values[val] = ticker

bottom_left_cell = cols[0].container(
    border=True, height="stretch", vertical_alignment="center")

with bottom_left_cell:
    if latest_norm_values:
        max_norm_value = max(latest_norm_values.items())
        min_norm_value = min(latest_norm_values.items())

        metric_cols = st.columns(2)
        metric_cols[0].metric(
            "Best stock",
            max_norm_value[1],
            delta=f"{round(max_norm_value[0] * 100)}%",
            width="content",
        )
        metric_cols[1].metric(
            "Worst stock",
            min_norm_value[1],
            delta=f"{round(min_norm_value[0] * 100)}%",
            width="content",
        )
    else:
        st.warning("No valid stock data available")


with right_cell:
    st.altair_chart(
        alt.Chart(
            normalized.reset_index().melt(
                id_vars=["Date"], var_name="Stock", value_name="Normalized price"
            )
        )
        .mark_line()
        .encode(
            alt.X("Date:T"),
            alt.Y("Normalized price:Q").scale(zero=False),
            alt.Color("Stock:N"),
        )
        .properties(height=400)
    )

""
""

"""
## Individual stocks vs peer average

For the analysis below, the "peer average" when analyzing stock X always
excludes X itself.
"""

if len(tickers) <= 1:
    st.warning("Pick 2 or more tickers to compare them")
    st.stop()

NUM_COLS = 4
chart_cols = st.columns(NUM_COLS)

for i, ticker in enumerate(tickers):
    peers = normalized.drop(columns=[ticker])
    peer_avg = peers.mean(axis=1)

    plot_data = pd.DataFrame(
        {
            "Date": normalized.index,
            ticker: normalized[ticker],
            "Peer average": peer_avg,
        }
    ).melt(id_vars=["Date"], var_name="Series", value_name="Price")

    chart = (
        alt.Chart(plot_data)
        .mark_line()
        .encode(
            alt.X("Date:T"),
            alt.Y("Price:Q").scale(zero=False),
            alt.Color(
                "Series:N",
                scale=alt.Scale(
                    domain=[ticker, "Peer average"], range=["red", "gray"]),
                legend=alt.Legend(orient="bottom"),
            ),
            alt.Tooltip(["Date", "Series", "Price"]),
        )
        .properties(title=f"{ticker} vs peer average", height=300)
    )

    cell = chart_cols[(i * 2) % NUM_COLS].container(border=True)
    cell.write("")
    cell.altair_chart(chart, use_container_width=True)

    plot_data = pd.DataFrame(
        {
            "Date": normalized.index,
            "Delta": normalized[ticker] - peer_avg,
        }
    )

    chart = (
        alt.Chart(plot_data)
        .mark_area()
        .encode(
            alt.X("Date:T"),
            alt.Y("Delta:Q").scale(zero=False),
        )
        .properties(title=f"{ticker} minus peer average", height=300)
    )

    cell = chart_cols[(i * 2 + 1) % NUM_COLS].container(border=True)
    cell.write("")
    cell.altair_chart(chart, use_container_width=True)

""
""

"""
## Raw data
"""

data
