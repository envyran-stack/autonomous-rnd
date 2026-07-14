"""3.2 OpenAI_API + 3.4 Tool_Calling 실습 기반 Streamlit 챗봇."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytz
import requests
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from openai import OpenAI

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

MODEL = "gpt-4o-mini"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant. Use tools when needed. "
    "시간, 주식, 날씨 질문에는 반드시 도구를 사용하세요. 답변은 한국어로 해."
)

CITY_TZ = {
    "서울": "Asia/Seoul",
    "seoul": "Asia/Seoul",
    "뉴욕": "America/New_York",
    "new york": "America/New_York",
    "도쿄": "Asia/Tokyo",
    "tokyo": "Asia/Tokyo",
    "런던": "Europe/London",
    "london": "Europe/London",
    "파리": "Europe/Paris",
    "paris": "Europe/Paris",
}


def get_city_time_tz(city: str) -> str:
    key = city.strip().lower()
    tz_name = CITY_TZ.get(key) or CITY_TZ.get(city.strip())
    if not tz_name:
        return json.dumps(
            {"error": f"지원하지 않는 도시: {city}"},
            ensure_ascii=False,
        )

    now = datetime.now(pytz.timezone(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(
        {"city": city, "timezone": tz_name, "current_time": now},
        ensure_ascii=False,
    )


def get_us_stock_price(ticker: str) -> str:
    symbol = ticker.strip().upper()
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period="2d")
        if hist.empty:
            return json.dumps(
                {"error": f"{symbol} 데이터가 없습니다."},
                ensure_ascii=False,
            )

        latest = hist.iloc[-1]
        close_price = float(latest["Close"]) if "Close" in latest else None
        open_price = float(latest["Open"]) if "Open" in latest else None

        return json.dumps(
            {
                "ticker": symbol,
                "open": round(open_price, 2) if open_price is not None else None,
                "close": round(close_price, 2) if close_price is not None else None,
                "currency": "USD",
                "source": "yfinance",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def get_weather(city: str) -> str:
    try:
        response = requests.get(
            f"https://wttr.in/{city.strip()}",
            params={"format": "j1"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        current = data["current_condition"][0]

        return json.dumps(
            {
                "city": city,
                "temp_c": current["temp_C"],
                "weather": current["weatherDesc"][0]["value"],
                "humidity": current["humidity"],
                "wind_kmph": current["windspeedKmph"],
                "source": "wttr.in",
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_city_time_tz",
            "description": "도시의 시간대를 반영해 현재 시간을 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_us_stock_price",
            "description": "미국 주식 티커의 최근 시가/종가 정보를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "도시의 현재 날씨 정보를 반환합니다.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_city_time_tz": get_city_time_tz,
    "get_us_stock_price": get_us_stock_price,
    "get_weather": get_weather,
}


@st.cache_resource
def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
    if not api_key:
        st.error(
            f"API 키가 없습니다. `{ENV_PATH}` 파일에 "
            "`OPENAI_API_KEY=sk-...` 를 설정하세요."
        )
        st.stop()
    return OpenAI(api_key=api_key)


def _assistant_message_dict(message) -> dict:
    data = {"role": "assistant", "content": message.content}
    if message.tool_calls:
        data["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ]
    return data


def run_agent_with_tools(
    client: OpenAI,
    messages: list[dict],
    temperature: float,
    max_rounds: int = 5,
) -> tuple[str, list[str]]:
    working_messages = list(messages)
    tool_logs: list[str] = []

    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model=MODEL,
            temperature=temperature,
            messages=working_messages,
            tools=TOOLS,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return message.content or "", tool_logs

        working_messages.append(_assistant_message_dict(message))

        for tool_call in message.tool_calls:
            fn_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")
            result = TOOL_FUNCTIONS[fn_name](**args)
            tool_logs.append(f"{fn_name}({args}) -> {result}")
            working_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return "도구 호출이 너무 많아 답변을 마무리하지 못했습니다.", tool_logs


def main():
    st.set_page_config(page_title="OpenAI Tool 챗봇", page_icon="🛠️")
    st.title("🛠️ OpenAI Tool Calling 챗봇")
    st.caption("3.2 OpenAI_API + 3.4 Tool_Calling 실습 · Streamlit")

    with st.sidebar:
        st.header("설정")
        temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.1)
        system_prompt = st.text_area(
            "System 프롬프트",
            value=DEFAULT_SYSTEM_PROMPT,
            height=120,
        )

        st.subheader("사용 가능한 Tool")
        st.markdown(
            "- `get_city_time_tz` : 도시 시간 조회\n"
            "- `get_us_stock_price` : 미국 주식 조회\n"
            "- `get_weather` : 도시 날씨 조회"
        )
        st.markdown("**예시 질문**")
        st.code(
            "서울 지금 몇 시야?\n"
            "AAPL 주가 알려줘\n"
            "도쿄 날씨 어때?",
            language=None,
        )

        if st.button("대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("tool_logs"):
                with st.expander("Tool 호출 내역"):
                    for log in message["tool_logs"]:
                        st.code(log)

    if prompt := st.chat_input("메시지를 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        api_messages = [
            {"role": "system", "content": system_prompt},
            *[
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
                if m["role"] in ("user", "assistant")
            ],
        ]

        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                try:
                    client = get_client()
                    answer, tool_logs = run_agent_with_tools(
                        client, api_messages, temperature
                    )
                    st.markdown(answer)
                    if tool_logs:
                        with st.expander("Tool 호출 내역"):
                            for log in tool_logs:
                                st.code(log)
                except Exception as e:
                    answer = f"오류가 발생했습니다: {e}"
                    tool_logs = []
                    st.error(answer)

        if not answer.startswith("오류가 발생했습니다"):
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "tool_logs": tool_logs,
                }
            )


if __name__ == "__main__":
    main()
