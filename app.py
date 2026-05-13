import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from flask import Flask, render_template_string, send_file

CSV = "/Users/gsv/Documents/UPF/Reto IA/glovo_ops_data_final.csv"
app = Flask(__name__)

TRANSPORT_COLORS = {"MOTORBIKE": "#FFC244", "BICYCLE": "#374151", "CAR": "#6B7280", "WALKER": "#D1D5DB"}
VERTICAL_COLORS  = {"WALL - Partner": "#FFC244", "WALL - NonPartner": "#374151", "COURIER": "#9CA3AF"}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_data():
    df = pd.read_csv(CSV)
    for col in ["activation_time_local", "courier_started_order_local",
                "pickup_time_local", "delivery_time_local"]:
        df[col] = pd.to_datetime(df[col])
    df["delivery_min"] = (
        (df["delivery_time_local"] - df["activation_time_local"]).dt.total_seconds() / 60
    )
    df["date"]    = df["activation_time_local"].dt.date
    df["hour"]    = df["activation_time_local"].dt.hour
    df["weekday"] = df["activation_time_local"].dt.day_name().str[:3]
    weekday_order = [
    "Mon", "Tue", "Wed",
    "Thu", "Fri", "Sat", "Sun"
    ]
    df["weekday"] = pd.Categorical(
    df["weekday"],
    categories=weekday_order,
    ordered=True)
    return df


# ---------------------------------------------------------------------------
# Chart helper — shared layout
# ---------------------------------------------------------------------------
def ch(fig, height=300, title=None):
    if title:
        fig.update_layout(title_text=title)
    fig.update_layout(
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="#F9FAFB",
        margin=dict(l=20, r=20, t=42, b=20),
        font=dict(family="Inter,sans-serif", size=11, color="#374151"),
        title_font=dict(size=13, color="#111827", family="Inter,sans-serif"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------
@app.route("/glovo_icon.png")
def icon():
    return send_file("/Users/gsv/Documents/UPF/Reto IA/glovo_icon.png")


@app.route("/")
def index():
    df = load_data()

    # ---- KPIs ----
    total_orders    = len(df)
    avg_gtv         = df["gtv"].mean()
    avg_fee         = df["delivery_fee"].mean()
    avg_rating      = df["rating"].dropna().mean()
    rating_rate     = df["rating"].notna().mean() * 100
    _corr_df        = df[["delivery_min", "saturation"]].dropna()
    _corr_df        = _corr_df[_corr_df["delivery_min"].between(0, 90)]
    eta_sat_corr    = _corr_df["delivery_min"].corr(_corr_df["saturation"])

    # ---- 1. Orders per day ----
    
    
    by_day = (
        df.groupby("weekday")["saturation"]
          .mean()
          .reset_index(name="avg_saturation")
          .sort_values("weekday")
    )

    fig1 = go.Figure(go.Bar(
        x=by_day["weekday"],
        y=by_day["avg_saturation"].round(1),
        marker=dict(color="#FFC244"),
        text=by_day["avg_saturation"].round(1),
        textposition="outside",
        hovertemplate="%{x}<br><b>Saturación promedio: %{y:.1f}</b><extra></extra>",
    ))

    fig1.update_yaxes(title_text="Saturación promedio")

    c_timeline = ch(fig1, 280, "Promedio de saturación por día")

    # ---- 2. Transport donut ----
    t = df["tranport_type"].value_counts()
    fig2 = go.Figure(go.Pie(
        labels=t.index, values=t.values, hole=0.55,
        marker_colors=[TRANSPORT_COLORS.get(k, "#ccc") for k in t.index],
        textinfo="label+percent",
    ))
    c_transport = ch(fig2, 280, "Transporte")

    # ---- 3. Rating distribution ----
    store_rating = (
        df.dropna(subset=["store_name", "rating"])
        .groupby("store_name")
        .agg(avg_rating=("rating", "mean"), n=("rating", "count"))
        .query("n >= 30")
        .nlargest(15, "n")
        .sort_values("avg_rating")
    )
    fig6 = go.Figure(go.Bar(
        y=store_rating.index,
        x=store_rating["avg_rating"].round(2),
        orientation="h",
        marker=dict(
            color=store_rating["avg_rating"],
            colorscale=[[0, "#EF4444"], [0.5, "#EAB308"], [1, "#22C55E"]],
            cmin=1, cmax=5,
            showscale=False,
        ),
        text=store_rating["avg_rating"].round(2).astype(str) + " ★  (" + store_rating["n"].astype(str) + " ratings)",
        textposition="outside",
        hovertemplate="%{y}<br>Promedio rating: %{x:.2f} ★<extra></extra>",
    ))
    fig6.update_xaxes(title_text="Promedio rating", range=[1, 5.5])
    c_rating = ch(fig6, 360, f"Promedio rating por comercio — {rating_rate:.0f}% de órdenes con reseña")

    # ---- 7. Top 10 stores ----
    top = df["store_name"].dropna().value_counts().head(10)
    fig7 = go.Figure(go.Bar(
        y=top.index[::-1], x=top.values[::-1],
        orientation="h",
        marker_color="#FFC244",
        text=[f"{v:,}" for v in top.values[::-1]],
        textposition="outside",
        hovertemplate="%{y}: %{x:,} orders<extra></extra>",
    ))
    fig7.update_xaxes(title_text="Órdenes")
    c_stores = ch(fig7, 360, "Top 10 comercios")

    # ---- 8. Bad rating reasons (flatten multi-tag) ----
    reasons = (
        df["bad_rating_reason"].dropna()
        .str.split(",").explode().str.strip()
        .value_counts().head(12)
    )
    labels = [r.replace("_", " ").title() for r in reasons.index[::-1]]
    fig8 = go.Figure(go.Bar(
        y=labels, x=reasons.values[::-1],
        orientation="h",
        marker_color="#EF4444",
        text=reasons.values[::-1],
        textposition="outside",
        hovertemplate="%{y}: %{x} reports<extra></extra>",
    ))
    fig8.update_xaxes(title_text="Reports")
    c_reasons = ch(fig8, 360, "Top razones mal reseña")

    # ---- 9. Vertical split ----
    v = df["vertical"].value_counts()
    fig9 = go.Figure(go.Pie(
        labels=[x.replace("WALL - ", "") for x in v.index],
        values=v.values, hole=0.55,
        marker_colors=[VERTICAL_COLORS.get(k, "#ccc") for k in v.index],
        textinfo="label+percent",
    ))
    c_vertical = ch(fig9, 280, "Vertical Split")

    # ---- 10. Delivery time distribution ----
    dt = df["delivery_min"].dropna().clip(0, 90)
    fig_dt = go.Figure(go.Histogram(
        x=dt, nbinsx=60,
        marker_color="#FFC244", marker_line_color="white", marker_line_width=0.5,
        opacity=0.9,
        hovertemplate="~%{x:.0f} min: %{y} orders<extra></extra>",
    ))
    fig_dt.add_shape(type="line", x0=dt.mean(), x1=dt.mean(), y0=0, y1=1, yref="paper",
        line=dict(color="#EF4444", width=2, dash="dash"))
    fig_dt.add_annotation(x=dt.mean(), y=0.95, yref="paper",
        text=f"Mean: {dt.mean():.1f} min", showarrow=False,
        xanchor="left", font=dict(color="#EF4444", size=11))
    fig_dt.update_xaxes(title_text="Minutos (inicio → entrega)")
    fig_dt.update_yaxes(title_text="Órdenes")
    c_deliv_dist = ch(fig_dt, 300, "Tiempo de distribución de entrega")

    # ---- 11. Scatter: delivery_min vs saturation ----
    scatter_df = df[["delivery_min", "saturation"]].dropna()
    scatter_df = scatter_df[scatter_df["delivery_min"].between(0, 90)]
    corr = scatter_df["delivery_min"].corr(scatter_df["saturation"])
    sample_s = scatter_df.sample(min(3000, len(scatter_df)), random_state=42)
    fig_sc = go.Figure(go.Scatter(
        x=sample_s["saturation"],
        y=sample_s["delivery_min"],
        mode="markers",
        marker=dict(color="#FFC244", size=3, opacity=0.4),
        hovertemplate="Saturación: %{x}<br>Delivery: %{y:.1f} min<extra></extra>",
    ))
    # trend line via numpy
    import numpy as np
    m, b = np.polyfit(scatter_df["saturation"], scatter_df["delivery_min"], 1)
    xs = np.array([scatter_df["saturation"].min(), scatter_df["saturation"].max()])
    fig_sc.add_trace(go.Scatter(
        x=xs, y=m * xs + b, mode="lines",
        line=dict(color="#EF4444", width=2),
        name=f"Trend (r={corr:.2f})",
        hoverinfo="skip",
    ))
    fig_sc.update_xaxes(title_text="Saturation")
    fig_sc.update_yaxes(title_text="Delivery Time (min)")
    fig_sc.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    c_deliv_scatter = ch(fig_sc, 300, f"Tiempo de entrega vs Saturación  (r = {corr:.3f})")

    # ---- 12. Map — aggregated pickup locations ----
    df["lat_r"] = df["pickup_latitude"].round(3)
    df["lon_r"] = df["pickup_longitude"].round(3)
    agg = df.groupby(["lat_r", "lon_r"]).agg(
        order_count=("order_id", "count"),
        saturation=("saturation", "mean"),
        store_name=("store_name", lambda x: x.dropna().mode()[0] if len(x.dropna()) > 0 else "Unknown"),
    ).reset_index()

    fig_map = go.Figure(go.Scattermap(
        lat=agg["lat_r"],
        lon=agg["lon_r"],
        mode="markers",
        marker=dict(
            size=agg["order_count"].apply(lambda v: max(2, v ** 0.5 * 0.6)),
            color=agg["saturation"],
            colorscale="YlOrRd",
            colorbar=dict(title="Promedio saturación"),
            opacity=0.8,
        ),
        text=agg["store_name"] + "<br>Orders: " + agg["order_count"].astype(str)
             + "<br>Promedio saturación: " + agg["saturation"].round(1).astype(str),
        hoverinfo="text",
    ))
    fig_map.update_layout(
        map=dict(style="open-street-map", center=dict(lat=48.864, lon=2.327), zoom=12),
        height=500,
        margin=dict(l=0, r=0, t=42, b=0),
        paper_bgcolor="white",
        title_text="Pickup Locations — Orders & Saturation",
        title_font=dict(size=13, color="#111827", family="Inter,sans-serif"),
        font=dict(family="Inter,sans-serif", size=11),
    )
    c_map = fig_map.to_html(full_html=False, include_plotlyjs=False,
                            config={"displayModeBar": False})

    return render_template_string(TEMPLATE,
        total_orders=f"{total_orders:,}",
        avg_gtv=f"{avg_gtv:.2f}€",
        avg_fee=f"{avg_fee:.2f}€",
        avg_rating=f"{avg_rating:.2f}",
        eta_sat_corr=f"{eta_sat_corr:.0%}",
        c_timeline=c_timeline,
        c_transport=c_transport,
        c_rating=c_rating,
        c_stores=c_stores,
        c_reasons=c_reasons,
        c_vertical=c_vertical,
        c_deliv_dist=c_deliv_dist,
        c_deliv_scatter=c_deliv_scatter,
        c_map=c_map,
    )


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Glovo Paris Ops Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-3.3.1.min.js"></script>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Inter',sans-serif;background:#F3F4F6;color:#111827}

    /* Header */
    .header{background:#fdc151;color:#111827;padding:18px 32px;display:flex;align-items:center;gap:14px}
    .header-logo{width:36px;height:36px;display:flex;align-items:center;justify-content:center;border:1.5px solid #111827;border-radius:6px;overflow:hidden}
    .header-logo img{width:36px;height:36px;object-fit:contain}
    .header h1{font-size:20px;font-weight:700;letter-spacing:-0.3px}
    .header .sub{font-size:12px;color:#7a5a00;margin-top:2px}

    /* Main */
    .main{padding:24px 28px;max-width:1400px;margin:0 auto}

    /* KPI row */
    .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
    .kpi{background:white;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
    .kpi .label{font-size:11px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
    .kpi .value{font-size:26px;font-weight:700;color:#111827;line-height:1}
    .kpi .accent{color:#FFC244}

    /* Chart cards */
    .grid{display:grid;gap:16px;margin-bottom:16px}
    .g-3{grid-template-columns:2fr 1fr 1fr}
    .g-2{grid-template-columns:1fr 1fr}
    .g-21{grid-template-columns:2fr 1fr}
    .g-1{grid-template-columns:1fr}
    .card{background:white;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);overflow:hidden;padding:4px}
  </style>
</head>
<body>

<div class="header">
  <div class="header-logo"> <img src='glovo_icon.png'> </div>
  <div>
    <h1>Glovo</h1>
    <div class="sub">Oct – Nov 2019 &nbsp;·&nbsp; 63,646 orders &nbsp;</div>
  </div>
</div>

<div class="main">

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi">
      <div class="label">Total órdenes</div>
      <div class="value accent">{{ total_orders }}</div>
    </div>
    <div class="kpi">
      <div class="label">GTV promedio</div>
      <div class="value">{{ avg_gtv }}</div>
    </div>
    <div class="kpi">
      <div class="label">Tarifa de entrega promedio</div>
      <div class="value">{{ avg_fee }}</div>
    </div>
    <div class="kpi">
      <div class="label">Promedio rating</div>
      <div class="value">{{ avg_rating }} <span style="font-size:18px;color:#FFC244">★</span></div>
    </div>
  </div>

  <!-- Map -->
  <div class="grid g-1">
    <div class="card">{{ c_map | safe }}</div>
  </div>

  <!-- Row 1: timeline (wide) + transport + vertical -->
  <div class="grid g-3">
    <div class="card">{{ c_timeline | safe }}</div>
    <div class="card">{{ c_transport | safe }}</div>
    <div class="card">{{ c_vertical | safe }}</div>
  </div>

  <!-- Row 2: rating + top stores -->
  <div class="grid g-2">
    <div class="card">{{ c_rating | safe }}</div>
    <div class="card">{{ c_stores | safe }}</div>
  </div>

  <!-- Bad rating reasons -->
  <div class="grid g-1">
    <div class="card">{{ c_reasons | safe }}</div>
  </div>

  <!-- Delivery time distribution + scatter -->
  <div class="grid g-2">
    <div class="card">{{ c_deliv_dist | safe }}</div>
    <div class="card">{{ c_deliv_scatter | safe }}</div>
  </div>

</div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True, port=5050)
