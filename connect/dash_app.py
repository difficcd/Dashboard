from dash import Dash, html, dcc, Input, Output

import plotly.graph_objects as go

import urllib.request
import urllib.parse
from urllib.parse import parse_qs, urlparse
import json
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
import numpy as np
from scipy.interpolate import make_interp_spline
from datetime import date
import time




# API 키 및 회기별 기간 정보
API_KEY = "68da180a494a4cc3b8add2071dc95242"
AGE_DATE_MAP = {
    20: (datetime(2016, 5, 30), datetime(2020, 5, 29)),
    21: (datetime(2020, 7, 16), datetime(2024, 5, 29)),
    22: (datetime(2024, 5, 30), datetime(2028, 5, 29)),  # 추정
}

# 법안 수집 함수
def get_bills_by_age(age, year=None):
    url = "https://open.assembly.go.kr/portal/openapi/TVBPMBILL11"
    bills = []
    p_index = 1
    p_size = 1000

    # 연도 범위로 종료 조건 설정
    year_end_cutoff = None
    if year:
        year_end_cutoff = datetime(year, 12, 31)

    while True:
        params = {
            "KEY": API_KEY,
            "Type": "json",
            "pIndex": p_index,
            "pSize": p_size,
            "AGE": age
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"

        try:
            time.sleep(0.5)
            req = urllib.request.Request(
                full_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Connection": "close"
                }
            )
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read())

            items = data.get("TVBPMBILL11", [])
            if len(items) < 2 or "row" not in items[1]:
                break

            rows = items[1]["row"]
            for row in rows:
                dt_str = row.get("PROPOSE_DT", "").strip()
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                except:
                    continue

                # 연도 필터링
                if year and dt.year != year:
                    continue

                bills.append(dt_str)

            if len(rows) < p_size:
                break
            p_index += 1

        except Exception as e:
            print(f" AGE {age} PAGE {p_index} Error: {e}")
            break

    return bills


# 월별로 그룹화
def group_bills_by_month(bills, target_year):
    counter = defaultdict(int)
    for dt_str in bills:
        try:
            dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d")
            if dt.year == target_year:
                ym = dt.strftime("%Y-%m")
                counter[ym] += 1
        except:
            continue
    return counter

# 그래프 생성 함수
def create_figure(all_data, target_year):
    today = date.today()
    last_month = today.month if target_year == today.year else 12

    fig = go.Figure()
    added_any_trace = False  # 유효한 데이터가 있는지 확인

    for age, data in all_data.items():
        start_date, end_date = AGE_DATE_MAP.get(age, (None, None))
        start_month = 1
        end_month = last_month

        if start_date:
            if start_date.year > target_year:
                continue
            elif start_date.year == target_year:
                start_month = start_date.month

        if end_date:
            if end_date.year < target_year:
                continue
            elif end_date.year == target_year:
                end_month = end_date.month

        # 유효 월 범위
        x_all = list(range(start_month - 1, end_month))

        # 누락 월 0 보정
        filled_data = defaultdict(int, data)
        for month_idx in x_all:
            ym = f"{target_year}-{month_idx + 1:02d}"
            _ = filled_data[ym]  # 접근만 해도 0으로 초기화됨

        y_all = [filled_data[f"{target_year}-{month_idx + 1:02d}"] for month_idx in x_all]

        if not x_all or not y_all or sum(y_all) == 0:
            continue  # 아무 값도 없으면 제외

        added_any_trace = True

        if len(set(y_all)) > 1 and len(x_all) >= 4:
            try:
                x_smooth = np.linspace(min(x_all), max(x_all), 300)
                spline = make_interp_spline(x_all, y_all, k=3)
                y_smooth = spline(x_smooth)

                fig.add_trace(go.Scatter(
                    x=x_smooth, y=y_smooth,
                    mode="lines",
                    line=dict(width=3, color="#4b65a2"),
                    name=f"{age}대 국회",
                    hoverinfo="skip"
                ))
                fig.add_trace(go.Scatter(
                    x=x_all, y=y_all,
                    mode="markers",
                    marker=dict(color="#4b65a2", size=8),
                    showlegend=False
                ))
            except Exception:
                fig.add_trace(go.Scatter(
                    x=x_all, y=y_all,
                    mode="lines+markers",
                    name=f"{age}대 국회",
                    line=dict(color="#4b65a2")
                ))
        else:
            fig.add_trace(go.Scatter(
                x=x_all, y=y_all,
                mode="lines+markers",
                name=f"{age}대 국회",
                line=dict(color="#4b65a2")
            ))

    # 대수 시작점 표시
    ymax = max((max(d.values() or [0]) for d in all_data.values()), default=0) * 0.95
    for age, (start_date, _) in AGE_DATE_MAP.items():
        if start_date.year == target_year:
            month_idx = start_date.month - 1
            if month_idx < last_month:
                fig.add_vline(x=month_idx, line_dash="dash", line_color="gray")
                fig.add_annotation(
                    x=month_idx, y=ymax,
                    text=f"{age}대 ({start_date.strftime('%m/%d')})",
                    showarrow=False,
                    font=dict(color="gray")
                )

    if not added_any_trace:
        fig.update_layout(
            title=f"{target_year}년 월별 국회 법안 발의건수 (데이터 없음)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
    else:
        fig.update_layout(
            title=f"{target_year}년 월별 국회 법안 발의건수",
            yaxis_title="발의 건수",
            hovermode="x unified",
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis=dict(tickformat=".0f", rangemode="tozero"),
            xaxis=dict(
                tickmode="array",
                tickvals=list(range(last_month)),
                ticktext=[f"{i+1:02d}월" for i in range(last_month)],
                rangemode="normal"
            )
        )

    return fig







# 임베드 준비 app 생성
def create_dash_app():

    app = Dash(
        __name__,
        requests_pathname_prefix='/dash/',  # FastAPI에서 mount할 경로
    )

    @app.callback(Output('graph', 'figure'), [Input('url', 'href')])
    def load_data(href):
        year = 2025
        if href:
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            if 'year' in query:
                try:
                    year = int(query['year'][0])
                except:
                    pass

    # 연도와 겹치는 모든 회기를 리스트로 수집
        target_ages = []
        for age, (start, end) in AGE_DATE_MAP.items():
            if start.year <= year <= end.year:
                target_ages.append(age)

        if not target_ages:
            return go.Figure(layout=dict(
                title="선택한 연도에 해당하는 국회 회기 정보가 없습니다.",
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            ))

        print(f"\n {year}년 → 대상 회기: {target_ages}")

        # 여러 회기의 데이터 수집
        all_bills_by_age = {}
        for age in target_ages:
            bills = get_bills_by_age(age, year)
            print(f" ▶ {age}대 국회: {len(bills)}건 수집 완료")
            grouped = group_bills_by_month(bills, target_year=year)
            all_bills_by_age[age] = grouped

        return create_figure(all_bills_by_age, target_year=year)


    app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div([  # 그래프와 버튼을 포괄하는 컨테이너
        dcc.Loading(
            id="loading",
            type="circle",
            color="#364A79", 
            children=[
                dcc.Graph(
                    id="graph",
                    style={"height": "300px"},
                    config={'displaylogo': False}
                )
            ]
        )
    ], style={"position": "relative"})  # 겹치기를 위한 부모 컨테이너 설정
])




    return app

