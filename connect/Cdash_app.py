from dash import Dash, html, dcc, Input, Output
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import urllib.request
import urllib.parse
import json
import time
import threading
from collections import defaultdict
from urllib.parse import parse_qs
from dbmanage import load_from_db, save_to_db # DB 관리 모듈 

API_KEY = "68da180a494a4cc3b8add2071dc95242"
DEFAULT_AGES = [20, 21, 22]
P_SIZE = 1000

cancel_flag = threading.Event() # 상태 저장 변수
running_flag = threading.Event()  # 현재 작업 실행 중 여부

last_ages = None  # 전역 변수로 이동

def get_committee_counts_and_total(ages=DEFAULT_AGES):
    if cancel_flag.is_set():
        print("[CANCELLED BEFORE START]")
        return {}, 0

    endpoint = "https://open.assembly.go.kr/portal/openapi/TVBPMBILL11"
    running_flag.set()

    try:
        committee_counts, total_count = load_from_db(ages)
        if total_count > 0:
            print("[DB HIT]")
            return committee_counts, total_count
        
        committee_counts = defaultdict(int)
        total_count = 0

        for age in ages:
            print(f"\n[START] AGE={age}")
            page = 1
            while True:
                if cancel_flag.is_set():
                    print(f"[CANCELLED] AGE={age} PAGE={page}")
                    return {}, 0  # running_flag will be cleared in finally

                # API 요청 처리
                params = {
                    "KEY": API_KEY,
                    "Type": "json",
                    "pIndex": page,
                    "pSize": P_SIZE,
                    "AGE": age
                }
                url = f"{endpoint}?{urllib.parse.urlencode(params)}"

                try:
                    print(f"  [Request] AGE={age} PAGE={page}")
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    response = urllib.request.urlopen(req)
                    data = json.loads(response.read())

                    items = data.get("TVBPMBILL11", [])
                    if len(items) < 2 or "row" not in items[1]:
                        print(f"  [No More Data] AGE={age} PAGE={page}")
                        break

                    rows = items[1]["row"]
                    if isinstance(rows, dict):
                        rows = [rows]

                    for row in rows:
                        committee = row.get("CURR_COMMITTEE", "미지정")
                        committee_counts[committee] += 1
                        total_count += 1

                    print(f"  [Fetched] AGE={age} PAGE={page} ROWS={len(rows)} TOTAL={total_count}")

                    if len(rows) < P_SIZE:
                        print(f"  [Last Page] AGE={age} PAGE={page}")
                        break

                    page += 1

                except Exception as e:
                    print(f"  [Error] AGE={age} PAGE={page} Error: {e}")
                    break
            save_to_db(dict(committee_counts), age)

        print(f"\n[COMPLETE] Total count for AGES {ages}: {total_count}")
        print(f"[Committee Counts]: {dict(committee_counts)}")
        return dict(committee_counts), total_count

    finally:
        running_flag.clear()  #  무조건 실행되도록 finally에서 처리

        

def create_figure(committee_counts, total_count, top_n=15):
    print(f"\n[Create Figure] Total Count: {total_count}")
    sorted_items = sorted(committee_counts.items(), key=lambda x: x[1], reverse=True)
    top_items = sorted_items[:top_n]
    other_items = sorted_items[top_n:]

    top_labels = [k for k, _ in top_items]
    top_counts = [v for _, v in top_items]
    top_percentages = [v / total_count * 100 for v in top_counts]

    if other_items:
        other_count = sum(v for _, v in other_items)
        other_percentage = other_count / total_count * 100
        top_labels.append("기타")
        top_counts.append(other_count)
        top_percentages.append(other_percentage)

    fig = go.Figure(
        go.Bar(
            x=top_labels,
            y=top_percentages,
            marker=dict(color="#939BD7"),
            width=0.55,
            text=[f"{p:.1f}%" for p in top_percentages],
            textposition='outside',
            hovertemplate=(
                "<b>%{x}</b><br>"
                "제출 건수: %{customdata[0]:,}건<br>"
                "비율: %{y:.1f}%<extra></extra>"
            ),
            customdata=[[c] for c in top_counts]
        )
    )

    fig.update_layout(
        yaxis_title="제출 비율 (%)",
        paper_bgcolor='white',
        plot_bgcolor='white',
        height=650,
        margin=dict(l=40, r=40, t=50, b=100),
        xaxis_tickangle=-30,
        xaxis=dict(tickfont=dict(size=7.5)),
        yaxis=dict(tickfont=dict(size=10)),
        uniformtext=dict(mode='hide', minsize=8),
        hoverlabel=dict(
            bgcolor="white",
            font=dict(color="black")
        )
    )

    return fig

def create_Cdash_app():
    app = Dash(__name__, requests_pathname_prefix='/dash2/', suppress_callback_exceptions=True)
    app.enable_dev_tools(debug=True, dev_tools_ui=True, dev_tools_props_check=True)

    @app.callback(
        Output('graph', 'figure'),
        Input('url', 'search')
    )
    def update_graph(search):
        global last_ages  # 전역 변수 사용
        print(f"\n[CALLBACK TRIGGERED] search={search}")
        if not search:
            raise PreventUpdate

        try:
            query = parse_qs(search[1:])
            print(f"[PARSED QUERY] {query}")
            age_list = [int(age) for age in query.get("age", [])]
            print(f"[AGE LIST] {age_list}")
        except Exception as e:
            print(f"[ERROR PARSING] {e}")
            age_list = DEFAULT_AGES

        age_list_sorted = sorted(age_list)
        if last_ages is None or age_list_sorted != last_ages:
            last_ages = age_list_sorted

            cancel_flag.set()
            while running_flag.is_set():
                time.sleep(0.05)
            cancel_flag.clear()

            committee_counts, total_count = get_committee_counts_and_total(age_list_sorted)
            return create_figure(committee_counts, total_count)

        print("기존 대수와 동일 → PreventUpdate")
        raise PreventUpdate

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div([
            dcc.Loading(
                id="loading",
                type="circle",
                color="#364A79",
                children=[
                    dcc.Graph(
                        id="graph",
                        style={"height": "280px"}
                    )
                ]
            )
        ], style={"position": "relative"})
    ])

    return app
