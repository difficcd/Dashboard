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
    month_labels = [f"{target_year}-{str(m+1).zfill(2)}" for m in range(12)]
    fig = go.Figure()

    for age, data in all_data.items():
        monthly_data = {k: v for k, v in data.items() if k.startswith(str(target_year))}
        if not monthly_data:
            continue

        sorted_items = sorted(monthly_data.items())
        x_labels = [item[0] for item in sorted_items]
        y = [item[1] for item in sorted_items]
        x = [month_labels.index(label) for label in x_labels if label in month_labels]

        if len(x) >= 4:
            try:
                x_smooth = np.linspace(min(x), max(x), 300)
                spline = make_interp_spline(x, y, k=3)
                y_smooth = spline(x_smooth)
                fig.add_trace(go.Scatter(
                    x=[f"{(int(i)+1):02d}월" for i in x_smooth],
                    y=y_smooth,
                    mode='lines',
                    name=f"{age}대 국회",
                    line=dict(width=3, color="#485CA3") 
                ))
            except:
                fig.add_trace(go.Scatter(
                    x=[f"{x_+1}월" for x_ in x],
                    y=y,
                    mode='lines+markers',
                    name=f"{age}대 국회",
                    line=dict(color="#485CA3")  
                ))
        else:
            fig.add_trace(go.Scatter(
                x=[f"{x_+1}월" for x_ in x],
                y=y,
                mode='lines+markers',
                name=f"{age}대 국회",
                line=dict(color="#485CA3")  
            ))

    # 회기 시작선 표시
    for age, (start_date, _) in AGE_DATE_MAP.items():
        if start_date.year == target_year:
            month_idx = start_date.month - 1
            fig.add_vline(x=f"{month_idx+1:02d}월", line_dash="dash", line_color="gray")
            fig.add_annotation(
                x=f"{month_idx+1:02d}월",
                y=max(max(data.values(), default=0) for data in all_data.values()) * 0.95,
                text=f"{age}대 ({start_date.strftime('%m/%d')})",
                showarrow=False,
                font=dict(color="gray")
            )

    # 최종 레이아웃 설정 (소수점 제거 포함)
    fig.update_layout(
        title=f"{target_year}년 월별 국회 법안 발의 추이",
        xaxis_title="월",
        yaxis_title="발의 건수",
        template=None,
        hovermode="x unified",
        yaxis=dict(tickformat=".0f", rangemode="tozero"),
        xaxis=dict(rangemode="normal")
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

