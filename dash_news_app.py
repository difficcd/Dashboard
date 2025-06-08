from dash import Dash, html, dcc, Input, Output, State
from urllib.parse import urlparse, parse_qs
import plotly.graph_objects as go
from dbmanage_NewsReact import NewsSentiment
from dbmanage_News import SessionLocal

def create_dash_app():
    app = Dash(__name__, requests_pathname_prefix="/dash_news_app/")

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),

        # 1. 총 댓글 수 및 통계 텍스트
        html.Div(id='stats-text'),

        # 2. legend를 그래프 밖에 수동으로 생성
        html.Div([
            html.Span([
                html.Span("●", style={'color': '#6B74C4', 'marginRight': '5px'}),
                html.Span("긍정", style={'color': '#2B2B2B'})
            ], style={'marginRight': '15px'}),

            html.Span([
                html.Span("●", style={'color': '#C5C5D0', 'marginRight': '5px'}),
                html.Span("부정", style={'color': '#2B2B2B'})
            ], style={'marginRight': '15px'}),

            html.Span([
                html.Span("●", style={'color': '#C1CBEC', 'marginRight': '5px'}),
                html.Span("중립", style={'color': '#2B2B2B'})
            ])
        ], style={
            'display': 'flex',
            'justifyContent': 'left',
            'fontWeight': 'bold',
            'fontSize': '14px',
            'margin': '20px 0',
            'margin-left': '50px'
        }),


        # 3. 그래프
        dcc.Graph(
            id='sentiment-pie',
            config={"displayModeBar": False},
            style={"height": "500px", "maxHeight": "500px"}
        )
    ], style={
        'width': '100%',
        'maxWidth': '600px',
        'margin': '0 auto',
        'overflow': 'hidden'
    })


    

    @app.callback(
        Output('sentiment-pie', 'figure'),  
        Output('stats-text', 'children'),
        Input('url', 'href')
    )

    def update_output(href):
        # URL에서 page 쿼리 파라미터 추출
        parsed_url = urlparse(href)
        query_params = parse_qs(parsed_url.query)
        page = int(query_params.get('page', [1])[0])  # 기본은 1페이지

        # 페이지 번호를 기반으로 쿼리 수행 (예: 최신 page번째 결과 가져오기)
        session = SessionLocal()
        # Dash 내부 수정
        sentiment = session.query(NewsSentiment).order_by(NewsSentiment.id).offset(page - 1).limit(1).first()

        session.close()

        if sentiment:
            positive = sentiment.positive_count
            negative = sentiment.negative_count
            neutral = sentiment.neutral_count
            total = positive + negative + neutral

            labels = ["긍정", "부정", "중립"]
            values = [positive, negative, neutral]

            fig = go.Figure(data=[go.Pie(
                labels=labels,
                textfont=dict(size=16),
                values=values,
                hole=0.35,
                marker=dict(colors=["#6B74C4", "#C5C5D0", "#C1CBEC"]),
                textinfo='label+percent',
                textposition='outside',  # ✅ 바깥쪽으로 위치
                insidetextorientation='radial'
            )])

            fig.update_layout(
                hoverlabel=dict(
                    bgcolor="white",      # 배경색 흰색
                    bordercolor="#AAA",   # 테두리 색
                    font_size=18,
                    font_color="black",
                    namelength=-1
                ),
                showlegend=False,
                autosize=False,
                margin=dict(t=50, b=50, l=50, r=50), # 줄임
                legend=dict(orientation="h", y=-0.2),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=500
            )


            stats_text = html.Div([
                html.P(f"총 댓글건수 {total}건", style={'margin': '0 10px'}),
                html.P(f"부정적 댓글 {negative}건", style={'margin': '0 10px'}),
                html.P(f"긍정적 댓글 {positive}건", style={'margin': '0 10px'}),
                html.P(f"중립적 댓글 {neutral}건", style={'margin': '0 10px'}),
            ], style={
                'display': 'flex',
                'justifyContent': 'center',
                'fontWeight': 'bold',
                'color': '#555',
                'fontSize': '16px',
                'marginTop': '5px'  
            })
        else:
            fig = go.Figure(data=[go.Pie(labels=["데이터 없음"], values=[1], hole=0.5)])
            stats_text = html.Div("감정 분석 데이터가 없습니다.", style={'textAlign': 'center', 'marginTop': '20px'})

        return fig, stats_text

    return app





def create_dash_app_from_result(sentiment_result: dict):
    app = Dash(__name__, requests_pathname_prefix="/dash_news_app_live/")

    app.layout = html.Div([
        # 통계 텍스트
        html.Div(id='stats-text'),

        # 범례
        html.Div([
            html.Span([
                html.Span("●", style={'color': '#6B74C4', 'marginRight': '5px'}),
                html.Span("긍정", style={'color': '#2B2B2B'})
            ], style={'marginRight': '15px'}),
            html.Span([
                html.Span("●", style={'color': '#C5C5D0', 'marginRight': '5px'}),
                html.Span("부정", style={'color': '#2B2B2B'})
            ], style={'marginRight': '15px'}),
            html.Span([
                html.Span("●", style={'color': '#C1CBEC', 'marginRight': '5px'}),
                html.Span("중립", style={'color': '#2B2B2B'})
            ])
        ], style={
            'display': 'flex',
            'justifyContent': 'left',
            'fontWeight': 'bold',
            'fontSize': '14px',
            'margin': '20px 0',
            'margin-left': '50px'
        }),

        # 그래프
        dcc.Graph(
            id='sentiment-pie',
            config={"displayModeBar": False},
            style={"height": "500px", "maxHeight": "500px"}
        )
    ], style={
        'width': '100%',
        'maxWidth': '600px',
        'margin': '0 auto',
        'overflow': 'hidden'
    })

    @app.callback(
        Output('sentiment-pie', 'figure'),
        Output('stats-text', 'children'),
        Input('sentiment-pie', 'id')  # 아무 트리거나 필요해서 사용
    )
    def update_output(_):
        positive = sentiment_result.get("긍정적 인식", 0)
        negative = sentiment_result.get("부정적 인식", 0)
        neutral = sentiment_result.get("중립", 0)
        total = positive + negative + neutral

        labels = ["긍정", "부정", "중립"]
        values = [positive, negative, neutral]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            textfont=dict(size=16),
            values=values,
            hole=0.35,
            marker=dict(colors=["#6B74C4", "#C5C5D0", "#C1CBEC"]),
            textinfo='label+percent',
            textposition='outside',
            insidetextorientation='radial'
        )])

        fig.update_layout(
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="#AAA",
                font_size=18,
                font_color="black",
                namelength=-1
            ),
            showlegend=False,
            autosize=False,
            margin=dict(t=50, b=50, l=50, r=50),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=500
        )

        stats_text = html.Div([
            html.P(f"총 댓글건수 {total}건", style={'margin': '0 10px'}),
            html.P(f"부정적 댓글 {negative}건", style={'margin': '0 10px'}),
            html.P(f"긍정적 댓글 {positive}건", style={'margin': '0 10px'}),
            html.P(f"중립적 댓글 {neutral}건", style={'margin': '0 10px'}),
        ], style={
            'display': 'flex',
            'justifyContent': 'center',
            'fontWeight': 'bold',
            'color': '#555',
            'fontSize': '16px',
            'marginTop': '5px'
        })

        return fig, stats_text

    return app


